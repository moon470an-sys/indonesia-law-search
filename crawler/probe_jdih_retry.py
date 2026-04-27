"""Retry-tolerant probe of jdih.* subdomain list pages.

The original probe_jdih_pw classified some sites as "unknown" because their
list page returned 200 OK but did not match the ESDM card-template. The
HTML on those pages still contains usable detail links — we just need to
identify the per-site selector. This probe revisits 11 viable list URLs
with 3 retries and a 90s timeout, then dumps HTML + extracts:
  - all anchors that look like detail URLs (slug or id pattern)
  - the most-common parent-class chain for those anchors
  - any pagination param patterns
  - visible total/result counters
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

TARGETS = [
    # tier 1 / tier 2 priority (Korean business impact)
    ("kemnaker",      "https://jdih.kemnaker.go.id/peraturan",          "노동부"),
    ("kemendag",      "https://jdih.kemendag.go.id/peraturan",          "무역부"),
    ("pertanian",     "https://jdih.pertanian.go.id/peraturan",         "농업부"),
    ("kemhan",        "https://jdih.kemhan.go.id/documents/regulations", "국방부"),
    ("dephub",        "https://jdih.dephub.go.id/peraturan",            "교통부"),
    ("kpu",           "https://jdih.kpu.go.id/peraturan-kpu",           "선거관리위"),
    ("brin",          "https://jdih.brin.go.id/dokumen-hukum/peraturan", "연구혁신청"),
    ("bnpt",          "https://jdih.bnpt.go.id/id/peraturan-perundang-undangan", "테러방지청"),
    ("bp2mi",         "https://jdih.bp2mi.go.id/index.php/content/peraturan_terbaru", "이주노동자청"),
    ("kemenpora",     "https://jdih.kemenpora.go.id/peraturan",         "청소년체육부"),
    ("pkp",           "https://jdih.pkp.go.id/produk-hukum",            "주거단지부"),
    # derived from detail URLs in earlier probe
    ("kemkes",        "https://jdih.kemkes.go.id/documents",            "보건부"),
    ("kemenpppa",     "https://jdih.kemenpppa.go.id/dokumen-hukum/produk-hukum", "여성가족부"),
    ("kemenag",       "https://jdih.kemenag.go.id/regulation",          "종교부"),
]

DETAIL_RX = [
    re.compile(r"/peraturan/detail/\d+", re.IGNORECASE),
    re.compile(r"/peraturan/[\w\-]+/[\w\-]+", re.IGNORECASE),
    re.compile(r"/dokumen[^/]*/[^/]+/[\w\-]+", re.IGNORECASE),
    re.compile(r"/document[s]?/[\w\-]+", re.IGNORECASE),
    re.compile(r"/regulation/[\w\-]+", re.IGNORECASE),
    re.compile(r"/produk-hukum/[\w\-]+", re.IGNORECASE),
    re.compile(r"/index\.php\?p=show_detail&id=\d+", re.IGNORECASE),
    re.compile(r"/view\?id=\d+", re.IGNORECASE),
]
PAGINATION_RX = re.compile(r"[?&](page|p|halaman|offset)=\d+", re.IGNORECASE)
TOTAL_RX = [
    re.compile(r"(\d{2,}(?:[\.,]\d{3})*)\s*(?:hasil|results?|dokumen|peraturan|data|regulasi|item)", re.IGNORECASE),
    re.compile(r"dari\s+(\d{2,}(?:[\.,]\d{3})*)", re.IGNORECASE),
]


async def probe_one(ctx, key: str, url: str, name_ko: str) -> dict:
    page = await ctx.new_page()
    page.set_default_timeout(90_000)
    last_err = None
    for attempt in range(3):
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(5000)
            html = await page.content()
            title = await page.title()

            anchors = await page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({h: a.href, t: (a.textContent||'').trim().slice(0,100),
                                cls: a.className||'', pcls: a.parentElement?.className||'',
                                ppcls: a.parentElement?.parentElement?.className||''}))"""
            )
            details = []
            for a in anchors:
                if any(rx.search(a["h"]) for rx in DETAIL_RX):
                    details.append(a)
            paginations = [a["h"] for a in anchors if PAGINATION_RX.search(a["h"])]

            totals = []
            for rx in TOTAL_RX:
                for m in rx.finditer(html):
                    totals.append(m.group(0)[:60])

            parent_cls_counter = Counter(a["pcls"] for a in details if a["pcls"])
            grand_cls_counter = Counter(a["ppcls"] for a in details if a["ppcls"])

            Path("data/probe").mkdir(parents=True, exist_ok=True)
            if len(html) > 5000:
                Path(f"data/probe/jdih_{key}.html").write_text(html[:800_000], encoding="utf-8")

            return {
                "key": key, "name_ko": name_ko, "url": url,
                "status": resp.status if resp else None, "final": page.url,
                "title": title, "len": len(html), "attempt": attempt + 1,
                "detail_count": len(details),
                "detail_sample": [a["h"] for a in details[:6]],
                "detail_text_sample": [a["t"] for a in details[:3]],
                "parent_cls_top3": parent_cls_counter.most_common(3),
                "grandparent_cls_top3": grand_cls_counter.most_common(3),
                "pagination_count": len(paginations),
                "pagination_sample": list(set(paginations))[:5],
                "totals_found": totals[:5],
            }
        except Exception as e:
            last_err = str(e)[:200]
            await asyncio.sleep(3)
    await page.close()
    return {"key": key, "url": url, "error": last_err, "attempt": 3}


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="id-ID")
        sem = asyncio.Semaphore(4)

        async def guarded(key, url, name_ko):
            async with sem:
                return await probe_one(ctx, key, url, name_ko)

        results = await asyncio.gather(*(guarded(k, u, n) for k, u, n in TARGETS))
        await browser.close()

    Path("data/probe_jdih_retry.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    print("=== jdih.* retry probe ===")
    viable = []
    for r in results:
        print()
        if r.get("error"):
            print(f"[{r['key']}] ERROR after {r.get('attempt',0)} attempts: {r['error']}")
            continue
        flag = "✅" if r["detail_count"] >= 5 else ("⚠️" if r["detail_count"] > 0 else "❌")
        print(f"{flag} [{r['key']}] {r.get('name_ko','')} status={r['status']} len={r['len']} attempt={r['attempt']}")
        print(f"   {r['url']} → {r['final']}")
        print(f"   detail={r['detail_count']}  pagination={r['pagination_count']}  totals={r['totals_found']}")
        if r["detail_sample"]:
            for u in r["detail_sample"][:3]:
                print(f"     {u}")
        if r["parent_cls_top3"]:
            for cls, n in r["parent_cls_top3"][:1]:
                print(f"     parent_cls top: [{n}x] {cls[:90]}")
        if r["detail_count"] >= 5:
            viable.append(r["key"])

    print(f"\n=== VIABLE for scraper-build: {len(viable)} ===")
    for k in viable:
        print(f"  {k}")


if __name__ == "__main__":
    asyncio.run(main())
