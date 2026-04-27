"""Probe central JDIHN aggregator + 5 sample 'unknown' member sites.

Goal: determine if jdihn.go.id provides a usable API/feed across all
member ministry JDIH sites (would short-circuit per-site scraping).

Outputs:
  data/probe/jdihn.html         — central site landing
  data/probe/jdihn_search.html  — search/list page if reachable
  data/probe/<host>.html        — sample list page from 5 unknown sites
  data/probe_jdihn.json         — summary (URLs tried, sizes, anchors)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

JDIHN_URLS = [
    "https://jdihn.go.id/",
    "https://jdihn.go.id/home",
    "https://jdihn.go.id/pencarian/index/peraturan",
    "https://jdihn.go.id/pencarian",
    "https://jdihn.go.id/api/peraturan",
    "https://jdihn.go.id/api/v1/peraturan",
    "https://jdihn.go.id/api/list/peraturan",
    "https://jdihn.go.id/peraturan",
    "https://jdihn.go.id/dokumen/peraturan",
]

# Try a sample of "unknown" sites discovered earlier — pick high-priority ones
SAMPLE_HOSTS = [
    "ojk.go.id",          # tier 1
    "kemenperin.go.id",   # tier 1
    "menlhk.go.id",       # tier 1
    "atrbpn.go.id",       # tier 1
    "pu.go.id",           # tier 1
    "kemnaker.go.id",     # tier 1
    "kominfo.go.id",      # tier 1
    "pom.go.id",          # tier 1
]


async def fetch_one(ctx, url: str, dump_path: Path | None = None) -> dict:
    page = await ctx.new_page()
    page.set_default_timeout(25_000)
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        await page.wait_for_timeout(2500)
        html = await page.content()
        title = await page.title()
        anchors = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({h: a.href, t: (a.textContent || '').trim().slice(0, 80)}))
                .slice(0, 50)"""
        )
        if dump_path and len(html) > 2000:
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(html[:600_000], encoding="utf-8")
        return {
            "url": url, "final": page.url, "status": resp.status if resp else None,
            "title": title, "len": len(html), "anchors": anchors[:25],
            "dumped": str(dump_path) if dump_path and len(html) > 2000 else None,
        }
    except Exception as e:
        return {"url": url, "error": str(e)[:200]}
    finally:
        await page.close()


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    out: dict = {"jdihn": [], "samples": {}}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="id-ID")

        # JDIHN central site
        for i, url in enumerate(JDIHN_URLS):
            slug = url.rstrip("/").split("/")[-1] or f"home_{i}"
            dump = Path(f"data/probe/jdihn_{slug}.html")
            r = await fetch_one(ctx, url, dump)
            out["jdihn"].append(r)
            if r.get("status") == 404 and i > 2:  # skip remaining once we get 404s on APIs
                pass

        # Sample unknown sites — try just /dokumen/peraturan since it's the most common
        for host in SAMPLE_HOSTS:
            url = f"https://jdih.{host}/dokumen/peraturan"
            dump = Path(f"data/probe/sample_{host}.html")
            r = await fetch_one(ctx, url, dump)
            # If 404, also try /
            if isinstance(r, dict) and r.get("status") == 404:
                r2 = await fetch_one(ctx, f"https://jdih.{host}/", Path(f"data/probe/sample_{host}_home.html"))
                out["samples"][host] = {"list": r, "home": r2}
            else:
                out["samples"][host] = {"list": r}

        await browser.close()

    Path("data/probe_jdihn.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    # Compact stdout summary
    print("=== JDIHN central ===")
    for r in out["jdihn"]:
        if "error" in r:
            print(f"  ERR  {r['url']}: {r['error'][:80]}")
        else:
            print(f"  {r['status']}  len={r['len']:>6}  {r['final']}  | {r['title'][:60]}")
    print("\n=== Sample unknown hosts ===")
    for host, d in out["samples"].items():
        for which, r in d.items():
            if "error" in r:
                print(f"  ERR  {host}/{which}: {r['error'][:80]}")
            else:
                print(f"  {r['status']}  len={r['len']:>6}  {host}/{which} → {r['final']}")


if __name__ == "__main__":
    asyncio.run(main())
