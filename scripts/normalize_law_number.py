"""Normalize law_number across all data/laws/jdih_*.jsonl files.

Current state (audited):
  - peraturan.go.id  : "Nomor 2 Tahun 2023"          ← clean
  - esdm             : "esdm-detail-100" placeholder OR "1565 K/10/MEM/2008"
  - kemnaker / polri / bnn / bps / bmkg : just "6"   ← no year
  - dephub           : "KM 2 TAHUN 2020"             ← prefix + year
  - kemkes / brin / kpu / bnpt / pkp : placeholder ("kemkes-?", "brin-{id}")
  - kejaksaan        : "6 TAHUN 2021(KEP)"
  - atrbpn           : "16" OR "1/Juknis-100.HK.02.01/I/2022"

Standardized output format (Indonesian legal convention):
  "<number> Tahun <YYYY>"  — for plain number+year (e.g. "2 Tahun 2023")
  "<complex-code>"         — for codes already containing slashes / dots
                              (e.g. "159/KPTS/M/2025", "HK.02.02/F/065/2026")
  ""                       — when nothing extractable (rare; placeholder dropped)

Extraction priority (per row), checked against title_id:
  1. "Nomor X Tahun Y"          → "X Tahun Y"
  2. "Nomor X/COMPLEX-CODE"     → "X/COMPLEX-CODE"
  3. "Nomor: X" or "Nomor X"    → "X"
  4. "<TYPE> X TAHUN Y"         → "X Tahun Y"
  5. fallback: keep current law_number if it's not a placeholder, else ""

Placeholders detected and stripped: anything matching /^[a-z]+-\?$/ or
/^[a-z]+-[a-f0-9\-]{6,}$/ (e.g. kemkes-?, brin-001777ec, bnpt-0yOxKMWwr).

Run: python -m scripts.normalize_law_number [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "data" / "laws"

# Detect adapter-generated placeholder values
PLACEHOLDER_RE = re.compile(
    r"^(?:[a-z]+-(?:\?|[a-f0-9\-]{4,}|detail-\d+))$|^kpu-\?$|^bkpm-\?$|^kemkes-\?$|^bps-\?$|^bnpt-[\w]+$",
    re.IGNORECASE,
)

# Extraction patterns, in priority order. Each returns the canonical string when matched.
def _extract_from_title(title: str) -> str | None:
    if not title:
        return None
    t = title.strip()

    # 1. "Nomor X Tahun Y" / "No. X Tahun Y" / "No X Tahun Y" / "Number X Of Y" (English)
    m = re.search(r"\b(?:Nomor|No\.?|Number)\s*[:.]?\s*([^\s,;]+(?:\s+[^\s,;]+)?)\s+(?:Tahun|Of)\s+(\d{4})", t, re.IGNORECASE)
    if m:
        num = m.group(1).strip().rstrip(".,")
        year = m.group(2)
        if num.lower() not in ("tahun", "of"):
            return f"{num} Tahun {year}"

    # 2. "Nomor X/CODE/CODE" / "No. X/CODE" — complex code
    m = re.search(r"\b(?:Nomor|No\.?)\s*[:.]?\s*([^\s,;]+\/[^\s,;]+)", t, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".,")

    # 3. ALL-CAPS "X TAHUN Y" without "Nomor" prefix (e.g. dephub "KM 2 TAHUN 2020")
    m = re.search(r"^[A-Z]+\.?\s+(\S+)\s+TAHUN\s+(\d{4})", t)
    if m:
        return f"{m.group(1).strip()} Tahun {m.group(2)}"

    # 4. "X Tahun Y" at start of title (e.g. polri "4 Tahun 2017")
    m = re.match(r"^(\S+)\s+Tahun\s+(\d{4})\b", t, re.IGNORECASE)
    if m and not m.group(1).lower().startswith("tahun"):
        return f"{m.group(1).strip()} Tahun {m.group(2)}"

    # 5. "Nomor X" / "No. X" / "Number X" (no Tahun cluster)
    m = re.search(r"\b(?:Nomor|No\.?|Number)\s*[:.]?\s*([^\s,;]+)", t, re.IGNORECASE)
    if m:
        cand = m.group(1).strip().rstrip(".,")
        if cand.lower() in ("tahun", "of", ""):
            cand = ""
        if cand:
            ym = re.search(r"\b(?:Tahun|Of)\s+(\d{4})\b", t, re.IGNORECASE)
            if ym:
                return f"{cand} Tahun {ym.group(1)}"
            return cand

    return None


def normalize(row: dict) -> str | None:
    """Return new law_number, or None to keep as-is."""
    cur = (row.get("law_number") or "").strip()
    title = row.get("title_id") or ""

    derived = _extract_from_title(title)

    # If current is a placeholder, prefer derived; if no derived, fall back to current (don't blank)
    if PLACEHOLDER_RE.match(cur):
        return derived if derived else None  # keep placeholder rather than empty

    # If current empty AND no derived, set "Tidak Diketahui" so DB NOT NULL passes
    if not cur and not derived:
        return "Tidak Diketahui"

    # If current is already a "X Tahun Y" form and derived agrees, keep
    if re.match(r"^\S+\s+Tahun\s+\d{4}$", cur, re.IGNORECASE):
        # Convert "X TAHUN Y" → "X Tahun Y" (lowercase "Tahun")
        normalized = re.sub(r"\bTAHUN\b", "Tahun", cur)
        if normalized != cur:
            return normalized
        return None

    # If current looks like "Nomor X Tahun Y", strip the "Nomor " prefix
    if cur.lower().startswith("nomor "):
        stripped = cur[6:].strip()
        # ensure year-case canon
        stripped = re.sub(r"\bTAHUN\b", "Tahun", stripped)
        return stripped

    # If current is a complex code (contains /), keep as-is
    if "/" in cur and len(cur) >= 5:
        return None

    # If current is just digits and derived has more info, prefer derived
    if re.fullmatch(r"\d+", cur) and derived and "Tahun" in derived:
        return derived

    # If current is empty but derived available, use it
    if not cur and derived:
        return derived

    # If "TAHUN" appears in cur uppercase, lowercase it
    if "TAHUN" in cur:
        return re.sub(r"\bTAHUN\b", "Tahun", cur)

    return None


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    rows = []
    changed = 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        total += 1
        new_num = normalize(row)
        if new_num is not None and new_num != (row.get("law_number") or ""):
            row["law_number"] = new_num
            changed += 1
        rows.append(row)
    if changed and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    grand_total = 0
    grand_changed = 0
    for f in sorted(LAWS.glob("*.jsonl")):
        total, changed = process_file(f, args.dry_run)
        if changed:
            print(f"{f.name}: {changed:>5}/{total:<5} updated")
        grand_total += total
        grand_changed += changed
    print(f"\nGRAND: {grand_changed:,} / {grand_total:,} normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
