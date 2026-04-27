"""Promote crawler output (data/raw/jdih_<site>.jsonl) into the source-of-truth
data/laws/jdih_<site>.jsonl with stable, monotonically-assigned ids.

Existing data/laws/ files are scanned to find the current max id; new rows
get ids starting at max_id + 1. If a target file already exists, its rows
are loaded and matched to incoming rows by (source, source_url) to preserve
ids across re-runs.

Usage:
    python -m scripts.promote_raw_jsonl jdih_bnn jdih_bmkg jdih_polri
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LAWS = ROOT / "data" / "laws"


def load_existing_ids() -> tuple[int, dict[tuple[str, str], int]]:
    """Returns (max_id, {(source,url): id}) across all data/laws/*.jsonl."""
    max_id = 0
    keymap: dict[tuple[str, str], int] = {}
    for f in LAWS.glob("*.jsonl"):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                rid = r.get("id")
                if isinstance(rid, int) and rid > max_id:
                    max_id = rid
                src = r.get("source")
                url = r.get("source_url")
                if rid and src and url:
                    keymap[(src, url)] = rid
    return max_id, keymap


def promote(site_key: str, next_id: int, keymap: dict[tuple[str, str], int]) -> tuple[int, int, int]:
    """Returns (new_count, reused_count, max_id_used)."""
    src_path = RAW / f"{site_key}.jsonl"
    dst_path = LAWS / f"{site_key}.jsonl"
    if not src_path.exists():
        print(f"  SKIP {site_key}: {src_path} not found", file=sys.stderr)
        return 0, 0, next_id - 1
    new_count = 0
    reused = 0
    with src_path.open(encoding="utf-8") as fin, dst_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = (row.get("source"), row.get("source_url"))
            if key in keymap:
                row["id"] = keymap[key]
                reused += 1
            else:
                row["id"] = next_id
                next_id += 1
                new_count += 1
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  {site_key}: new={new_count} reused={reused} → {dst_path.relative_to(ROOT)}")
    return new_count, reused, next_id - 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="+", help="site keys, e.g. jdih_bnn jdih_bmkg jdih_polri")
    args = ap.parse_args()

    max_id, keymap = load_existing_ids()
    print(f"Existing max_id={max_id}, total tracked rows={len(keymap)}")
    next_id = max_id + 1
    grand_new = 0
    grand_reused = 0
    for site in args.sites:
        nc, ru, last = promote(site, next_id, keymap)
        next_id = last + 1
        grand_new += nc
        grand_reused += ru
    print(f"\nTotal: new={grand_new} reused={grand_reused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
