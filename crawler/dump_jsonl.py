"""Dump laws.db to per-source JSONL files under data/laws/.

The JSONL files become the source of truth committed to git; data/laws.db
is rebuilt in CI by crawler.build_db.

Each line is a JSON object containing a stable `id` (so id-keyed
translations/*.json files keep working), the (source, source_url) upsert
identity, and every metadata field from the laws table.

Translation fields (title_ko, summary_ko, categories, keywords) are NOT
emitted here — they live separately in translations/*.json.

Usage:
    python -m crawler.dump_jsonl                # all sources
    python -m crawler.dump_jsonl jdih_esdm      # one source
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db


ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = ROOT / "data" / "laws"

# Columns dumped to JSONL. Excludes translation fields and timestamps.
COLUMNS = [
    "id", "slug",
    "category", "law_type", "law_number", "year",
    "title_id", "title_en",
    "ministry_code", "ministry_name_ko", "region_code",
    "enactment_date", "promulgation_date", "effective_date", "repealed_date",
    "status", "era",
    "source", "source_url", "pdf_url_id", "pdf_url_en",
]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("sources", nargs="*",
                   help="restrict to these source values (default: all)")
    args = p.parse_args(argv)

    LAWS_DIR.mkdir(parents=True, exist_ok=True)

    with db.connect() as c:
        if args.sources:
            placeholders = ",".join("?" for _ in args.sources)
            sources = [r[0] for r in c.execute(
                f"SELECT DISTINCT source FROM laws WHERE source IN ({placeholders}) ORDER BY source",
                args.sources,
            ).fetchall()]
        else:
            sources = [r[0] for r in c.execute(
                "SELECT DISTINCT source FROM laws ORDER BY source"
            ).fetchall()]

        total = 0
        for src in sources:
            rows = c.execute(
                f"SELECT {','.join(COLUMNS)} FROM laws WHERE source = ? ORDER BY id",
                (src,),
            ).fetchall()
            out_path = LAWS_DIR / f"{src}.jsonl"
            with out_path.open("w", encoding="utf-8") as f:
                for r in rows:
                    obj = {k: r[k] for k in COLUMNS if r[k] is not None}
                    f.write(json.dumps(obj, ensure_ascii=False))
                    f.write("\n")
            print(f"  {len(rows):>6} → {out_path.relative_to(ROOT)}")
            total += len(rows)
    print(f"total {total} rows across {len(sources)} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
