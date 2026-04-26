"""Probe pagination size + nav categories on jdih.esdm.go.id.

Run: python -m crawler.probe_esdm_pages
"""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

URL = "https://jdih.esdm.go.id/dokumen/peraturan?page=1&per-page=50"


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-probe/0.1"
            ),
            locale="id-ID",
        )
        page = await ctx.new_page()
        page.set_default_timeout(30_000)
        await page.goto(URL, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")

        result = await page.evaluate(
            """
            () => {
              const out = {};
              // pagination summary text
              const summaries = Array.from(document.querySelectorAll('.summary, .pagination-summary, .pagination, nav'));
              out.summary_texts = summaries.map(n => (n.textContent || '').trim().slice(0, 400));
              // last-page link
              const lastLinks = Array.from(document.querySelectorAll('a[href*="page="]'))
                .map(a => a.getAttribute('href'));
              out.page_hrefs = lastLinks.slice(-25);
              // top nav menu
              const nav = Array.from(document.querySelectorAll('nav a, .navbar a, .sidebar a, aside a, .menu a'))
                .map(a => ({text: (a.textContent || '').trim().slice(0,80), href: a.getAttribute('href')}))
                .filter(x => x.href && x.text);
              out.nav = nav.slice(0, 60);
              return out;
            }
            """
        )
        out_path = "data/probe_esdm_pages.json"
        import os
        os.makedirs("data", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"wrote {out_path}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
