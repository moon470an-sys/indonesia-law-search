"""Deep list-URL discovery for sites that returned no/partial detail
anchors on /peraturan or /home.

For each host, try a wider list of candidate paths with multiple page
params. Score by max unique-detail-count at any URL. Dump the best HTML
for inspection.
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
    # Phase 1B-8 partial / failed
    "atrbpn.go.id", "kemendag.go.id", "kejaksaan.go.id", "bkpm.go.id",
    # Tier 1+2 still-empty
    "dephub.go.id", "kkp.go.id", "pu.go.id", "pom.go.id", "lkpp.go.id",
    "bps.go.id", "lps.go.id", "lan.go.id", "kemlu.go.id",
    "kemenkopmk.go.id", "bp2mi.go.id", "bkkbn.go.id", "setneg.go.id",
    "komisiyudisial.go.id", "bnn.go.id", "bpkp.go.id",
]

# Per-host candidate paths (best-guess based on JDIH platform patterns)
DEEP_PATHS = [
    "/peraturan", "/peraturan?hal=1", "/peraturan?halaman=1", "/peraturan?page=1",
    "/produk-hukum", "/produk-hukum/index", "/produk-hukum?page=1",
    "/dokumen", "/dokumen/peraturan", "/dokumen/peraturan?page=1", "/dokumen-hukum",
    "/regulation", "/regulation?page=1", "/regulation/year",
    "/regulasi", "/peraturan-perundang-undangan",
    "/peraturan/klaster", "/peraturan/tipe", "/peraturan/index",
    "/public/dokumen-hukum", "/cari_peraturan", "/cari_peraturan?page=1",
    "/id/document", "/id/peraturan", "/id/dokumen",
    "/index.php?p=show_detail",
    "/wirata.html", "/wirata.html?act=Cari",
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
    re.compile(r"/produk-hukum/detail\?id=\d+", re.I),
    re.compile(r"/wirata\.html\?id=", re.I),
]


async def fetch(client, url):
    try:
        r = await client.get(url, timeout=15.0, follow_redirects=True)
        return r.status_code, r.text
    except Exception:
        return None, None


async def probe_host(client, host):
    base = f"https://jdih.{host}"
    out = {"host": host, "best": None}
    best_score = 0
    for p in DEEP_PATHS:
        url = base + p
        status, html = await fetch(client, url)
        if not html or status != 200 or len(html) < 5000:
            continue
        urls_in_html = set(re.findall(r'href=["\']([^"\']+)["\']', html))
        details = set()
        for u in urls_in_html:
            for rx in DETAIL_RX:
                if rx.search(u):
                    details.add(u)
                    break
        score = len(details)
        if score > best_score:
            best_score = score
            entry = {"url": url, "status": status, "len": len(html), "detail_count": score,
                     "detail_sample": list(details)[:6]}
            out["best"] = entry
            Path("data/probe").mkdir(parents=True, exist_ok=True)
            Path(f"data/probe/deep_{host}.html").write_text(html[:600_000], encoding="utf-8")
    return out


async def main():
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        async def guarded(h):
            async with sem:
                return await probe_host(client, h)
        results = await asyncio.gather(*(guarded(h) for h in HOSTS))

    Path("data/probe_deeper.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    for r in results:
        host = r["host"]
        best = r.get("best")
        if best:
            print(f"  {host:<28} {best['url'][:75]:<75}  detail={best['detail_count']}")
        else:
            print(f"  {host:<28} (no useful URL found)")


if __name__ == "__main__":
    asyncio.run(main())
