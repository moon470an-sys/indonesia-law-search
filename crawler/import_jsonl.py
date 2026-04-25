"""Import peraturan.go.id JSONL files (output of crawler.peraturan_full) into the DB."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from glob import glob
from pathlib import Path

from . import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("import_jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="JSONL paths or globs (e.g. data/raw/*.jsonl)")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        for hit in glob(p):
            files.append(Path(hit))
    if not files:
        log.error("no files matched: %s", args.paths)
        return 1

    db.init_db()
    total = 0
    with db.connect() as conn:
        for f in files:
            log.info("→ %s", f)
            n = 0
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as e:
                        log.warning("  bad json line skipped: %s", e)
                        continue
                    db.upsert_law(conn, row)
                    n += 1
                    if n % 1000 == 0:
                        log.info("  %d rows", n)
            log.info("  done: %d rows", n)
            total += n
    log.info("total upserted: %d rows", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
