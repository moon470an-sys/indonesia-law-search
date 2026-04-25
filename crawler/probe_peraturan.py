"""Probe peraturan.go.id list pages to discover real DOM structure.

Designed to run inside GitHub Actions (US-region runner) where the site
is reachable. Output is plain text on stdout — capture as a workflow log
or upload as an artifact.
"""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

TARGETS = [
    ("home",    "https://peraturan.go.id/"),
    ("uu",      "https://peraturan.go.id/uu"),
    ("pp",      "https://peraturan.go.id/pp"),
    ("perpres", "https://peraturan.go.id/perpres"),
    ("permen",  "https://peraturan.go.id/permen"),
    ("perda",   "https://peraturan.go.id/perda"),
]

# We try each candidate selector and report counts. The first one with
# enough hits wins, and we dump the first matching node's outerHTML so a
# human reader can confirm the structure.
CANDIDATES = [
    "table tbody tr",
    "ul.list-group > li",
    ".list-group-item",
    "div.card",
    "article",
    ".result-item",
    ".law-item",
    ".peraturan-item",
    "div.row > div.col",
    'a[href*="/details/"]',
    'a[href*="/uu/"]',
    'a[href*="/pp/"]',
    'a[href*="/perpres/"]',
    'a[href*="/permen/"]',
    'a[href*="/perda/"]',
    'a[href*=".pdf"]',
]


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-probe/0.2"
            ),
            locale="id-ID",
            ignore_https_errors=True,
        )

        for label, url in TARGETS:
            print(f"\n========================================")
            print(f"=== {label}: {url}")
            print(f"========================================")
            page = await ctx.new_page()
            page.set_default_timeout(60_000)
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                http = resp.status if resp else "?"
                print(f"HTTP {http}; final URL = {page.url}")
                title = await page.title()
                print(f"title = {title!r}")

                try:
                    await page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass

                # selector counts
                counts = await page.evaluate(
                    """
                    (selectors) => selectors.map(sel => {
                      try { return [sel, document.querySelectorAll(sel).length]; }
                      catch(e) { return [sel, -1]; }
                    })
                    """,
                    CANDIDATES,
                )
                print("\n-- selector counts --")
                for sel, n in counts:
                    if n > 0:
                        print(f"  {n:>5}  {sel}")

                # detail link sample
                link_dump = await page.evaluate(
                    """
                    () => {
                      const sels = ['a[href*="/details/"]','a[href*="/uu/"]','a[href*="/pp/"]',
                                    'a[href*="/perpres/"]','a[href*="/permen/"]','a[href*="/perda/"]'];
                      let nodes = [];
                      for (const s of sels) {
                        nodes = Array.from(document.querySelectorAll(s));
                        if (nodes.length >= 2) break;
                      }
                      return nodes.slice(0, 5).map(a => ({
                        href: a.getAttribute('href'),
                        text: (a.textContent || '').trim().slice(0, 200),
                      }));
                    }
                    """
                )
                print("\n-- first detail-style links --")
                for l in link_dump:
                    print(f"  href={l['href']!r}")
                    print(f"    text={l['text']!r}")

                # closest ancestor (= row container) of the first link
                ancestor = await page.evaluate(
                    """
                    () => {
                      const a = document.querySelector(
                        'a[href*="/details/"], a[href*="/uu/"], a[href*="/pp/"], a[href*="/perpres/"], a[href*="/permen/"], a[href*="/perda/"]'
                      );
                      if (!a) return null;
                      let node = a;
                      for (let i = 0; i < 6; i++) {
                        if (!node.parentElement) break;
                        node = node.parentElement;
                        if (node.querySelectorAll('a').length >= 2) break;
                        if (node.tagName === 'TR' || node.tagName === 'LI' || node.tagName === 'ARTICLE') break;
                      }
                      return {
                        tag: node.tagName,
                        cls: node.className,
                        outer: node.outerHTML.slice(0, 4000),
                      };
                    }
                    """
                )
                if ancestor:
                    print(f"\n-- ancestor tag={ancestor['tag']} class={ancestor['cls']!r} --")
                    print(ancestor["outer"])

                # pagination
                pag = await page.evaluate(
                    """
                    () => {
                      const nav = document.querySelector('.pagination, ul.pagination, nav');
                      return nav ? nav.outerHTML.slice(0, 1500) : null;
                    }
                    """
                )
                if pag:
                    print("\n-- pagination HTML --")
                    print(pag)

            except Exception as e:
                print(f"ERR {type(e).__name__}: {e}")
            finally:
                await page.close()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
