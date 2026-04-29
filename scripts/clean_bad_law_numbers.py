"""Detect and clean garbage in law_number across data/laws/*.jsonl.

The crawlers (and the upstream JDIH sites themselves) sometimes leave
non-numbers in the law_number field — e.g. a stray colon picked up
after "Nomor :", a single Roman numeral letter pulled out of a broken
title ("Undang-undang Nomor B Tahun 2006"), the literal placeholder
"Tidak Diketahui", or the broken-dash artifact "19- Tahun 2026".

This pass replaces those values with one of:
  - "Tahun YYYY"  when the year column is populated
  - ""             otherwise (the UI renders this as "(번호 미상)")

Run: python -X utf8 -m scripts.clean_bad_law_numbers
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "data" / "laws"

BAD_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("broken_dash",       re.compile(r"^\d+-\s+Tahun\s+\d{4}\s*$", re.IGNORECASE)),
    ("trailing_dash",     re.compile(r"^\d+-\s*$")),
    ("single_punct",      re.compile(r"^[\s:;,.\-]+$")),
    ("placeholder_str",   re.compile(r"^(Tidak\s+Diketahui|tidak\s+diketahui|None|null|N/A|TBD)\s*$", re.IGNORECASE)),
    ("nomor_fragment",    re.compile(r"^(mor|nomor|number|no\.?)\s*$", re.IGNORECASE)),
    ("single_letter",     re.compile(r"^[A-Za-z]$")),
    ("roman_only",        re.compile(r"^[IiVvXxLlCcDdMm]{1,4}$")),
    ("repeating_letters", re.compile(r"^([A-Za-z])\1{1,5}$")),  # "lll", "AA"
    ("type_fragment",     re.compile(r"^(PER|KEP|UU|PP|SK|TAP)$")),
]


def is_bad(law_number: str) -> str | None:
    s = (law_number or "").strip()
    if not s:
        return "empty"
    for name, rx in BAD_PATTERNS:
        if rx.match(s):
            return name
    return None


def normalize(row: dict) -> str | None:
    """Return a new law_number when the current one is garbage; otherwise
    None to leave it alone."""
    cur = (row.get("law_number") or "").strip()
    bad = is_bad(cur)
    if not bad:
        return None
    year = row.get("year")
    if year and isinstance(year, int) and 1900 < year < 2100:
        return f"Tahun {year}"
    return ""  # blank — UI renders "(번호 미상)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    grand_changed = 0
    grand_total = 0
    for f in sorted(LAWS.glob("*.jsonl")):
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        n = 0
        for r in rows:
            new = normalize(r)
            if new is not None and new != (r.get("law_number") or ""):
                r["law_number"] = new
                n += 1
        if n:
            print(f"{f.name}: {n:>4}/{len(rows):<5} cleaned")
            if not args.dry_run:
                tmp = f.with_suffix(".jsonl.tmp")
                with tmp.open("w", encoding="utf-8") as fp:
                    for r in rows:
                        fp.write(json.dumps(r, ensure_ascii=False) + "\n")
                tmp.replace(f)
        grand_changed += n
        grand_total += len(rows)
    print(f"\nGRAND: {grand_changed:,} / {grand_total:,} cleaned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
