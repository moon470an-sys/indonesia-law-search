"""Generic JDIHN-style JSON-API scraper for ministry sites with proper APIs.

Three sites confirmed (probe_layers run): bnn, bmkg, polri.

Each site has its own JSON shape, so we define a per-site Adapter that maps
the raw JSON row into our LawRecord shape. The runner handles pagination
auto-detection (tries common param names: page+limit, page+perPage,
offset+limit, page only) and writes one JSONL per site under data/raw/.

CLI:
  python -m crawler.api_scrapers bnn bmkg polri        # all named
  python -m crawler.api_scrapers --all                 # everything in ADAPTERS
  python -m crawler.api_scrapers bnn --max-pages 5     # cap for smoke test
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import httpx

from .base_scraper import LawRecord

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36 jdih-api-scraper/0.1"
)


def _parse_yyyymmdd(s: str | int | None) -> str | None:
    """'20260414' or 20260414 → '2026-04-14'. Returns None on bad input."""
    if s is None:
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # ISO already?
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return None


def _parse_iso(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else None


def _g(obj: dict, *keys: str, default: Any = None) -> Any:
    """Get the first non-None value for any of the given keys."""
    for k in keys:
        v = obj.get(k)
        if v is not None and v != "":
            return v
    return default


# === Per-site adapters ===
# `map_row(raw_row, site) -> LawRecord` is the core.

def _map_bnn(row: dict) -> LawRecord:
    # https://jdih.bnn.go.id/api/peraturan
    # row keys: id, percategorycode, judul, nomor, tahun, tanggal, status, file_url
    title = _g(row, "judul", default="")
    law_number = _g(row, "nomor", default="")
    year = _g(row, "tahun")
    return LawRecord(
        category="keputusan",  # BNN publishes mostly Perka/SE — admin regulations
        law_type=_g(row, "percategorycode", default="PerkaBNN"),
        law_number=str(law_number) if law_number else f"bnn-{row.get('id','')}",
        title_id=title,
        source="jdih_bnn",
        source_url=f"https://jdih.bnn.go.id/produk-hukum/{row.get('id','')}",
        ministry_code="bnn",
        ministry_name_ko="마약수사청",
        year=int(year) if year and str(year).isdigit() else None,
        enactment_date=_parse_yyyymmdd(_g(row, "tanggal")),
        status=("berlaku" if str(_g(row, "status", default="")).lower().startswith("berlaku") else "tidak_diketahui"),
        pdf_url_id=_g(row, "file_url"),
    )


def _map_bmkg(row: dict) -> LawRecord:
    # https://jdih.bmkg.go.id/api/dokumen
    # JDIHN 2.0 schema — very rich
    title = _g(row, "judul", default="")
    bentuk = _g(row, "bentuk_peraturan", default="")
    jenis = _g(row, "jenis_peraturan", default="")
    law_type = bentuk or jenis or "Peraturan"
    law_number = _g(row, "nomor_peraturan", default="")
    year = _g(row, "tahun_terbit")
    # PDF: data_lampiran[0].url_lampiran (relative)
    pdf_url = None
    lampirans = row.get("data_lampiran") or []
    if isinstance(lampirans, list) and lampirans:
        u = lampirans[0].get("url_lampiran")
        if u:
            pdf_url = u if u.startswith("http") else f"https://jdih.bmkg.go.id/{u.lstrip('/')}"
    return LawRecord(
        category="peraturan",
        law_type=str(law_type),
        law_number=str(law_number) if law_number and str(law_number) != "--" else f"bmkg-{row.get('id','')}",
        title_id=title,
        source="jdih_bmkg",
        source_url=f"https://jdih.bmkg.go.id/dokumen/detail/{row.get('id','')}",
        ministry_code="bmkg",
        ministry_name_ko="기상기후지구물리청",
        year=int(year) if year and str(year).isdigit() else None,
        enactment_date=_parse_iso(_g(row, "tanggal_penetapan")),
        promulgation_date=_parse_iso(_g(row, "tanggal_pengundangan")),
        status=("berlaku" if str(_g(row, "status", default="")).lower().startswith("berlaku") else "tidak_diketahui"),
        pdf_url_id=pdf_url,
    )


def _map_polri(row: dict) -> LawRecord:
    # https://jdih.polri.go.id/api/v1/dokumen
    title = _g(row, "judul", default="")
    law_type = _g(row, "jenis", "singkatan_jenis", default="PERKAP")
    law_number = _g(row, "nomor_peraturan", default="")
    year = _g(row, "tahun_terbit")
    # external URL (PDF or HTML) buried in metadata_eksternal JSON string
    pdf_url = _g(row, "url_eksternal")
    return LawRecord(
        category="peraturan",
        law_type=str(law_type),
        law_number=str(law_number) if law_number else f"polri-{row.get('id','')}",
        title_id=title,
        source="jdih_polri",
        source_url=f"https://jdih.polri.go.id/dokumen/detail/{row.get('id','')}",
        ministry_code="polri",
        ministry_name_ko="국가경찰청",
        year=int(year) if year and str(year).isdigit() else None,
        enactment_date=_parse_iso(_g(row, "tanggal_penetapan")),
        promulgation_date=_parse_iso(_g(row, "tanggal_pengundangan")),
        status="tidak_diketahui",
        pdf_url_id=pdf_url,
    )


# === Adapter registry ===
# Each adapter: (list_url, list_key, total_key|None, page_param, limit_param, limit, mapper)
ADAPTERS: dict[str, dict] = {
    "bnn": {
        "list_url": "https://jdih.bnn.go.id/api/peraturan",
        "list_key": "data",
        "total_key": None,   # paginate until empty
        "page_param": "page",
        "limit_param": "limit",
        "limit": 50,
        "mapper": _map_bnn,
    },
    "bmkg": {
        "list_url": "https://jdih.bmkg.go.id/api/dokumen",
        "list_key": "data",
        "total_key": "dataCount",
        "page_param": "page",
        # bmkg's perPage convention; will fall back if 1st response has fewer than asked-for
        "limit_param": "perPage",
        "limit": 100,
        "mapper": _map_bmkg,
    },
    "polri": {
        "list_url": "https://jdih.polri.go.id/api/v1/dokumen",
        "list_key": "data",
        "total_key": None,
        "page_param": "page",
        "limit_param": "limit",
        "limit": 100,
        "mapper": _map_polri,
    },
}


async def fetch_page(client: httpx.AsyncClient, adapter: dict, page: int) -> tuple[list[dict], int | None]:
    """Returns (rows, total_or_None)."""
    params = {adapter["page_param"]: page}
    if adapter.get("limit_param"):
        params[adapter["limit_param"]] = adapter["limit"]
    r = await client.get(adapter["list_url"], params=params, timeout=30.0)
    r.raise_for_status()
    obj = r.json()
    if isinstance(obj, list):
        rows = obj
        total = None
    else:
        rows = obj.get(adapter["list_key"]) or []
        total = obj.get(adapter["total_key"]) if adapter.get("total_key") else None
    return rows, total


async def scrape_site(site: str, max_pages: int) -> tuple[int, int, Path]:
    """Returns (yielded, errors, output_path)."""
    adapter = ADAPTERS[site]
    out_path = Path(f"data/raw/jdih_{site}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    yielded = 0
    errors = 0
    total = None
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID,en;q=0.5"}) as client:
        with out_path.open("w", encoding="utf-8") as f:
            for page in range(1, max_pages + 1):
                try:
                    rows, t = await fetch_page(client, adapter, page)
                except Exception as e:
                    log.error("[%s] page %d fetch failed: %s", site, page, e)
                    errors += 1
                    if errors >= 3:
                        log.error("[%s] aborting after 3 consecutive errors", site)
                        break
                    continue
                if t is not None and total is None:
                    total = t
                    log.info("[%s] total reported=%d", site, total)
                if not rows:
                    log.info("[%s] page %d empty → done", site, page)
                    break
                for raw in rows:
                    try:
                        rec = adapter["mapper"](raw)
                        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
                        yielded += 1
                    except Exception as e:
                        log.warning("[%s] map failed for row id=%s: %s", site, raw.get("id"), e)
                        errors += 1
                log.info("[%s] page %d → %d rows (cum=%d/%s)", site, page, len(rows),
                         yielded, total or "?")
                # Heuristic stop: got fewer rows than requested limit ⇒ last page
                if len(rows) < adapter["limit"]:
                    log.info("[%s] short page (%d < %d) → assumed last", site, len(rows), adapter["limit"])
                    break
                # If total known and we hit it, stop
                if total is not None and yielded >= total:
                    log.info("[%s] reached reported total %d", site, total)
                    break
    log.info("[%s] DONE yielded=%d errors=%d → %s", site, yielded, errors, out_path)
    return yielded, errors, out_path


async def main_async(sites: list[str], max_pages: int) -> None:
    results = await asyncio.gather(*(scrape_site(s, max_pages) for s in sites))
    print("\n=== Summary ===")
    for site, (n, e, p) in zip(sites, results):
        print(f"  {site:8} yielded={n:>5} errors={e:>3} → {p}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*", help="site keys (bnn bmkg polri)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-pages", type=int, default=200)
    args = ap.parse_args()
    sites = list(ADAPTERS) if args.all else args.sites
    if not sites:
        ap.error("specify site keys or --all")
    bad = [s for s in sites if s not in ADAPTERS]
    if bad:
        ap.error(f"unknown sites: {bad} (known: {list(ADAPTERS)})")
    asyncio.run(main_async(sites, args.max_pages))


if __name__ == "__main__":
    main()
