"""Delete peraturan.go.id rows that are nav/stats links, not actual laws.

Heuristic: real detail URLs contain digits or 'tahun' or '/details/'.
Anything else (rekapitulasi, grafik, sub-category landing pages) is removed.

Run after a crawl that produced spurious rows.
"""
from __future__ import annotations

import re
import sys

from crawler import db


PATTERN = re.compile(r"(\d|tahun|details)", re.IGNORECASE)


def main() -> int:
    with db.connect() as c:
        rows = c.execute(
            "SELECT id, source_url FROM laws WHERE source='peraturan_go_id'"
        ).fetchall()
        bad_ids: list[int] = []
        for r in rows:
            last = r["source_url"].rstrip("/").rsplit("/", 1)[-1].lower()
            if not PATTERN.search(last):
                bad_ids.append(r["id"])

        print(f"Total peraturan_go_id rows: {len(rows)}")
        print(f"Will delete: {len(bad_ids)}")

        if "--dry-run" in sys.argv:
            for i in bad_ids:
                row = next(r for r in rows if r["id"] == i)
                print(f"  - #{i}: {row['source_url']}")
            return 0

        if not bad_ids:
            return 0

        c.executemany(
            "DELETE FROM laws WHERE id = ?",
            [(i,) for i in bad_ids],
        )
        print(f"Deleted {len(bad_ids)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
