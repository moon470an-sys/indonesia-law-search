"""Daily incremental update orchestrator.

Pipeline:
  1. For each registered scraper, fetch the set of source_urls already in DB
     and pass them as `known_source_urls` for incremental mode.
  2. Run the scraper. It bails out as soon as it hits N consecutive known URLs.
  3. Upsert into laws (newly-added rows have title_ko = NULL).
  4. Split newly-added pending rows into chunks under
     `data/pending/chunks/<ministry>_NN.json` (~300/chunk) for the
     `/translate-pending` slash command to consume.
  5. Write a `data/pending/today.summary.json` describing the day's deltas.

Usage:
    python -m crawler.update_all                 # all ministries
    python -m crawler.update_all esdm            # subset
    python -m crawler.update_all --full esdm     # ignore known_source_urls (full re-crawl)

Inheritance: scrapers must accept a `known_source_urls: set[str] | None` kwarg
in __init__. Scrapers that don't are run in non-incremental mode.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import math
from datetime import date, datetime
from pathlib import Path

from . import db
from .ministries import (
    ALL_SCRAPERS, PeraturanGoIdScraper,
    DephubScraper, EsdmScraper, BkpmScraper,
    KemenkeuScraper, KemendagScraper,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("crawler.update_all")

ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = ROOT / "data" / "pending"
CHUNK_DIR = PENDING_DIR / "chunks"
SUMMARY_PATH = PENDING_DIR / "today.summary.json"

KEY_MAP = {
    "peraturan": PeraturanGoIdScraper,
    "dephub":    DephubScraper,
    "esdm":      EsdmScraper,
    "bkpm":      BkpmScraper,
    "kemenkeu":  KemenkeuScraper,
    "kemendag":  KemendagScraper,
}

CHUNK_SIZE = 300


def known_source_urls(conn, source_value: str) -> set[str]:
    rows = conn.execute(
        "SELECT source_url FROM laws WHERE source = ?", (source_value,)
    ).fetchall()
    return {r["source_url"] for r in rows}


def source_value_for(scraper_cls) -> str:
    code = getattr(scraper_cls, "ministry_code", "") or ""
    if code:
        return f"jdih_{code}"
    return "peraturan_go_id"


def supports_incremental(scraper_cls) -> bool:
    sig = inspect.signature(scraper_cls.__init__)
    return "known_source_urls" in sig.parameters


async def run_scraper(scraper_cls, *, full: bool) -> tuple[list[dict], int]:
    src_value = source_value_for(scraper_cls)
    with db.connect() as c:
        before_total = c.execute(
            "SELECT COUNT(*) FROM laws WHERE source = ?", (src_value,)
        ).fetchone()[0]
        known = set() if full else known_source_urls(c, src_value)

    kwargs = {}
    if supports_incremental(scraper_cls) and not full:
        kwargs["known_source_urls"] = known

    log.info("[%s] running (incremental=%s, known=%d)",
             scraper_cls.__name__,
             supports_incremental(scraper_cls) and not full,
             len(known))
    async with scraper_cls(**kwargs) as scraper:
        rows = await scraper.run()

    new_in_batch = 0
    with db.connect() as c:
        for row in rows:
            db.upsert_law(c, row)
        after_total = c.execute(
            "SELECT COUNT(*) FROM laws WHERE source = ?", (src_value,)
        ).fetchone()[0]
        new_in_batch = after_total - before_total
    log.info("[%s] yielded=%d, new_in_db=%d", scraper_cls.__name__, len(rows), new_in_batch)
    return rows, new_in_batch


def export_pending_chunks(ministry_code: str, batch_label: str) -> list[str]:
    """Split untranslated rows for a ministry into ~CHUNK_SIZE JSON chunks.

    Returns the list of chunk file paths written.
    """
    if not ministry_code:
        return []
    with db.connect() as c:
        rows = c.execute(
            "SELECT id, title_id, law_type FROM laws "
            " WHERE ministry_code = ? AND title_ko IS NULL ORDER BY id",
            (ministry_code,),
        ).fetchall()
    if not rows:
        return []
    items = [
        {"id": r["id"], "title_id": r["title_id"], "law_type": r["law_type"]}
        for r in rows
    ]
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    n_chunks = math.ceil(len(items) / CHUNK_SIZE)
    paths: list[str] = []
    for i in range(n_chunks):
        chunk = items[i * CHUNK_SIZE: (i + 1) * CHUNK_SIZE]
        if not chunk:
            continue
        # Stable filename per ministry/batch so re-runs overwrite the same files.
        out = CHUNK_DIR / f"{ministry_code}_{batch_label}_{i + 1:02d}.json"
        out.write_text(
            json.dumps(chunk, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        paths.append(str(out.relative_to(ROOT)))
    return paths


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="*", help="ministry keys to run (default: all)")
    parser.add_argument("--full", action="store_true",
                        help="ignore known_source_urls and force full crawl")
    args = parser.parse_args(argv)

    db.init_db()
    targets = ALL_SCRAPERS
    if args.keys:
        chosen = [KEY_MAP[k] for k in args.keys if k in KEY_MAP]
        if not chosen:
            log.error("No matching scrapers. Valid keys: %s", list(KEY_MAP))
            return 1
        targets = chosen

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    summary: dict = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "date": today,
        "full": args.full,
        "ministries": {},
        "total_new": 0,
        "chunk_files": [],
    }

    for cls in targets:
        try:
            rows, new_in_db = await run_scraper(cls, full=args.full)
        except Exception as e:
            log.exception("[%s] failed", cls.__name__)
            summary["ministries"][cls.__name__] = {"error": str(e)[:300]}
            continue
        code = getattr(cls, "ministry_code", "") or "peraturan"
        chunks = export_pending_chunks(code, batch_label=today)
        summary["ministries"][cls.__name__] = {
            "ministry_code": code,
            "yielded": len(rows),
            "new_in_db": new_in_db,
            "chunk_files": chunks,
        }
        summary["total_new"] += new_in_db
        summary["chunk_files"].extend(chunks)

    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    log.info("summary written → %s (total_new=%d, chunks=%d)",
             SUMMARY_PATH.relative_to(ROOT), summary["total_new"], len(summary["chunk_files"]))

    # Re-dump JSONL for sources whose row count changed. We dump unconditionally
    # for any source that ran, since updated_at also drifts even when no new
    # rows arrive — keeps `data/laws/*.jsonl` faithful to the live DB.
    if summary["total_new"] > 0 or args.full:
        from . import dump_jsonl
        sources_touched = []
        for cls in targets:
            code = getattr(cls, "ministry_code", "") or ""
            src = f"jdih_{code}" if code else "peraturan_go_id"
            sources_touched.append(src)
        log.info("re-dumping JSONL for: %s", sources_touched)
        dump_jsonl.main(sources_touched)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
