"""Probe peraturan.go.id list pages to discover real DOM structure.

Designed to run inside GitHub Actions (US-region runner) where the site
is reachable. Captures:
  • selector hit counts on multiple paths
  • detail-style link samples
  • ancestor outerHTML for the first detail link
  • pagination HTML
  • a focused list of "detail-shaped" hrefs (containing year/tahun/details)
"""
from __future__ import annotations

import asyncio
import json
import re

from playwright.async_api import async_playwright

TARGETS = [
    ("home",        "https://peraturan.go.id/"),
    ("uu",          "https://peraturan.go.id/uu"),
    ("pp",          "https://peraturan.go.id/pp"),
    ("perpres",     "https://peraturan.go.id/perpres"),
    ("permen",      "https://peraturan.go.id/permen"),
    ("perda",       "https://peraturan.go.id/perda"),
    # 후보: 진짜 listing/검색은 hub path가 아닐 수 있음
    ("uu-2023",     "https://peraturan.go.id/uu/2023"),
    ("uu-tahun-23", "https://peraturan.go.id/uu/tahun/2023"),
    ("pencarian",   "https://peraturan.go.id/pencarian"),
    ("search",      "https://peraturan.go.id/search"),
    ("permenkeu",   "https://peraturan.go.id/permen/permenkeu"),
]

CANDIDATES = [
    "table tbody tr",
    "ul.list-group > li",
    ".list-group-item",
    "div.card",
    "article",
    ".result-item", ".law-item", ".peraturan-item",
    "div.row > div.col",
    'a[href*="/details/"]',
    'a[href*="/uu/"]',
    'a[href*="/pp/"]',
    'a[href*="/perpres/"]',
    'a[href*="/permen/"]',
    'a[href*="/perda/"]',
    'a[href*=".pdf"]',
]

# 진짜 detail URL 후보 패턴 — 연도 4자리, "tahun", "/details/", "no-" 등 포함
DETAIL_PAT = r"(\b\d{4}\b|tahun-?\d|-no[-_]?\d|/details/\d)"


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-probe/0.3"
            ),
            locale="id-ID",
            ignore_https_errors=True,
        )

        for label, url in TARGETS:
            print(f"\n{'=' * 70}")
            print(f"=== {label}: {url}")
            print(f"{'=' * 70}")
            page = await ctx.new_page()
            page.set_default_timeout(60_000)
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                http = resp.status if resp else "?"
                print(f"HTTP {http} | final URL = {page.url}")
                title = await page.title()
                print(f"title = {title!r}")

                try:
                    await page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass

                # 1) selector counts
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

                # 2) ALL anchors — focus on detail-shaped hrefs
                hrefs = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('a[href]'))
                            .map(a => ({
                                href: a.getAttribute('href'),
                                text: (a.textContent || '').trim().slice(0,250)
                            }))
                            .filter(o => o.href && o.href !== '#')
                    """
                )
                detail_like = [
                    h for h in hrefs
                    if h["href"] and re.search(DETAIL_PAT, h["href"], re.IGNORECASE)
                ]
                print(f"\n-- total anchors: {len(hrefs)}; detail-pattern matches: {len(detail_like)} --")
                for h in detail_like[:15]:
                    print(f"  href={h['href']!r}")
                    if h["text"]:
                        print(f"    text={h['text'][:200]!r}")

                # 3) first detail-link ancestor outerHTML
                if detail_like:
                    first_href = detail_like[0]["href"]
                    ancestor = await page.evaluate(
                        """
                        (href) => {
                          const a = document.querySelector(`a[href="${CSS.escape(href)}"]`)
                                 || document.querySelector(`a[href*="${CSS.escape(href)}"]`);
                          if (!a) return null;
                          let node = a;
                          for (let i = 0; i < 6; i++) {
                            if (!node.parentElement) break;
                            node = node.parentElement;
                            if (node.querySelectorAll('a').length >= 2) break;
                            if (['TR','LI','ARTICLE'].includes(node.tagName)) break;
                          }
                          return {
                            tag: node.tagName,
                            cls: node.className,
                            outer: node.outerHTML.slice(0, 4000),
                          };
                        }
                        """,
                        first_href,
                    )
                    if ancestor:
                        print(f"\n-- ancestor of first detail-link --")
                        print(f"   tag={ancestor['tag']} class={ancestor['cls']!r}")
                        print(ancestor["outer"])

                # 4) pagination
                pag = await page.evaluate(
                    """
                    () => {
                      const nav = document.querySelector('.pagination, ul.pagination');
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
