"""Probe 65 JDIH sites with Playwright (real browser).

For each host:
  1. Visit https://jdih.<host>/  (with retries on schemes/paths)
  2. Find any link whose text or href looks like a regulation list
  3. Visit that list page
  4. Detect template signature (.card-body.no-padding-tb, "Ditampilkan ... dari N Data")

Output: data/probe_jdih_pw.json
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright

SITES = [
    "polkam.go.id", "ekon.go.id", "kemenkopmk.go.id", "maritim.go.id",
    "kemenkopangan.go.id", "kemenkoipk.go.id", "kemenkopolhukam.go.id",
    "dephub.go.id", "kkp.go.id", "menlhk.go.id", "bkpm.go.id",
    "kemenkeu.go.id", "bappenas.go.id", "kemenkopukm.go.id",
    "kemendag.go.id", "kemenperin.go.id", "pertanian.go.id",
    "kemnaker.go.id", "bp2mi.go.id", "kemenkumham.go.id",
    "imigrasi.go.id", "pu.go.id", "pkp.go.id", "atrbpn.go.id",
    "kominfo.go.id", "kemkes.go.id", "kemensos.go.id", "bkkbn.go.id",
    "kemenpppa.go.id", "kemdikbud.go.id", "kemenag.go.id",
    "kemenpora.go.id", "kemendesa.go.id", "kemlu.go.id",
    "kemendagri.go.id", "kemhan.go.id", "menpan.go.id",
    "setneg.go.id", "setkab.go.id", "kemenparekraf.go.id",
    "ojk.go.id", "lps.go.id", "bps.go.id", "pom.go.id",
    "bnpt.go.id", "bnn.go.id", "bpkp.go.id", "anri.go.id",
    "lan.go.id", "brin.go.id", "bmkg.go.id", "bsn.go.id",
    "lkpp.go.id", "kpk.go.id", "komnasham.go.id", "kpu.go.id",
    "mahkamahagung.go.id", "komisiyudisial.go.id",
    "kejaksaan.go.id", "polri.go.id", "tni.mil.id", "bin.go.id",
    "bssn.go.id", "bphmigas.go.id", "mkri.id",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TOTAL_RE = re.compile(r"dari\s+(\d+)\s+Data", re.IGNORECASE)
LIST_LINK_HEURISTIC = """
() => {
  const cands = ['/dokumen/peraturan','/peraturan','/dokumen/index','/peraturan/index','/produk-hukum','/produk_hukum','/regulasi','/peraturan-perundang-undangan','/document/peraturan'];
  const all = Array.from(document.querySelectorAll('a[href]'));
  for (const c of cands) {
    const a = all.find(x => (x.getAttribute('href')||'').toLowerCase().includes(c));
    if (a) return a.getAttribute('href');
  }
  const a = all.find(x => {
    const t = (x.textContent||'').trim();
    const h = x.getAttribute('href')||'';
    return /peraturan/i.test(t) && (h.startsWith('http') || h.startsWith('/'));
  });
  return a ? a.getAttribute('href') : null;
}
"""


async def probe_host(browser, host: str) -> dict:
    out: dict = {"host": host}
    context = await browser.new_context(user_agent=UA, locale="id-ID")
    page = await context.new_page()
    page.set_default_timeout(35_000)
    base = f"https://jdih.{host}"
    try:
        try:
            await page.goto(base, wait_until="domcontentloaded", timeout=35_000)
        except Exception as e:
            out.update({"category": "error", "detail": f"home: {e}"[:200]})
            await context.close()
            return out
        # Try the standard path first
        std_url = f"{base}/dokumen/peraturan"
        try:
            await page.goto(std_url, wait_until="domcontentloaded", timeout=35_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)
            txt = await page.content()
            if "card-body" in txt and "no-padding-tb" in txt:
                m = TOTAL_RE.search(txt)
                out.update({
                    "category": "standard",
                    "list_url": std_url,
                    "total": int(m.group(1)) if m else None,
                })
                await context.close()
                return out
        except Exception:
            pass
        # Fall back: discover list link on home page
        try:
            await page.goto(base, wait_until="domcontentloaded", timeout=30_000)
            href = await page.evaluate(LIST_LINK_HEURISTIC)
        except Exception as e:
            out.update({"category": "error", "detail": f"home2: {e}"[:200]})
            await context.close()
            return out
        if not href:
            out.update({"category": "unknown", "detail": "no list link found on home"})
            await context.close()
            return out
        list_url = urljoin(base, href)
        try:
            await page.goto(list_url, wait_until="domcontentloaded", timeout=35_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)
            txt = await page.content()
        except Exception as e:
            out.update({"category": "error", "detail": f"list: {e}"[:200], "list_url": list_url})
            await context.close()
            return out
        has_card = "card-body" in txt and "no-padding-tb" in txt
        m = TOTAL_RE.search(txt)
        if has_card and m:
            out.update({
                "category": "standard",
                "list_url": list_url,
                "total": int(m.group(1)),
            })
        elif has_card or m:
            out.update({
                "category": "partial",
                "list_url": list_url,
                "total": int(m.group(1)) if m else None,
                "has_card": has_card,
            })
        else:
            out.update({"category": "unknown", "list_url": list_url})
    except Exception as e:
        out.update({"category": "error", "detail": str(e)[:200]})
    finally:
        try:
            await context.close()
        except Exception:
            pass
    return out


async def main() -> None:
    sem = asyncio.Semaphore(6)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        async def guarded(host: str) -> dict:
            async with sem:
                return await probe_host(browser, host)
        results = await asyncio.gather(*(guarded(h) for h in SITES))
        await browser.close()
    out = sorted(results, key=lambda x: (x["category"], -(x.get("total") or 0)))
    Path("data").mkdir(exist_ok=True)
    with open("data/probe_jdih_pw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    by = {}
    for r in out:
        by.setdefault(r["category"], []).append(r["host"])
    print(json.dumps({k: len(v) for k, v in by.items()}, indent=2))
    for cat, hosts in by.items():
        print(f"  [{cat}] {hosts}")
    print(f"wrote data/probe_jdih_pw.json ({len(out)} sites)")


if __name__ == "__main__":
    asyncio.run(main())
