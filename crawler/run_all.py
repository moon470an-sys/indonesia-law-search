"""Run every ministry scraper and upsert results into SQLite.

Usage:
    python -m crawler.run_all              # all ministries
    python -m crawler.run_all dephub esdm  # subset
"""
from __future__ import annotations

import asyncio
import logging
import sys

from . import db
from .ministries import ALL_SCRAPERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("crawler.run_all")


async def run_one(scraper_cls) -> list[dict]:
    async with scraper_cls() as scraper:
        return await scraper.run()


async def main(codes: list[str] | None = None) -> int:
    db.init_db()
    targets = ALL_SCRAPERS
    if codes:
        targets = [c for c in ALL_SCRAPERS if c.ministry_code in codes]
        if not targets:
            log.error("No scrapers match: %s", codes)
            return 1

    inserted = 0
    for cls in targets:
        log.info("running %s", cls.ministry_code)
        try:
            rows = await run_one(cls)
        except Exception:
            log.exception("[%s] scraper failed", cls.ministry_code)
            continue
        with db.connect() as conn:
            for row in rows:
                db.upsert_law(conn, row)
                inserted += 1
    log.info("upserted %d rows total", inserted)
    return 0


if __name__ == "__main__":
    codes = sys.argv[1:]
    raise SystemExit(asyncio.run(main(codes)))
