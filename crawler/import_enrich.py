"""Import enrichment JSONL files (output of crawler.peraturan_enrich) into the DB.

Each JSONL line is {id, enactment_date?, promulgation_date?, status?, relasi?[]}.
We UPDATE only the columns present in each record (preserves any prior values
for fields the enricher didn't pick up). Relasi rows are written into the
relations table by URL — the related_law_id is filled where we know the target,
otherwise the row is skipped.
"""
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
log = logging.getLogger("import_enrich")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="JSONL paths or globs (e.g. data/enrich/*.jsonl)")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        for hit in glob(p):
            files.append(Path(hit))
    if not files:
        log.error("no files matched: %s", args.paths)
        return 1

    db.init_db()
    updated = 0
    rels = 0
    with db.connect() as conn:
        # cache: source_url → law_id (peraturan_go_id only)
        url_to_id: dict[str, int] = {
            r["source_url"]: r["id"]
            for r in conn.execute(
                "SELECT id, source_url FROM laws WHERE source = 'peraturan_go_id'"
            ).fetchall()
        }

        for f in files:
            log.info("→ %s", f)
            seen = 0
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as e:
                        log.warning("  bad json: %s", e)
                        continue
                    rid = row.get("id")
                    if rid is None:
                        continue
                    seen += 1

                    sets: list[str] = []
                    params: list = []
                    for col in ("enactment_date", "promulgation_date", "status"):
                        v = row.get(col)
                        if v:
                            sets.append(f"{col} = ?")
                            params.append(v)
                    if sets:
                        sets.append("updated_at = CURRENT_TIMESTAMP")
                        params.append(rid)
                        conn.execute(
                            f"UPDATE laws SET {', '.join(sets)} WHERE id = ?",
                            params,
                        )
                        updated += 1

                    relasi = row.get("relasi")
                    if relasi:
                        for rel_url in relasi:
                            rel_id = url_to_id.get(rel_url)
                            if rel_id is None or rel_id == rid:
                                continue
                            try:
                                conn.execute(
                                    """
                                    INSERT OR IGNORE INTO relations
                                        (law_id, related_law_id, relation_kind)
                                    VALUES (?, ?, 'terkait')
                                    """,
                                    (rid, rel_id),
                                )
                                rels += 1
                            except Exception:
                                pass
                    if seen % 1000 == 0:
                        log.info("  processed %d", seen)
            log.info("  done: %d entries", seen)
    log.info("total: laws updated %d, relations inserted %d", updated, rels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
