"""Try multiple strategies to reach jdih.kemnaker.go.id from Actions IPs.

Previous attempts (httpx + Playwright) get ERR_CONNECTION_CLOSED. Try:
  1. curl_cffi with Chrome131 TLS fingerprint (defeats some IP+TLS blocks)
  2. Different User-Agent strings
  3. JDIH-style API endpoints (/api/peraturan, /api/v1/dokumen, /api/produk-hukum)
  4. Wayback Machine CDX index (count of available snapshots)
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)
UA_FIREFOX = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

TARGETS_HTML = [
    ("https://jdih.kemnaker.go.id/peraturan", UA_BROWSER, "browser-html"),
    ("https://jdih.kemnaker.go.id/peraturan", UA_FIREFOX, "firefox-html"),
    ("https://jdih.kemnaker.go.id/peraturan", UA_MOBILE, "mobile-html"),
    ("https://jdih.kemnaker.go.id/", UA_BROWSER, "root-html"),
]

API_TARGETS = [
    "https://jdih.kemnaker.go.id/api/peraturan",
    "https://jdih.kemnaker.go.id/api/v1/peraturan",
    "https://jdih.kemnaker.go.id/api/v1/dokumen",
    "https://jdih.kemnaker.go.id/api/dokumen",
    "https://jdih.kemnaker.go.id/api/produk-hukum",
    "https://jdih.kemnaker.go.id/api/v1/produk-hukum",
    "https://jdih.kemnaker.go.id/api/list",
]


async def httpx_try(label: str, url: str, ua: str) -> dict:
    try:
        async with httpx.AsyncClient(headers={"User-Agent": ua, "Accept-Language": "id-ID,en;q=0.5"}) as client:
            r = await client.get(url, timeout=20.0, follow_redirects=True)
            return {"label": label, "url": url, "ua": ua[:30], "engine": "httpx",
                    "status": r.status_code, "len": len(r.content),
                    "ctype": r.headers.get("content-type", "")[:40]}
    except Exception as e:
        return {"label": label, "url": url, "ua": ua[:30], "engine": "httpx",
                "error": str(e)[:100]}


async def curl_cffi_try(label: str, url: str, ua: str = UA_BROWSER) -> dict:
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError as e:
        return {"label": label, "url": url, "engine": "curl_cffi", "error": f"not installed: {e}"}
    try:
        async with AsyncSession(impersonate="chrome131") as s:
            r = await s.get(url, timeout=25)
            ctype = r.headers.get("content-type", "")
            return {"label": label, "url": url, "engine": "curl_cffi",
                    "status": r.status_code, "len": len(r.content),
                    "ctype": ctype[:40]}
    except Exception as e:
        return {"label": label, "url": url, "engine": "curl_cffi", "error": str(e)[:120]}


async def wayback_count(host: str) -> dict:
    """How many archived snapshots exist for jdih.<host>/* on web.archive.org?"""
    url = (
        f"https://web.archive.org/cdx/search/cdx?url=jdih.{host}/*"
        "&output=json&limit=20000&filter=statuscode:200&from=20200101"
        "&fl=timestamp,original&collapse=urlkey"
    )
    try:
        async with httpx.AsyncClient(headers={"User-Agent": UA_BROWSER}) as client:
            r = await client.get(url, timeout=60.0)
            if r.status_code == 200 and r.text.strip():
                rows = r.json()
                if isinstance(rows, list) and len(rows) > 1:
                    return {"engine": "wayback-cdx", "host": host,
                            "snapshots": len(rows) - 1,
                            "newest": rows[1] if len(rows) > 1 else None,
                            "oldest": rows[-1] if len(rows) > 1 else None}
            return {"engine": "wayback-cdx", "host": host, "status": r.status_code, "body_head": r.text[:120]}
    except Exception as e:
        return {"engine": "wayback-cdx", "host": host, "error": str(e)[:120]}


async def main() -> None:
    out: list[dict] = []
    for url, ua, label in TARGETS_HTML:
        out.append(await httpx_try(label, url, ua))
        out.append(await curl_cffi_try(label, url, ua))
    for u in API_TARGETS:
        out.append(await httpx_try("api", u, UA_BROWSER))
        out.append(await curl_cffi_try("api", u, UA_BROWSER))
    out.append(await wayback_count("kemnaker.go.id"))

    Path("data").mkdir(exist_ok=True)
    Path("data/probe_kemnaker_bypass.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print("=== kemnaker bypass probe ===")
    for r in out:
        if "error" in r:
            print(f"  ERR  {r.get('engine','?')[:10]:<10} {r.get('url',r.get('host',''))[:80]}: {r['error'][:60]}")
        else:
            extra = ""
            if r.get("snapshots") is not None:
                extra = f"  snapshots={r['snapshots']} newest={r.get('newest')} oldest={r.get('oldest')}"
            print(f"  {r.get('status','?'):>3}  {r.get('engine','?'):<10} {r.get('url',r.get('host',''))[:90]}  len={r.get('len','?')} ct={r.get('ctype','')}{extra}")


if __name__ == "__main__":
    asyncio.run(main())
