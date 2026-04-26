"""Rebuild data/laws.db from data/laws/*.jsonl + translations/*.json.

This is the entry point CI calls before `npm run build`. It is also safe
to run locally — it always recreates the DB file fresh.

Pipeline:
  1. Delete any existing data/laws.db (and -wal/-shm).
  2. db.init_db() — creates schema, FTS5 tables, dimension seed rows.
  3. For each data/laws/*.jsonl, INSERT every row preserving the original
     `id` so that id-keyed translation files still resolve.
  4. For each translations/*.json (array of {id, title_ko, ...}), apply
     translations onto existing rows. Files for ids that no longer exist
     are skipped quietly.
  5. Print row count + untranslated count.

Usage:
    python -m crawler.build_db
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from . import db


ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = ROOT / "data" / "laws"
TRANS_DIR = ROOT / "translations"


# Same column list as dump_jsonl, excluding 'id' which is bound separately.
INSERT_COLUMNS = [
    "slug",
    "category", "law_type", "law_number", "year",
    "title_id", "title_en",
    "ministry_code", "ministry_name_ko", "region_code",
    "enactment_date", "promulgation_date", "effective_date", "repealed_date",
    "status", "era",
    "source", "source_url", "pdf_url_id", "pdf_url_en",
]


def insert_row(conn: sqlite3.Connection, row: dict) -> None:
    cols = ["id"] + INSERT_COLUMNS
    placeholders = ",".join(f":{c}" for c in cols)
    payload = {c: row.get(c) for c in cols}
    payload["status"] = payload.get("status") or "berlaku"
    payload["era"] = payload.get("era") or "modern"
    if not payload.get("source") or not payload.get("source_url"):
        return  # skip malformed
    if not payload.get("category") or not payload.get("law_type") or not payload.get("law_number") or not payload.get("title_id"):
        return  # skip rows that violate NOT NULL
    conn.execute(
        f"INSERT INTO laws ({','.join(cols)}) VALUES ({placeholders})",
        payload,
    )


def apply_translation_file(conn: sqlite3.Connection, path: Path) -> tuple[int, int]:
    """Apply title_ko/summary_ko/categories/keywords for ids in this file.

    Returns (applied, skipped).
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0
    if not isinstance(payload, list):
        return 0, 0
    applied = 0
    skipped = 0
    for entry in payload:
        try:
            law_id = int(entry["id"])
            title_ko = (entry["title_ko"] or "").strip()
        except (KeyError, ValueError, AttributeError, TypeError):
            skipped += 1
            continue
        if not title_ko:
            skipped += 1
            continue
        # apply_translation no-ops silently when id doesn't exist
        db.apply_translation(
            conn,
            law_id=law_id,
            title_ko=title_ko,
            summary_ko=(entry.get("summary_ko") or "").strip() or None,
            categories=entry.get("categories") or None,
            keywords=entry.get("keywords") or None,
        )
        applied += 1
    return applied, skipped


def main() -> int:
    db_path = db.DB_PATH
    for ext in ("", "-wal", "-shm", "-journal"):
        p = Path(str(db_path) + ext)
        if p.exists():
            p.unlink()
    db.init_db()

    jsonl_files = sorted(LAWS_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"WARNING: no JSONL files found under {LAWS_DIR}", file=sys.stderr)
    total_inserted = 0
    with db.connect() as conn:
        for path in jsonl_files:
            n = 0
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    insert_row(conn, row)
                    n += 1
            print(f"  inserted {n:>6} from {path.relative_to(ROOT)}")
            total_inserted += n

    trans_files = sorted(TRANS_DIR.glob("*.json"))
    total_applied = 0
    total_skipped = 0
    with db.connect() as conn:
        for path in trans_files:
            applied, skipped = apply_translation_file(conn, path)
            print(f"  translated {applied:>6} (skipped {skipped:>5}) from {path.relative_to(ROOT)}")
            total_applied += applied
            total_skipped += skipped

    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
        untrans = conn.execute("SELECT COUNT(*) FROM laws WHERE title_ko IS NULL").fetchone()[0]
    print(f"\nDB built: {total} rows ({untrans} untranslated)")
    print(f"  inserted={total_inserted}  translated={total_applied}  trans_skipped={total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
