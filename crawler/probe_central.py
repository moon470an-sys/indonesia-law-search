"""Probe alternative central sources for Indonesian regulations.

Goal: find a source that aggregates ministry-level Permen/Kepmen across
all ministries, so we don't have to build 65 custom scrapers.

Targets:
  1. peraturan.bpk.go.id  (Audit Board — comprehensive, ministry-filterable)
  2. jdihn.bphn.go.id     (BPHN — official JDIHN aggregator backend)
  3. data.go.id           (open data portal)

For each target we try:
  - landing/search pages
  - JSON API endpoints (REST conventions)
  - per-ministry filter URLs
  - first-page DOM selector probe (count of result rows)

Outputs:
  data/probe_central.json     — structured results per target
  data/probe/central_<n>.html — HTML dumps of viable list pages

Run on GitHub Actions:
  python -m crawler.probe_central
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

# === peraturan.bpk.go.id ===
BPK_URLS = [
    "https://peraturan.bpk.go.id/",
    "https://peraturan.bpk.go.id/Home",
    "https://peraturan.bpk.go.id/Search",
    "https://peraturan.bpk.go.id/Search?keywords=&jenis=&pemrakarsa=&p=1",
    "https://peraturan.bpk.go.id/Details",  # detail prefix
    # filtered by ministry (kementerian) — try a known one
    "https://peraturan.bpk.go.id/Home/ResultByJenis?jenis=Peraturan%20Menteri",
    "https://peraturan.bpk.go.id/Home/ResultByPemrakarsa",
    # API / JSON conventions
    "https://peraturan.bpk.go.id/api/Search",
    "https://peraturan.bpk.go.id/api/peraturan",
]

# === jdihn.bphn.go.id ===
JDIHN_URLS = [
    "https://jdihn.bphn.go.id/",
    "https://jdihn.bphn.go.id/api",
    "https://jdihn.bphn.go.id/api/peraturan",
    "https://jdihn.bphn.go.id/api/v1/peraturan",
    "https://jdihn.bphn.go.id/api/v1/dokumen",
    "https://jdihn.bphn.go.id/data/peraturan",
    "https://jdihn.bphn.go.id/peraturan",
    "https://jdihn.bphn.go.id/search",
    # the public-facing search may be on different host
    "https://jdihn.go.id/",  # repeat from earlier — confirm DNS
    "https://www.jdihn.go.id/",
]

# === data.go.id ===
DATAGOID_URLS = [
    "https://data.go.id/",
    "https://data.go.id/dataset?q=peraturan",
    "https://data.go.id/dataset?q=jdih",
    "https://data.go.id/api/3/action/package_search?q=peraturan",
    "https://data.go.id/api/3/action/package_list",
]


async def httpx_probe(client: httpx.AsyncClient, url: str) -> dict:
    """Light probe — just GET, record status/size/ctype/title."""
    try:
        r = await client.get(url, follow_redirects=True, timeout=20.0)
        ctype = r.headers.get("content-type", "")
        body = r.text if "html" in ctype or "json" in ctype or "text" in ctype else ""
        title_m = re.search(r"<title[^>]*>(.*?)</title>", body or "", re.IGNORECASE | re.DOTALL)
        # for JSON, sample the keys
        json_keys = None
        if "json" in ctype:
            try:
                obj = r.json()
                if isinstance(obj, dict):
                    json_keys = list(obj.keys())[:20]
                elif isinstance(obj, list):
                    json_keys = ["[list]", f"len={len(obj)}"]
                    if obj and isinstance(obj[0], dict):
                        json_keys.append(f"item_keys={list(obj[0].keys())[:10]}")
            except Exception as e:
                json_keys = [f"json-parse-err: {e!s}"[:100]]
        return {
            "url": url, "status": r.status_code, "final": str(r.url),
            "ctype": ctype, "len": len(r.content),
            "title": (title_m.group(1).strip()[:120] if title_m else None),
            "json_keys": json_keys,
        }
    except Exception as e:
        return {"url": url, "error": str(e)[:200]}


async def pw_probe_with_dump(ctx, url: str, dump_to: Path | None = None) -> dict:
    page = await ctx.new_page()
    page.set_default_timeout(30_000)
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3000)
        html = await page.content()
        title = await page.title()
        # detect total/result count patterns
        patterns = [
            r"(\d+(?:[\.,]\d{3})*)\s*(?:hasil|results?|dokumen|peraturan|data)",
            r"dari\s+(\d+(?:[\.,]\d{3})*)",
            r"total[^0-9]{0,20}(\d+(?:[\.,]\d{3})*)",
        ]
        totals = []
        for p in patterns:
            for m in re.finditer(p, html, re.IGNORECASE):
                totals.append(m.group(0))
        # anchors that look like detail/list links
        anchors = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({h: a.href, t: (a.textContent || '').trim().slice(0, 80)}))
                .filter(x => /peraturan|search|dokumen|details?|jenis|pemrakarsa|api/i.test(x.h))
                .slice(0, 40)"""
        )
        if dump_to and len(html) > 5000:
            dump_to.parent.mkdir(parents=True, exist_ok=True)
            dump_to.write_text(html[:600_000], encoding="utf-8")
        return {
            "url": url, "status": resp.status if resp else None, "final": page.url,
            "title": title, "len": len(html),
            "totals_found": totals[:8],
            "anchors": anchors,
            "dumped": str(dump_to) if dump_to and len(html) > 5000 else None,
        }
    except Exception as e:
        return {"url": url, "error": str(e)[:200]}
    finally:
        await page.close()


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    out: dict = {"bpk_httpx": [], "jdihn_httpx": [], "datagoid_httpx": [],
                 "bpk_pw": [], "jdihn_pw": []}

    # Phase 1: lightweight httpx probes for all URLs
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID,en;q=0.5"}) as client:
        for url in BPK_URLS:
            out["bpk_httpx"].append(await httpx_probe(client, url))
        for url in JDIHN_URLS:
            out["jdihn_httpx"].append(await httpx_probe(client, url))
        for url in DATAGOID_URLS:
            out["datagoid_httpx"].append(await httpx_probe(client, url))

    # Phase 2: Playwright probe with HTML dumps for the most promising URLs
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="id-ID")

        # BPK: dump landing + a search results page
        bpk_pw_targets = [
            ("https://peraturan.bpk.go.id/Home", "central_bpk_home.html"),
            ("https://peraturan.bpk.go.id/Search?keywords=&jenis=&p=1", "central_bpk_search.html"),
            ("https://peraturan.bpk.go.id/Home/ResultByJenis?jenis=Peraturan+Menteri&p=1",
             "central_bpk_permen.html"),
        ]
        for url, fname in bpk_pw_targets:
            r = await pw_probe_with_dump(ctx, url, Path(f"data/probe/{fname}"))
            out["bpk_pw"].append(r)

        # JDIHN: dump landing + try API
        jdihn_pw_targets = [
            ("https://jdihn.bphn.go.id/", "central_jdihn_bphn_home.html"),
            ("https://jdihn.bphn.go.id/peraturan", "central_jdihn_bphn_list.html"),
        ]
        for url, fname in jdihn_pw_targets:
            r = await pw_probe_with_dump(ctx, url, Path(f"data/probe/{fname}"))
            out["jdihn_pw"].append(r)

        await browser.close()

    Path("data/probe_central.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    # Compact summary
    def summarize(label: str, items: list[dict]) -> None:
        print(f"\n=== {label} ===")
        for r in items:
            if "error" in r:
                print(f"  ERR  {r['url']}: {r['error'][:90]}")
            else:
                extra = ""
                if r.get("json_keys"):
                    extra = f"  json={r['json_keys']}"
                if r.get("totals_found"):
                    extra += f"  totals={r['totals_found']}"
                print(f"  {r.get('status')}  {r.get('len','?'):>7}  {r.get('ctype','')[:20]:<20}  {r['url']}{extra}")

    summarize("BPK httpx", out["bpk_httpx"])
    summarize("BPK Playwright", out["bpk_pw"])
    summarize("JDIHN httpx", out["jdihn_httpx"])
    summarize("JDIHN Playwright", out["jdihn_pw"])
    summarize("data.go.id httpx", out["datagoid_httpx"])


if __name__ == "__main__":
    asyncio.run(main())
