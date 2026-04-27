"""Probe bmkg /api/dokumen pagination.

The default ?page=N&perPage=K is ignored. dataCount=1269 but only 5 returned.
Try alternative param conventions and discover any related endpoints.
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

URLS = [
    # baseline
    "https://jdih.bmkg.go.id/api/dokumen",
    # different page/size params
    "https://jdih.bmkg.go.id/api/dokumen?page=2",
    "https://jdih.bmkg.go.id/api/dokumen?page=2&perPage=10",
    "https://jdih.bmkg.go.id/api/dokumen?page=2&per_page=10",
    "https://jdih.bmkg.go.id/api/dokumen?page=2&size=10",
    "https://jdih.bmkg.go.id/api/dokumen?page=2&take=10",
    "https://jdih.bmkg.go.id/api/dokumen?offset=5&limit=10",
    "https://jdih.bmkg.go.id/api/dokumen?skip=5&take=10",
    "https://jdih.bmkg.go.id/api/dokumen?start=5&length=10",
    "https://jdih.bmkg.go.id/api/dokumen?p=2",
    "https://jdih.bmkg.go.id/api/dokumen?halaman=2",
    # alternate endpoints (JDIHN 2.0 conventions)
    "https://jdih.bmkg.go.id/api/v1/dokumen",
    "https://jdih.bmkg.go.id/api/v2/dokumen",
    "https://jdih.bmkg.go.id/api/dokumen/list",
    "https://jdih.bmkg.go.id/api/peraturan",
    "https://jdih.bmkg.go.id/api/v1/peraturan",
    "https://jdih.bmkg.go.id/api/v1/dokumenhukum",
    "https://jdih.bmkg.go.id/api/dokumenhukum",
    # Frontend route (probably proxies to API with specific params)
    "https://jdih.bmkg.go.id/peraturan",
    "https://jdih.bmkg.go.id/peraturan?page=2",
]


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    out = []
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        for url in URLS:
            try:
                r = await client.get(url, timeout=15.0, follow_redirects=True)
                ctype = r.headers.get("content-type", "")
                rec = {"url": url, "status": r.status_code, "ctype": ctype, "len": len(r.content)}
                if "json" in ctype.lower():
                    try:
                        obj = r.json()
                        if isinstance(obj, dict):
                            data = obj.get("data") or []
                            rec["dataCount"] = obj.get("dataCount")
                            rec["data_len"] = len(data) if isinstance(data, list) else None
                            if isinstance(data, list) and data:
                                rec["sample_ids"] = [d.get("id") for d in data[:8] if isinstance(d, dict)]
                    except Exception as e:
                        rec["parse_error"] = str(e)[:100]
                else:
                    title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
                    rec["title"] = (title_m.group(1).strip()[:80] if title_m else None)
                out.append(rec)
            except Exception as e:
                out.append({"url": url, "error": str(e)[:100]})

    Path("data/probe_bmkg_pag.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print("=== bmkg pagination probe ===")
    for r in out:
        if "error" in r:
            print(f"  ERR  {r['url']}: {r['error'][:60]}")
        else:
            ext = ""
            if r.get("dataCount") is not None:
                ext = f"  dataCount={r['dataCount']}  data_len={r['data_len']}  ids={r.get('sample_ids')}"
            elif r.get("title"):
                ext = f"  title={r['title']}"
            print(f"  {r['status']}  {r['ctype'][:25]:<25}  {r['url']}{ext}")


if __name__ == "__main__":
    asyncio.run(main())
