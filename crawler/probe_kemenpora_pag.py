"""Probe kemenpora pagination — discover the actual page param.

The default ?page=N is ignored; the same 5 records return on every page.
Try alternative conventions and check the HTML for hidden form fields,
AJAX endpoints, or pagination URLs.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

# Variations to try
URLS = [
    "https://jdih.kemenpora.go.id/peraturan",
    "https://jdih.kemenpora.go.id/peraturan?page=2",
    "https://jdih.kemenpora.go.id/peraturan?halaman=2",
    "https://jdih.kemenpora.go.id/peraturan?p=2",
    "https://jdih.kemenpora.go.id/peraturan?offset=5",
    "https://jdih.kemenpora.go.id/peraturan?start=5",
    "https://jdih.kemenpora.go.id/peraturan?per_page=100",
    "https://jdih.kemenpora.go.id/peraturan?limit=100",
    "https://jdih.kemenpora.go.id/peraturan?show=100",
    "https://jdih.kemenpora.go.id/peraturan/2",  # path-based
    "https://jdih.kemenpora.go.id/peraturan/page/2",
    "https://jdih.kemenpora.go.id/peraturan/index/2",
]


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    out = []
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID,en;q=0.5"}) as client:
        for url in URLS:
            try:
                r = await client.get(url, timeout=20.0, follow_redirects=True)
                # Count detail links
                detail_links = re.findall(r'/peraturan/detail/(\d+)/', r.text)
                # Find unique IDs (first 10)
                unique_ids = list(dict.fromkeys(detail_links))[:8]
                out.append({
                    "url": url, "status": r.status_code, "len": len(r.content),
                    "detail_count": len(detail_links),
                    "unique_ids": unique_ids,
                })
            except Exception as e:
                out.append({"url": url, "error": str(e)[:120]})

        # Also fetch the base page and dump it for AJAX endpoint discovery
        try:
            r = await client.get("https://jdih.kemenpora.go.id/peraturan", timeout=20.0)
            Path("data/probe/kemenpora_full.html").write_text(r.text[:600_000], encoding="utf-8")
            # Look for JS/AJAX endpoints
            ajax_patterns = re.findall(
                r'(?:fetch|axios\.get|xhr\.open|\$\.get|\$\.ajax)\s*\(\s*["\']([^"\']+)["\']',
                r.text)
            api_paths = re.findall(r'(/api/[^"\'\s]+)', r.text)
            all_endpoints = list(set(ajax_patterns + api_paths))[:20]
            print(f"\nAJAX/API endpoints found: {all_endpoints}")
            # Check for hidden form fields on the listing
            forms = re.findall(r'<form[^>]*action=["\']([^"\']+)["\'][^>]*>', r.text)
            print(f"Forms: {forms[:5]}")
        except Exception as e:
            print(f"base fetch error: {e}")

    Path("data/probe_kemenpora_pag.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print("\n=== Pagination probe ===")
    for r in out:
        if "error" in r:
            print(f"  ERR  {r['url']}: {r['error']}")
        else:
            print(f"  {r['status']} det={r['detail_count']:>3} uniq={r['unique_ids']}  {r['url']}")


if __name__ == "__main__":
    asyncio.run(main())
