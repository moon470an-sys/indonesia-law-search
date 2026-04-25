"""Run scrapers and upsert into SQLite.

Usage:
    python -m crawler.run_all                # all sources
    python -m crawler.run_all peraturan      # peraturan.go.id only
    python -m crawler.run_all esdm dephub    # subset by source key
"""
from __future__ import annotations

import asyncio
import logging
import sys

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
log = logging.getLogger("crawler.run_all")

# 명시적 source-key 매핑 (CLI 인자용)
KEY_MAP = {
    "peraturan": PeraturanGoIdScraper,
    "dephub":    DephubScraper,
    "esdm":      EsdmScraper,
    "bkpm":      BkpmScraper,
    "kemenkeu":  KemenkeuScraper,
    "kemendag":  KemendagScraper,
}


async def run_one(scraper_cls) -> list[dict]:
    async with scraper_cls() as scraper:
        return await scraper.run()


async def main(keys: list[str] | None = None) -> int:
    db.init_db()
    targets = ALL_SCRAPERS
    if keys:
        chosen = [KEY_MAP[k] for k in keys if k in KEY_MAP]
        if not chosen:
            log.error("No matching scrapers. Valid keys: %s", list(KEY_MAP))
            return 1
        targets = chosen

    upserted = 0
    for cls in targets:
        log.info("running %s", cls.__name__)
        try:
            rows = await run_one(cls)
        except Exception:
            log.exception("[%s] scraper failed", cls.__name__)
            continue
        with db.connect() as conn:
            for row in rows:
                db.upsert_law(conn, row)
                upserted += 1
    log.info("upserted %d rows total", upserted)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
