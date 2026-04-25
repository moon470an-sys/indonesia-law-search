"""Probe peraturan.go.id list/detail page DOM via Playwright."""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

CANDIDATES = [
    "https://peraturan.go.id/",
    "https://peraturan.go.id/uu",
    "https://peraturan.go.id/pp",
    "https://peraturan.go.id/perpres",
    "https://peraturan.go.id/permen",
    "https://peraturan.go.id/uu/2023",
]


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            locale="id-ID",
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        page.set_default_timeout(45_000)

        for url in CANDIDATES:
            print(f"\n>>> {url}")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                print(f"   HTTP {resp.status if resp else '?'} title={await page.title()!r}")
                # 첫 anchor 30개
                hrefs = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('a[href]'))
                                .map(a => a.getAttribute('href'))
                                .filter(h => h && (h.startsWith('/') || h.includes('peraturan.go.id')))
                                .slice(0, 30)
                    """
                )
                for h in hrefs:
                    print(f"     a {h}")
            except Exception as e:
                print(f"   ERR {type(e).__name__}: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
