"""Probe OJK JDIH with Playwright (handles Cloudflare/JS).

Discover the actual list page URL and dump first-page HTML structure
so we can write the scraper.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

CANDIDATES = [
    "https://jdih.ojk.go.id/",
    "https://jdih.ojk.go.id/home",
    "https://jdih.ojk.go.id/dokumen/peraturan",
    "https://jdih.ojk.go.id/peraturan",
    "https://jdih.ojk.go.id/regulasi",
    "https://jdih.ojk.go.id/produk-hukum",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


async def main() -> None:
    out: list[dict] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="id-ID")
        page = await ctx.new_page()
        page.set_default_timeout(25_000)

        for url in CANDIDATES:
            try:
                resp = await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)  # let JS render
                title = await page.title()
                final = page.url
                # extract all <a href> for nav discovery
                anchors = await page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({h: a.href, t: (a.textContent || '').trim().slice(0, 80)}))
                        .filter(x => x.h.startsWith('https://jdih.ojk.go.id'))
                        .slice(0, 60)"""
                )
                body_len = len(await page.content())
                out.append({
                    "url": url, "final_url": final, "status": resp.status if resp else None,
                    "title": title, "body_len": body_len, "anchors": anchors,
                })
            except Exception as e:
                out.append({"url": url, "error": str(e)[:200]})

        # if we found a list page, dump its full HTML
        list_candidates = [
            r for r in out
            if isinstance(r, dict) and r.get("final_url")
            and any(k in r.get("final_url", "").lower() for k in ("regulasi", "peraturan", "produk"))
            and r.get("status") == 200
        ]
        if list_candidates:
            target = list_candidates[0]["final_url"]
            await page.goto(target, wait_until="networkidle")
            html = await page.content()
            Path("data/probe").mkdir(parents=True, exist_ok=True)
            Path("data/probe/ojk_list.html").write_text(html, encoding="utf-8")
            out.append({"dumped_html_for": target, "size": len(html)})

        await browser.close()

    Path("data").mkdir(exist_ok=True)
    Path("data/probe_ojk.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps([{k: v for k, v in r.items() if k != "anchors"} for r in out], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
