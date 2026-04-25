"""Probe ESDM JDIH list page DOM to confirm selectors before finalizing the scraper.

Run: python -m crawler.probe_esdm
"""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

URL = "https://jdih.esdm.go.id/dokumen/peraturan?page=1"


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

        # 1) total length / page title
        title = await page.title()
        print(f"\n=== TITLE ===\n{title}")

        # 2) candidate row containers — print the most frequent direct-child structures
        result = await page.evaluate(
            """
            () => {
              const out = [];
              const candidates = [
                'table tbody tr',
                'ul.list-group > li',
                '.list-item',
                '.card',
                'article',
                'div.row > div',
                'main li',
                'main article',
                'div.col-md-12 > div',
                'a[href*="/dokumen/view"]',
              ];
              for (const sel of candidates) {
                const nodes = document.querySelectorAll(sel);
                out.push({ selector: sel, count: nodes.length });
              }
              return out;
            }
            """
        )
        print("\n=== SELECTOR COUNTS ===")
        for r in result:
            print(f"  {r['count']:>5}  {r['selector']}")

        # 3) For the first /dokumen/view link, dump the closest reasonable ancestor's outerHTML.
        sample = await page.evaluate(
            """
            () => {
              const a = document.querySelector('a[href*="/dokumen/view"]');
              if (!a) return null;
              // walk up at most 5 levels and pick the first that contains other useful info
              let node = a;
              for (let i = 0; i < 5; i++) {
                if (!node.parentElement) break;
                node = node.parentElement;
                if (node.querySelectorAll('a').length >= 2) break;
              }
              return {
                href: a.getAttribute('href'),
                anchorText: a.textContent.trim().slice(0, 200),
                ancestorTag: node.tagName,
                ancestorClass: node.className,
                outerHTML: node.outerHTML.slice(0, 4000),
              };
            }
            """
        )
        print("\n=== SAMPLE ENTRY DOM ===")
        print(json.dumps(sample, indent=2, ensure_ascii=False))

        # 4) pagination
        pag = await page.evaluate(
            """
            () => {
              const nav = document.querySelector('.pagination, ul.pagination, nav');
              return nav ? nav.outerHTML.slice(0, 1500) : null;
            }
            """
        )
        print("\n=== PAGINATION HTML ===")
        print(pag)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
