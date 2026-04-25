"""Import a translation JSON file into the laws DB.

Usage:
    python -m crawler.import_translations translations/2026-04-25_all.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="path to translation JSON file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.path)
    if not src.exists():
        print(f"File not found: {src}", file=sys.stderr)
        return 1

    payload = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        print("Expected a JSON array.", file=sys.stderr)
        return 2

    applied = 0
    with db.connect() as conn:
        for entry in payload:
            try:
                law_id = int(entry["id"])
                title_ko = entry["title_ko"].strip()
            except (KeyError, ValueError, AttributeError):
                print(f"Skipping malformed entry: {entry}", file=sys.stderr)
                continue
            if not title_ko:
                continue
            if args.dry_run:
                print(f"would update id={law_id}: {title_ko}")
                continue
            db.apply_translation(
                conn,
                law_id=law_id,
                title_ko=title_ko,
                summary_ko=(entry.get("summary_ko") or "").strip() or None,
                categories=entry.get("categories") or None,
                keywords=entry.get("keywords") or None,
            )
            applied += 1

    print(f"Applied {applied} translations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
