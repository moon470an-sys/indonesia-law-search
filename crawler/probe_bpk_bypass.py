"""Attempt to bypass Cloudflare on peraturan.bpk.go.id.

Strategies tried (in order):
  1. curl_cffi with Chrome131 impersonation
     — mimics real Chrome's TLS/JA4 fingerprint, defeats most Cloudflare
  2. Playwright + stealth patches + cookie warming
     — visits homepage first to acquire cf_clearance cookie, then targets
  3. Playwright with realistic browser config (UA, viewport, timezone)

For each strategy:
  - Hit /Home, /Search?p=1, /Home/ResultByJenis?jenis=Peraturan+Menteri&p=1
  - Record status, body length, presence of result rows
  - Dump first viable HTML to data/probe/bpk_<strategy>.html

Output: data/probe_bpk.json
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

TARGETS = [
    ("home", "https://peraturan.bpk.go.id/Home"),
    ("search", "https://peraturan.bpk.go.id/Search?keywords=&jenis=&pemrakarsa=&p=1"),
    ("permen", "https://peraturan.bpk.go.id/Home/ResultByJenis?jenis=Peraturan+Menteri&p=1"),
    ("kepmen", "https://peraturan.bpk.go.id/Home/ResultByJenis?jenis=Keputusan+Menteri&p=1"),
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# CSS selectors that, if present, suggest we got past Cloudflare to the real app
SUCCESS_HINTS = [
    "card-list",  # BPK uses Bootstrap card lists
    "result-item",
    "search-result",
    "list-result",
    "fragment-detail",
    "Peraturan Menteri",  # title text
    "Hasil pencarian",    # "search results" in Indonesian
    "Total",
]

CHALLENGE_HINTS = [
    "Just a moment",            # cloudflare interstitial title
    "cf-browser-verification",
    "cf_chl_",
    "Checking your browser",
    "Attention Required",
    "Sorry, you have been blocked",
]


def evaluate(html: str) -> dict:
    found_success = [h for h in SUCCESS_HINTS if h.lower() in html.lower()]
    found_challenge = [h for h in CHALLENGE_HINTS if h.lower() in html.lower()]
    # row-counters
    rows = len(re.findall(r"<tr[\s>]", html, re.IGNORECASE))
    cards = len(re.findall(r'class="[^"]*card[^"]*"', html, re.IGNORECASE))
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.IGNORECASE | re.DOTALL)
    return {
        "len": len(html),
        "title": (title_m.group(1).strip()[:120] if title_m else None),
        "rows": rows, "cards": cards,
        "success_hints": found_success,
        "challenge_hints": found_challenge,
    }


# === Strategy 1: curl_cffi ===
async def try_curl_cffi() -> dict:
    out: dict = {"strategy": "curl_cffi", "results": []}
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError as e:
        out["error"] = f"curl_cffi not installed: {e}"
        return out

    Path("data/probe").mkdir(parents=True, exist_ok=True)
    async with AsyncSession(impersonate="chrome131") as s:
        # warm: visit landing
        try:
            r0 = await s.get("https://peraturan.bpk.go.id/", timeout=20)
            out["warmup"] = {"status": r0.status_code, "len": len(r0.content)}
        except Exception as e:
            out["warmup"] = {"error": str(e)[:200]}

        for label, url in TARGETS:
            try:
                r = await s.get(url, timeout=25)
                ev = evaluate(r.text)
                rec = {"label": label, "url": url, "status": r.status_code, **ev}
                if r.status_code == 200 and len(r.content) > 8000 and not ev["challenge_hints"]:
                    Path(f"data/probe/bpk_curl_{label}.html").write_text(r.text[:600_000], encoding="utf-8")
                    rec["dumped"] = True
                out["results"].append(rec)
            except Exception as e:
                out["results"].append({"label": label, "url": url, "error": str(e)[:200]})
    return out


# === Strategy 2: Playwright + stealth + cookie warming ===
STEALTH_JS = """
() => {
  // Common detection vectors used by Cloudflare/anti-bot
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  Object.defineProperty(navigator, 'languages', { get: () => ['id-ID', 'id', 'en-US', 'en'] });
  Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
  Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
  // Chrome-specific
  window.chrome = { runtime: {}, app: {}, csi: () => {}, loadTimes: () => {} };
  // Permissions
  const orig = navigator.permissions.query;
  navigator.permissions.query = (p) =>
    p.name === 'notifications' ? Promise.resolve({state: 'denied'}) : orig(p);
}
"""


async def try_playwright_stealth() -> dict:
    out: dict = {"strategy": "playwright_stealth", "results": []}
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        out["error"] = f"playwright missing: {e}"
        return out

    Path("data/probe").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
        )
        ctx = await browser.new_context(
            user_agent=UA,
            locale="id-ID",
            timezone_id="Asia/Jakarta",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
        )
        await ctx.add_init_script(STEALTH_JS)

        page = await ctx.new_page()
        page.set_default_timeout(45_000)

        # Warmup: visit homepage and wait long enough for any JS challenge to clear
        try:
            r0 = await page.goto("https://peraturan.bpk.go.id/", wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(8000)  # allow CF challenge to complete
            home_html = await page.content()
            out["warmup"] = {"status": r0.status if r0 else None, "len": len(home_html), **evaluate(home_html)}
            if r0 and r0.status == 200 and len(home_html) > 8000:
                Path("data/probe/bpk_pw_home.html").write_text(home_html[:600_000], encoding="utf-8")
        except Exception as e:
            out["warmup"] = {"error": str(e)[:200]}

        for label, url in TARGETS:
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                await page.wait_for_timeout(5000)
                html = await page.content()
                ev = evaluate(html)
                rec = {"label": label, "url": url, "status": resp.status if resp else None, **ev}
                if resp and resp.status == 200 and len(html) > 8000 and not ev["challenge_hints"]:
                    Path(f"data/probe/bpk_pw_{label}.html").write_text(html[:600_000], encoding="utf-8")
                    rec["dumped"] = True
                out["results"].append(rec)
            except Exception as e:
                out["results"].append({"label": label, "url": url, "error": str(e)[:200]})

        await browser.close()
    return out


async def main() -> None:
    out: dict = {}
    out["curl_cffi"] = await try_curl_cffi()
    out["playwright_stealth"] = await try_playwright_stealth()

    Path("data").mkdir(exist_ok=True)
    Path("data/probe_bpk.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    def fmt_result(r: dict) -> str:
        if "error" in r:
            return f"ERR  {r.get('label','?')}: {r['error'][:80]}"
        ch = ",".join(r.get("challenge_hints", [])) or "-"
        sc = ",".join(r.get("success_hints", [])) or "-"
        return (f"{r.get('status'):>3}  len={r.get('len',0):>6} rows={r.get('rows',0):>3} "
                f"cards={r.get('cards',0):>3} chal=[{ch}] succ=[{sc}] "
                f"{'DUMPED' if r.get('dumped') else ''}  {r.get('label')}")

    for strat in ("curl_cffi", "playwright_stealth"):
        s = out[strat]
        print(f"\n========== {strat} ==========")
        if s.get("error"):
            print(f"  STRATEGY ERROR: {s['error']}")
            continue
        if s.get("warmup"):
            print(f"  warmup: {s['warmup']}")
        for r in s.get("results", []):
            print(f"  {fmt_result(r)}")


if __name__ == "__main__":
    asyncio.run(main())
