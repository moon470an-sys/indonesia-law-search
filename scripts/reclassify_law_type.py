"""Re-derive law_type from title_id for already-collected jdih_*.jsonl files.

Most JDIH adapters hard-coded law_type to a single Permen variant
(e.g. "Permenaker" for everything from kemnaker), so genuine Keputusan/
Surat Edaran/Pedoman entries land in the Permen hierarchy bucket.
The hierarchy classifier in web/lib/hierarchy.ts groups by the law_type
prefix, so simply rewriting that string is enough — no DB-level changes
or re-crawl required.

Rules (applied in order, first match wins):
  title starts with "Keputusan Menteri…"        → law_type = "Kepmen<suffix>"
  title starts with "Keputusan Kepala…"          → law_type = "Keputusan Kepala <inst>"
  title starts with "Keputusan Direktur Jenderal" → law_type = "Keputusan Dirjen"
  title starts with "Keputusan Bersama"          → law_type = "Keputusan Bersama"
  title starts with "Keputusan Presiden"         → law_type = "Keppres"
  title starts with "Surat Edaran"               → law_type = "Surat Edaran"
  title starts with "Instruksi Menteri"          → law_type = "Inmen<suffix>"
  title starts with "Instruksi Presiden"         → law_type = "Inpres"
  title starts with "Peraturan Pemerintah Pengganti" → law_type = "Perppu"
  title starts with "Peraturan Pemerintah"       → law_type = "PP"
  title starts with "Peraturan Presiden"         → law_type = "Perpres"
  title starts with "Undang-Undang"              → law_type = "UU"
  title starts with "Pedoman"                    → law_type = "Pedoman"
  title starts with "Nota Kesepahaman"|"MoU"     → law_type = "MoU"
  title starts with "Perjanjian Kerja Sama"|"PKS"→ law_type = "PKS"
  title starts with "Rancangan"                  → law_type = "Rancangan PUU"
  default: keep existing law_type

Per-ministry Kepmen suffix preserved by mapping ministry_code:
  kemnaker → Kepmenaker / kemenkeu → Kepmenkeu / kemendag → Kepmendag etc.

Run: python -m scripts.reclassify_law_type [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "data" / "laws"

# Suffix mapping by ministry_code → "kepmen<suffix>"
MIN_SUFFIX = {
    "esdm":       "esdm",
    "kemenkeu":   "keu",
    "kemendag":   "dag",
    "kemenhub":   "hub",
    "kemenkes":   "kes",
    "kemenag":    "ag",
    "kemenhan":   "han",
    "kemenaker":  "aker",
    "kemenpora":  "pora",
    "kemenpppa":  "pppa",
    "kemenpkp":   "pkp",
    "atrbpn":     "atr",
    "brin":       "brin",
    "bmkg":       "bmkg",
    "bnn":        "bnn",
    "bnpt":       "bnpt",
    "bps":        "bps",
    "polri":      "polri",
    "kpu":        "kpu",
    "kejaksaan":  "jaksaan",
}


def classify_title(title: str, ministry_code: str | None, current_law_type: str) -> str | None:
    """Return new law_type, or None if no change needed."""
    if not title:
        return None
    t = title.strip()
    suffix = MIN_SUFFIX.get(ministry_code or "", "")

    # Order matters — most specific first.
    if t.startswith("Keputusan Bersama"):
        return "Keputusan Bersama"
    if re.match(r"Keputusan Menteri", t, re.I):
        return f"Kepmen{suffix}" if suffix else "Kepmen"
    if re.match(r"Keputusan Kepala", t, re.I):
        return "Keputusan Kepala"
    if re.match(r"Keputusan Direktur Jenderal", t, re.I):
        return "Keputusan Dirjen"
    if re.match(r"Keputusan Sekretaris", t, re.I):
        return "Keputusan Sekretaris"
    if re.match(r"Keputusan Presiden", t, re.I):
        return "Keppres"
    if re.match(r"Keputusan", t, re.I):
        # generic keputusan — still goes into Kepmen bucket
        return f"Kepmen{suffix}" if suffix else "Kepmen"

    if re.match(r"Peraturan Pemerintah Pengganti", t, re.I):
        return "Perppu"
    if re.match(r"Peraturan Pemerintah", t, re.I):
        return "PP"
    if re.match(r"Peraturan Presiden", t, re.I):
        return "Perpres"
    if re.match(r"Peraturan Menteri", t, re.I):
        return f"Permen{suffix}" if suffix else "Permen"
    if re.match(r"Peraturan Kepala", t, re.I):
        return "Peraturan Kepala"
    if re.match(r"Peraturan Direktur Jenderal", t, re.I):
        return "Peraturan Dirjen"
    if re.match(r"Peraturan Bersama", t, re.I):
        return "Peraturan Bersama"

    if re.match(r"(Undang-Undang|Undang Undang|UU\s)", t, re.I):
        return "UU"
    if re.match(r"Surat Edaran", t, re.I):
        return "Surat Edaran"
    if re.match(r"Instruksi Menteri", t, re.I):
        return f"Inmen{suffix}" if suffix else "Inmen"
    if re.match(r"Instruksi Presiden", t, re.I):
        return "Inpres"

    if re.match(r"(Nota Kesepahaman|Memorandum|MoU)", t, re.I):
        return "MoU"
    if re.match(r"Perjanjian Kerja Sama", t, re.I):
        return "PKS"
    if re.match(r"Rancangan", t, re.I):
        return "Rancangan PUU"
    if re.match(r"Pedoman", t, re.I):
        return "Pedoman"
    return None


def process_file(path: Path, dry_run: bool) -> tuple[int, int, dict[str, int]]:
    changed = 0
    total = 0
    by_new_type: dict[str, int] = {}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        total += 1
        new_lt = classify_title(
            row.get("title_id") or "",
            row.get("ministry_code"),
            row.get("law_type") or "",
        )
        if new_lt and new_lt != row.get("law_type"):
            row["law_type"] = new_lt
            changed += 1
            by_new_type[new_lt] = by_new_type.get(new_lt, 0) + 1
        rows.append(row)
    if changed and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total, changed, by_new_type


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="restrict to specific filenames (no path)")
    args = ap.parse_args()

    files = sorted(LAWS.glob("jdih_*.jsonl"))
    if args.only:
        files = [f for f in files if f.name in args.only]
    grand_total = 0
    grand_changed = 0
    grand_new_types: dict[str, int] = {}
    for f in files:
        total, changed, by_type = process_file(f, args.dry_run)
        if changed:
            print(f"{f.name}: {changed}/{total} reclassified")
            for lt, n in sorted(by_type.items(), key=lambda kv: -kv[1])[:6]:
                print(f"    → {lt}: {n}")
        grand_total += total
        grand_changed += changed
        for lt, n in by_type.items():
            grand_new_types[lt] = grand_new_types.get(lt, 0) + n
    print(f"\nGRAND: {grand_changed:,} / {grand_total:,} reclassified")
    print("Top new law_type counts:")
    for lt, n in sorted(grand_new_types.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {lt:30} {n:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
