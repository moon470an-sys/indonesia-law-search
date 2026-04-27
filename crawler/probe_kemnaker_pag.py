"""Probe kemnaker pagination conventions."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"

URLS = [
    "https://jdih.kemnaker.go.id/peraturan?tahun=2025",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2025&page=2",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2020",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2020&page=2",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2010",
    "https://jdih.kemnaker.go.id/peraturan?tahun=1990",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2024&sort=terbaru&page=2",
    "https://jdih.kemnaker.go.id/peraturan?tahun=2024&sort=terbaru&page=3",
    # search keyword
    "https://jdih.kemnaker.go.id/peraturan?keyword=a",
    "https://jdih.kemnaker.go.id/peraturan?keyword=2024",
    # tag filter
    "https://jdih.kemnaker.go.id/peraturan?tag%5B%5D=hukum",
    # status filter
    "https://jdih.kemnaker.go.id/peraturan?status=Berlaku",
    "https://jdih.kemnaker.go.id/peraturan?status=Berlaku&page=2",
]


async def main() -> None:
    out = []
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        for url in URLS:
            try:
                r = await client.get(url, timeout=15.0, follow_redirects=True)
                ids = re.findall(r"/peraturan/detail/(\d+)/", r.text)
                # Find the count in the page text "X hasil" or "X dokumen"
                count = re.findall(r"(\d+)\s*hasil|(\d+)\s*Dokumen", r.text, re.IGNORECASE)
                count_str = "-"
                if count:
                    flat = [v for tup in count for v in tup if v]
                    if flat: count_str = ",".join(flat[:3])
                unique = list(dict.fromkeys(ids))[:6]
                out.append({"url": url, "status": r.status_code, "len": len(r.content),
                            "ids_count": len(ids), "unique_first6": unique, "page_count": count_str})
            except Exception as e:
                out.append({"url": url, "error": str(e)[:100]})
    Path("data/probe_kemnaker_pag.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in out:
        if "error" in r:
            print(f"  ERR  {r['url'][:80]}: {r['error']}")
        else:
            print(f"  {r['status']} ids={r['ids_count']:>3} uniq={r['unique_first6']} hasil={r['page_count']}  {r['url']}")


if __name__ == "__main__":
    asyncio.run(main())
