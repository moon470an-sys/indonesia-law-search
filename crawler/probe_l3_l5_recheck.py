"""Re-check L3-wayback (19) and L5-dead (33) jdih sites + properly count
Wayback snapshots.

Network conditions may have changed since the original probe; some sites
that were unreachable then might respond now (kemnaker is one such case).
We try a list of common URL paths per host with httpx (3 retries each)
and also query Wayback CDX with showNumPages for an accurate count.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"

# From probe_layers result
L3_WAYBACK = [
    "polkam.go.id", "maritim.go.id", "kemenkopangan.go.id", "dephub.go.id",
    "kkp.go.id", "menlhk.go.id", "bappenas.go.id", "kemenkopukm.go.id",
    "pu.go.id", "kominfo.go.id", "kemendagri.go.id", "setneg.go.id",
    "kemenparekraf.go.id", "bpkp.go.id", "lkpp.go.id",
    "komnasham.go.id", "kejaksaan.go.id", "tni.mil.id",
]

L5_DEAD = [
    "ekon.go.id", "kemenkopmk.go.id", "kemenkoipk.go.id", "kemenkopolhukam.go.id",
    "bkpm.go.id", "kemendag.go.id", "kemenperin.go.id", "bp2mi.go.id",
    "kemenkumham.go.id", "imigrasi.go.id", "atrbpn.go.id", "kemensos.go.id",
    "bkkbn.go.id", "kemdikbud.go.id", "kemenpora.go.id", "kemendesa.go.id",
    "kemlu.go.id", "menpan.go.id", "setkab.go.id", "ojk.go.id", "lps.go.id",
    "bps.go.id", "pom.go.id", "bnn.go.id", "anri.go.id", "lan.go.id",
    "bsn.go.id", "kpk.go.id", "kpu.go.id", "komisiyudisial.go.id",
    "mahkamahagung.go.id", "bin.go.id", "bssn.go.id", "bphmigas.go.id",
    "mkri.id",
]

PATHS = ["/peraturan", "/dokumen", "/dokumen/peraturan",
         "/produk-hukum", "/regulasi", "/dokumen-hukum",
         "/regulation", "/", "/home", "/index"]


async def try_host(client: httpx.AsyncClient, host: str) -> dict:
    base = f"https://jdih.{host}"
    out = {"host": host, "tries": []}
    best_url = None
    best_len = 0
    for p in PATHS:
        url = base + p
        try:
            r = await client.get(url, timeout=12.0, follow_redirects=True)
            entry = {"url": url, "status": r.status_code, "len": len(r.content)}
            out["tries"].append(entry)
            if r.status_code == 200 and len(r.content) > 8000 and len(r.content) > best_len:
                best_url = str(r.url)
                best_len = len(r.content)
        except Exception as e:
            out["tries"].append({"url": url, "error": str(e)[:80]})
    out["best_url"] = best_url
    out["best_len"] = best_len
    out["reachable"] = best_url is not None
    return out


async def wayback_count(client: httpx.AsyncClient, host: str) -> dict:
    """Use showNumPages then page=K to get total snapshot count."""
    url = (
        f"https://web.archive.org/cdx/search/cdx?url=jdih.{host}/*"
        "&output=json&filter=statuscode:200&from=20200101&collapse=urlkey"
        "&fl=timestamp,original&limit=10000"
    )
    try:
        r = await client.get(url, timeout=45.0)
        if r.status_code != 200 or not r.text.strip():
            return {"host": host, "error": f"cdx status {r.status_code}", "snapshots": 0}
        rows = r.json()
        if isinstance(rows, list) and len(rows) > 1:
            return {"host": host, "snapshots": len(rows) - 1,
                    "newest_ts": rows[1][0] if len(rows) > 1 else None,
                    "oldest_ts": rows[-1][0] if len(rows) > 1 else None}
        return {"host": host, "snapshots": 0}
    except Exception as e:
        return {"host": host, "error": str(e)[:120], "snapshots": 0}


async def main() -> None:
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID"}) as client:
        # Re-check reachability for all 52 hosts
        all_hosts = L3_WAYBACK + L5_DEAD
        sem = asyncio.Semaphore(8)
        async def guarded(h):
            async with sem:
                return await try_host(client, h)
        reachability_results = await asyncio.gather(*(guarded(h) for h in all_hosts))

        # Wayback count for each (parallelized but rate-limited)
        sem2 = asyncio.Semaphore(4)
        async def wb_g(h):
            async with sem2:
                return await wayback_count(client, h)
        wayback_results = await asyncio.gather(*(wb_g(h) for h in all_hosts))

    # Merge by host
    merged = {}
    for r in reachability_results:
        merged[r["host"]] = {"reachable": r["reachable"], "best_url": r.get("best_url"),
                             "best_len": r.get("best_len", 0)}
    for r in wayback_results:
        h = r["host"]
        merged.setdefault(h, {})
        merged[h]["snapshots"] = r.get("snapshots", 0)
        merged[h]["newest_ts"] = r.get("newest_ts")
        merged[h]["oldest_ts"] = r.get("oldest_ts")

    Path("data/probe_l3l5_recheck.json").write_text(
        json.dumps({"hosts": merged}, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    # Print summary
    sorted_hosts = sorted(merged.items(), key=lambda kv: (-kv[1].get("reachable", False), -(kv[1].get("snapshots") or 0)))
    print("=== L3/L5 re-check ===")
    print(f"{'Host':<28} {'Reach':<5} {'BestURL':<70} {'Snapshots':>10}")
    for h, m in sorted_hosts:
        url = (m.get("best_url") or "-")[:68]
        rc = "YES" if m.get("reachable") else "no"
        sn = m.get("snapshots") or 0
        print(f"  {h:<28} {rc:<5} {url:<70} {sn:>10}")

    newly_reachable = [h for h, m in merged.items() if m.get("reachable")]
    print(f"\nNewly reachable: {len(newly_reachable)} sites")
    print(f"  {newly_reachable}")


if __name__ == "__main__":
    asyncio.run(main())
