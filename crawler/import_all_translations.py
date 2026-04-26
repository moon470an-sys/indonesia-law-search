"""Import every translations/*.json file that hasn't been applied yet.

Idempotent: import_translations.apply_translation only updates `title_ko`
when the row exists, so re-running is safe.

Usage:
    python -m crawler.import_all_translations            # all files
    python -m crawler.import_all_translations esdm       # just esdm_*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db


ROOT = Path(__file__).resolve().parent.parent
TRANS_DIR = ROOT / "translations"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("prefix", nargs="?", default=None,
                   help="ministry_code prefix; defaults to all files")
    args = p.parse_args(argv)

    pattern = f"{args.prefix}_*.json" if args.prefix else "*.json"
    paths = sorted(TRANS_DIR.glob(pattern))
    if not paths:
        print(f"No translation files matching {pattern}", file=sys.stderr)
        return 0

    applied = 0
    skipped = 0
    with db.connect() as conn:
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  [skip] {path.name}: {e}", file=sys.stderr)
                continue
            if not isinstance(payload, list):
                continue
            local_applied = 0
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
                db.apply_translation(
                    conn,
                    law_id=law_id,
                    title_ko=title_ko,
                    summary_ko=(entry.get("summary_ko") or "").strip() or None,
                    categories=entry.get("categories") or None,
                    keywords=entry.get("keywords") or None,
                )
                local_applied += 1
            applied += local_applied
            print(f"  [{path.name}] applied={local_applied}")
    print(f"total applied={applied} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
