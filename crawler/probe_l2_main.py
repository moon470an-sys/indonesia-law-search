"""Detailed DOM probe for the 10 L2-main sites discovered by probe_layers.

For each site: fetch the list page with Playwright, dump full HTML, then
extract candidate selectors:
  - all anchors whose href looks like a regulation detail page
  - all anchors whose text/href contains pagination keywords (page=, /page/, ?p=)
  - any visible "total"/"hasil" counters
  - top-3 most-common ancestor class chains for detail anchors (likely the
    item-card selector)

Output: data/probe_l2.json + data/probe/l2_<host>.html for each site.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

# (host, list_url) — the URL probe_layers found 200 OK on the main domain
TARGETS = [
    ("ojk.go.id",            "https://ojk.go.id/id/regulasi"),
    ("kemenkeu.go.id",       "https://kemenkeu.go.id/peraturan"),
    ("pertanian.go.id",      "https://pertanian.go.id/peraturan"),
    ("kemnaker.go.id",       "https://kemnaker.go.id/peraturan"),
    ("kemkes.go.id",         "https://kemkes.go.id/id/regulasi"),
    ("kemenpppa.go.id",      "https://kemenpppa.go.id/id/regulasi"),
    ("kemhan.go.id",         "https://kemhan.go.id/peraturan"),
    ("lps.go.id",            "https://lps.go.id/regulasi"),
    ("lan.go.id",            "https://lan.go.id/peraturan"),
    ("mahkamahagung.go.id",  "https://mahkamahagung.go.id/peraturan"),
]

DETAIL_PATTERNS = [
    r"/peraturan/[^/?#]+/[^/?#]+",
    r"/peraturan/detail",
    r"/regulasi/[^/?#]+/[^/?#]+",
    r"/regulation/",
    r"/dokumen/[^/?#]+/[^/?#]+",
    r"/produk-hukum",
    r"detail|view\?id|index\.php\?p",
]

PAGINATION_HINTS = [r"\?page=\d", r"/page/\d", r"\?p=\d", r"\?halaman=\d", r"&page=\d", r"&offset=\d"]
TOTAL_PATTERNS = [
    r"(\d+(?:[\.,]\d{3})*)\s*(?:hasil|results?|dokumen|peraturan|data|regulasi|item)",
    r"dari\s+(\d+(?:[\.,]\d{3})*)",
    r"total[^0-9]{0,20}(\d+(?:[\.,]\d{3})*)",
    r"(\d+(?:[\.,]\d{3})*)\s+(?:peraturan|regulasi)\s+ditemukan",
]


async def probe_site(ctx, host: str, url: str) -> dict:
    page = await ctx.new_page()
    page.set_default_timeout(45_000)
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(4000)  # let JS hydrate
        html = await page.content()
        title = await page.title()

        # Extract all internal anchors
        anchors = await page.evaluate(
            f"""() => Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({{
                    h: a.href,
                    t: (a.textContent || '').trim().slice(0, 100),
                    cls: a.className || '',
                    parent_cls: (a.parentElement?.className || '') + ' / ' + (a.parentElement?.parentElement?.className || ''),
                }}))
                .filter(x => x.h.includes('{host}') && x.h !== '{url}')"""
        )

        # Score anchors as detail vs pagination vs other
        detail_anchors = [a for a in anchors
                          if any(re.search(p, a["h"], re.IGNORECASE) for p in DETAIL_PATTERNS)]
        pagination_anchors = [a for a in anchors
                              if any(re.search(p, a["h"], re.IGNORECASE) for p in PAGINATION_HINTS)]

        # Count parent_cls of detail anchors → guess at the card selector
        parent_class_counter = Counter(a["parent_cls"] for a in detail_anchors)

        # Search for total/count strings
        totals_found = []
        for p in TOTAL_PATTERNS:
            for m in re.finditer(p, html, re.IGNORECASE):
                totals_found.append(m.group(0)[:60])

        Path("data/probe").mkdir(parents=True, exist_ok=True)
        if len(html) > 5000:
            Path(f"data/probe/l2_{host}.html").write_text(html[:800_000], encoding="utf-8")

        return {
            "host": host, "url": url, "status": resp.status if resp else None,
            "final": page.url, "title": title, "len": len(html),
            "anchors_total": len(anchors),
            "detail_count": len(detail_anchors),
            "detail_sample": [a["h"] for a in detail_anchors[:6]],
            "detail_parent_classes_top3": parent_class_counter.most_common(3),
            "pagination_count": len(pagination_anchors),
            "pagination_sample": [a["h"] for a in pagination_anchors[:5]],
            "totals_found": totals_found[:5],
        }
    except Exception as e:
        return {"host": host, "url": url, "error": str(e)[:200]}
    finally:
        await page.close()


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="id-ID")
        sem = asyncio.Semaphore(4)

        async def guarded(host, url):
            async with sem:
                try:
                    return await asyncio.wait_for(probe_site(ctx, host, url), timeout=120)
                except asyncio.TimeoutError:
                    return {"host": host, "url": url, "error": "host-timeout-120s"}

        results = await asyncio.gather(*(guarded(h, u) for h, u in TARGETS))
        await browser.close()

    Path("data/probe_l2.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    print("=== L2-main DOM probe ===")
    for r in results:
        if "error" in r:
            print(f"\n[{r['host']}] ERROR: {r['error']}")
            continue
        print(f"\n[{r['host']}] status={r['status']} title={r['title'][:60]}")
        print(f"  url: {r['url']} → {r['final']}")
        print(f"  detail_anchors={r['detail_count']}  pagination={r['pagination_count']}  totals={r['totals_found']}")
        if r["detail_sample"]:
            print(f"  detail samples:")
            for u in r["detail_sample"]:
                print(f"    {u}")
        if r["pagination_sample"]:
            print(f"  pagination samples: {r['pagination_sample']}")
        if r["detail_parent_classes_top3"]:
            print(f"  parent_class top3:")
            for cls, n in r["detail_parent_classes_top3"]:
                print(f"    [{n}x]  {cls[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
