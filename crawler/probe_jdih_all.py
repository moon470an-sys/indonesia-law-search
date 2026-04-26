"""Probe 65+ JDIH sites for template signature.

Output: data/probe_jdih_all.json with classification:
  - standard:   uses .card-body.no-padding-tb cards + "Ditampilkan ... dari N Data"
  - unknown:    HTTP 200 but signature missing (custom template)
  - error:      timeout/refused/HTTP error

Run: python -m crawler.probe_jdih_all
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx

SITES = [
    "polkam.go.id", "ekon.go.id", "kemenkopmk.go.id", "maritim.go.id",
    "kemenkopangan.go.id", "kemenkoipk.go.id", "kemenkopolhukam.go.id",
    "dephub.go.id", "kkp.go.id", "menlhk.go.id", "bkpm.go.id",
    "kemenkeu.go.id", "bappenas.go.id", "kemenkopukm.go.id",
    "kemendag.go.id", "kemenperin.go.id", "pertanian.go.id",
    "kemnaker.go.id", "bp2mi.go.id", "kemenkumham.go.id",
    "imigrasi.go.id", "pu.go.id", "pkp.go.id", "atrbpn.go.id",
    "kominfo.go.id", "kemkes.go.id", "kemensos.go.id", "bkkbn.go.id",
    "kemenpppa.go.id", "kemdikbud.go.id", "kemenag.go.id",
    "kemenpora.go.id", "kemendesa.go.id", "kemlu.go.id",
    "kemendagri.go.id", "kemhan.go.id", "menpan.go.id",
    "setneg.go.id", "setkab.go.id", "kemenparekraf.go.id",
    "ojk.go.id", "lps.go.id", "bps.go.id", "pom.go.id",
    "bnpt.go.id", "bnn.go.id", "bpkp.go.id", "anri.go.id",
    "lan.go.id", "brin.go.id", "bmkg.go.id", "bsn.go.id",
    "lkpp.go.id", "kpk.go.id", "komnasham.go.id", "kpu.go.id",
    "mahkamahagung.go.id", "komisiyudisial.go.id",
    "kejaksaan.go.id", "polri.go.id", "tni.mil.id", "bin.go.id",
    "bssn.go.id", "bphmigas.go.id",
    # special TLDs
    "mkri.id",
]
# Already seeded earlier in this project
ALREADY_DONE = {"esdm.go.id"}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-probe/1.0"
)
TOTAL_RE = re.compile(r"dari\s+(\d+)\s+Data", re.IGNORECASE)


async def probe_one(client: httpx.AsyncClient, host: str) -> dict:
    base = f"https://jdih.{host}"
    url = f"{base}/dokumen/peraturan"
    try:
        r = await client.get(url, follow_redirects=True, timeout=20.0)
    except Exception as e:
        return {"host": host, "category": "error", "detail": str(e)[:200]}
    if r.status_code != 200:
        # try home page as fallback
        try:
            r2 = await client.get(base, follow_redirects=True, timeout=15.0)
            return {
                "host": host, "category": "error",
                "detail": f"peraturan {r.status_code}, home {r2.status_code}",
                "final_url": str(r.url), "home_final_url": str(r2.url),
            }
        except Exception as e:
            return {"host": host, "category": "error", "detail": f"peraturan {r.status_code}; home: {e}"}
    text = r.text
    has_card = "card-body" in text and "no-padding-tb" in text
    m = TOTAL_RE.search(text)
    total = int(m.group(1)) if m else None
    if has_card and total is not None:
        category = "standard"
    elif has_card or total is not None:
        category = "partial"
    else:
        category = "unknown"
    return {
        "host": host,
        "category": category,
        "total": total,
        "final_url": str(r.url),
        "size": len(text),
        "has_card": has_card,
    }


async def main() -> None:
    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        async def guarded(host: str) -> dict:
            async with sem:
                return await probe_one(client, host)
        targets = [h for h in SITES if h not in ALREADY_DONE]
        results = await asyncio.gather(*(guarded(h) for h in targets))
    out = sorted(results, key=lambda x: (x["category"], -(x.get("total") or 0)))
    Path("data").mkdir(exist_ok=True)
    with open("data/probe_jdih_all.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    by = {}
    for r in out:
        by.setdefault(r["category"], []).append(r["host"])
    summary = {k: len(v) for k, v in by.items()}
    print(json.dumps(summary, indent=2))
    print(f"wrote data/probe_jdih_all.json ({len(out)} sites)")


if __name__ == "__main__":
    asyncio.run(main())
