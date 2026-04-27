"""Discover the actual list page URL and DOM pattern for the 22 newly-
reachable jdih.* subdomains.

For each host, try a list of candidate list-page URLs (peraturan first,
then /dokumen-hukum, /produk-hukum, etc.). For each URL that returns
useful HTML (>5KB and at least 5 detail-link anchors), record the
selector hints (parent class chains, total count, pagination links).

Output: data/probe_batch_dom.json + data/probe/batch_<host>.html
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from pathlib import Path

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"

HOSTS = [
    # Tier 1
    "dephub.go.id", "kkp.go.id", "pu.go.id", "bkpm.go.id", "atrbpn.go.id",
    "kemendag.go.id",
    # Tier 2
    "pom.go.id", "lkpp.go.id", "bps.go.id", "bpkp.go.id",
    # Others
    "lps.go.id", "lan.go.id", "kpu.go.id", "komisiyudisial.go.id",
    "kemenkopmk.go.id", "kemlu.go.id", "kemenpora.go.id", "bnn.go.id",
    "bp2mi.go.id", "bkkbn.go.id", "kejaksaan.go.id", "setneg.go.id",
]

PATHS = [
    "/peraturan", "/dokumen/peraturan", "/dokumen", "/dokumen-hukum",
    "/produk-hukum", "/regulasi", "/peraturan-perundang-undangan",
    "/dokumen-hukum/produk-hukum", "/regulation",
    "/perundangan", "/peraturan?hal=1", "/peraturan?halaman=1",
    "/", "/home",
]


DETAIL_RX = [
    re.compile(r"/peraturan/detail/\d+", re.I),
    re.compile(r"/peraturan/[\w\-]{8,}", re.I),
    re.compile(r"/dokumen[^/]*/[\w\-]{8,}", re.I),
    re.compile(r"/document[s]?/[\w\-]{8,}", re.I),
    re.compile(r"/regulation/[\w\-]{8,}", re.I),
    re.compile(r"/regulasi/[\w\-]{8,}", re.I),
    re.compile(r"/produk-hukum/[\w\-]+", re.I),
    re.compile(r"/dokumen-hukum/[\w\-/]+", re.I),
    re.compile(r"/index\.php\?p=show_detail", re.I),
    re.compile(r"/view\?id=\d+", re.I),
]
PAGINATION_RX = re.compile(r"[?&](page|p|halaman|hal|offset|skip)=\d+|class=[\"\']page-link", re.I)
TOTAL_RX = [
    re.compile(r"(\d{2,}(?:[\.,]\d{3})*)\s*(?:hasil|results?|dokumen|peraturan|data|regulasi)", re.I),
    re.compile(r"dari\s+(\d{2,}(?:[\.,]\d{3})*)", re.I),
]


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str] | None:
    for attempt in range(2):
        try:
            r = await client.get(url, timeout=20.0, follow_redirects=True)
            return r.status_code, r.text
        except Exception:
            await asyncio.sleep(1 + attempt)
    return None


async def probe_host(client: httpx.AsyncClient, host: str) -> dict:
    base = f"https://jdih.{host}"
    out = {"host": host, "tries": []}
    for p in PATHS:
        url = base + p
        result = await fetch(client, url)
        if not result:
            out["tries"].append({"url": url, "error": "fetch-failed"})
            continue
        status, html = result
        # Count detail anchors
        urls_in_html = set(re.findall(r'href=["\']([^"\']+)["\']', html))
        details = set()
        for u in urls_in_html:
            for rx in DETAIL_RX:
                if rx.search(u):
                    details.add(u)
                    break
        # Pagination signals
        pag = bool(PAGINATION_RX.search(html))
        # Total count
        totals = []
        for rx in TOTAL_RX:
            for m in rx.finditer(html):
                totals.append(m.group(0)[:50])
        entry = {"url": url, "status": status, "len": len(html),
                 "detail_count": len(details),
                 "pagination_signal": pag,
                 "totals_found": totals[:3],
                 "detail_sample": list(details)[:5]}
        out["tries"].append(entry)
        # Pick best
        if status == 200 and len(html) > 5000 and len(details) >= 5:
            best = out.get("best") or {}
            if (entry["detail_count"] > best.get("detail_count", 0)) or \
               (entry["detail_count"] == best.get("detail_count", 0) and entry["len"] > best.get("len", 0)):
                Path("data/probe").mkdir(parents=True, exist_ok=True)
                Path(f"data/probe/batch_{host}.html").write_text(html[:600_000], encoding="utf-8")
                out["best"] = entry
    return out


async def main() -> None:
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        async def guarded(h):
            async with sem:
                return await probe_host(client, h)
        results = await asyncio.gather(*(guarded(h) for h in HOSTS))

    Path("data/probe_batch_dom.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    print(f"{'Host':<26} {'BestURL':<70} {'Detail':>6} {'Pag':>4} {'Total':<25}")
    for r in results:
        host = r["host"]
        best = r.get("best")
        if best:
            print(f"  {host:<26} {best['url'][:68]:<70} {best['detail_count']:>6} {('Y' if best['pagination_signal'] else 'n'):>4} {','.join(best['totals_found'])[:25]}")
        else:
            # Show best of partial tries
            valid = [t for t in r["tries"] if isinstance(t, dict) and "error" not in t]
            if valid:
                best_partial = max(valid, key=lambda x: x.get("detail_count", 0))
                print(f"  {host:<26} (no good list) tried {len(valid)} URLs, max_details={best_partial['detail_count']}")
            else:
                print(f"  {host:<26} all-failed")


if __name__ == "__main__":
    asyncio.run(main())
