"""Multi-layer probe for 65 Indonesian JDIH sites.

For each host, attempts:
  Layer 1 — API discovery: GET 8 standard JDIHN-style API endpoints,
            classify success by JSON content-type and parseability.
  Layer 2 — Main domain (jdih.X.go.id → X.go.id): try /peraturan, /regulasi,
            /id/regulasi, /produk-hukum on the main ministry domain.
  Layer 3 — Wayback CDX: ask web.archive.org how many archived URLs exist
            for jdih.X.go.id, plus the most recent snapshot timestamp.

Output: data/probe_layers.json with per-host classification and per-layer
        viability flags. The deciding logic in Layer 1 also dumps any JSON
        response under data/probe/api_<host>_<n>.json for shape inspection.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

HOSTS = [
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
    "bssn.go.id", "bphmigas.go.id", "mkri.id",
]

API_PATHS = [
    "/api/peraturan", "/api/v1/peraturan", "/api/dokumen", "/api/v1/dokumen",
    "/api/list", "/api/list/peraturan",
    "/json/peraturan", "/data/peraturan",
    "/rss/peraturan", "/feed/peraturan", "/feed",
    # JDIHN 2.0 spec
    "/api/v1/dokumenhukum", "/api/dokumen/peraturan",
]

MAIN_PATHS = [
    "/peraturan", "/regulasi", "/id/regulasi", "/produk-hukum",
    "/dokumen-hukum", "/peraturan-perundang-undangan",
    "/regulation", "/laws",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

CDX_TEMPLATE = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=jdih.{host}/*&output=json&limit=1&filter=statuscode:200"
    "&from=20200101&fl=timestamp,original&collapse=urlkey"
)


async def probe_url(client: httpx.AsyncClient, url: str, dump_dir: Path | None = None,
                    dump_name: str | None = None) -> dict:
    try:
        r = await client.get(url, follow_redirects=True, timeout=12.0)
    except Exception as e:
        return {"url": url, "error": str(e)[:160]}
    ctype = r.headers.get("content-type", "")
    out: dict = {"url": url, "status": r.status_code, "ctype": ctype, "len": len(r.content),
                 "final": str(r.url)}
    is_json = "json" in ctype.lower() or (
        r.status_code == 200 and r.text and r.text.lstrip().startswith(("{", "["))
    )
    out["is_json"] = is_json
    if is_json and r.status_code == 200:
        try:
            obj = r.json()
            if isinstance(obj, dict):
                out["json_keys"] = list(obj.keys())[:25]
                # common JDIHN list shapes: {data: [...]} or {results: [...]} or {peraturan: [...]}
                for list_key in ("data", "results", "items", "peraturan", "dokumen", "rows"):
                    v = obj.get(list_key)
                    if isinstance(v, list):
                        out["list_key"] = list_key
                        out["list_len"] = len(v)
                        if v and isinstance(v[0], dict):
                            out["row_keys"] = list(v[0].keys())[:20]
                        break
            elif isinstance(obj, list):
                out["list_len"] = len(obj)
                if obj and isinstance(obj[0], dict):
                    out["row_keys"] = list(obj[0].keys())[:20]
            if dump_dir and dump_name:
                dump_dir.mkdir(parents=True, exist_ok=True)
                (dump_dir / dump_name).write_text(r.text[:200_000], encoding="utf-8")
        except Exception as e:
            out["json_parse_error"] = str(e)[:120]
    elif r.status_code == 200 and "html" in ctype.lower():
        title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
        out["title"] = title_m.group(1).strip()[:120] if title_m else None
    return out


async def probe_host(client: httpx.AsyncClient, host: str) -> dict:
    out: dict = {"host": host, "api": [], "main": [], "wayback": None}
    base = f"https://jdih.{host}"
    main = f"https://{host}"

    # Layer 1: API endpoints on jdih.<host>
    for p in API_PATHS:
        r = await probe_url(client, base + p, Path("data/probe"),
                            f"api_{host}_{p.strip('/').replace('/', '_')}.json")
        out["api"].append(r)

    # Layer 2: Main ministry domain
    for p in MAIN_PATHS:
        r = await probe_url(client, main + p)
        out["main"].append(r)

    # Layer 3: Wayback CDX availability
    try:
        cdx_url = CDX_TEMPLATE.format(host=host)
        r = await client.get(cdx_url, timeout=20.0)
        if r.status_code == 200 and r.text.strip():
            try:
                rows = r.json()
                # CDX returns [["timestamp","original"], ...] (header + data)
                if isinstance(rows, list) and len(rows) > 1:
                    out["wayback"] = {"snapshots_seen": len(rows) - 1,
                                      "newest_sample": rows[1] if len(rows) > 1 else None}
                else:
                    # Run a wider count query
                    count_url = (
                        f"https://web.archive.org/cdx/search/cdx?url=jdih.{host}/*"
                        f"&output=json&showNumPages=true"
                    )
                    cr = await client.get(count_url, timeout=15.0)
                    out["wayback"] = {"raw_count_response": cr.text[:200], "rows_seen_in_initial": len(rows)}
            except Exception as e:
                out["wayback"] = {"parse_error": str(e)[:120], "body_head": r.text[:200]}
        else:
            out["wayback"] = {"status": r.status_code, "body_head": r.text[:200]}
    except Exception as e:
        out["wayback"] = {"error": str(e)[:160]}

    return out


def classify(host_result: dict) -> dict:
    """Pick the best layer for a host."""
    api_hits = [r for r in host_result.get("api", [])
                if r.get("status") == 200 and r.get("is_json") and r.get("list_len", 0) > 0]
    main_hits = [r for r in host_result.get("main", [])
                 if r.get("status") == 200 and r.get("len", 0) > 8000]
    wb = host_result.get("wayback") or {}
    has_wb = isinstance(wb, dict) and wb.get("snapshots_seen", 0) > 0
    if api_hits:
        return {"layer": "L1-api", "evidence": api_hits[0]["url"], "list_len": api_hits[0].get("list_len")}
    if main_hits:
        return {"layer": "L2-main", "evidence": main_hits[0]["url"]}
    if has_wb:
        return {"layer": "L3-wayback", "snapshots": wb.get("snapshots_seen")}
    return {"layer": "L5-dead"}


async def main() -> None:
    Path("data/probe").mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(8)

    async with httpx.AsyncClient(
        headers={"User-Agent": UA, "Accept-Language": "id-ID,en;q=0.5"},
        http2=True,
    ) as client:
        async def guarded(host: str) -> dict:
            async with sem:
                try:
                    return await asyncio.wait_for(probe_host(client, host), timeout=240)
                except asyncio.TimeoutError:
                    return {"host": host, "error": "host-timeout-240s"}

        results = await asyncio.gather(*(guarded(h) for h in HOSTS))

    # Classify each host
    classified: list[dict] = []
    for r in results:
        if r.get("error"):
            classified.append({"host": r["host"], "layer": "L5-dead",
                               "reason": "host-timeout"})
            continue
        c = classify(r)
        classified.append({"host": r["host"], **c})

    Path("data/probe_layers.json").write_text(
        json.dumps({"raw": results, "classified": classified}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )

    # Summary
    by_layer: dict = {}
    for c in classified:
        by_layer.setdefault(c["layer"], []).append(c["host"])
    print("=== Layer assignment summary ===")
    for layer in sorted(by_layer):
        print(f"  [{layer}] {len(by_layer[layer]):>2} sites")
        for h in by_layer[layer]:
            entry = next((x for x in classified if x["host"] == h), {})
            extra = ""
            if entry.get("evidence"):
                extra = f"  → {entry['evidence']}"
            if entry.get("list_len") is not None:
                extra += f"  list_len={entry['list_len']}"
            if entry.get("snapshots") is not None:
                extra += f"  snapshots={entry['snapshots']}"
            print(f"      {h:30}{extra}")


if __name__ == "__main__":
    asyncio.run(main())
