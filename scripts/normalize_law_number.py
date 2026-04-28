"""Normalize law_number across all data/laws/*.jsonl files.

Strategy (in priority order, per row):
  1. Title-based extraction. Indonesian regulation titles routinely
     start with the literal "Nomor <X>/CODE..." or "Nomor <X> Tahun
     <Y>" — the most authoritative source for the canonical number.
  2. Strip the trailing " Tahun YYYY" suffix when the leading slug
     already encodes the year (so "144-pmk-07-2009 Tahun 2009" loses
     its tail).
  3. Decode slug-style numbers (lowercase + hyphens, the form used by
     URL slugs): convert hyphens to slashes/dots, uppercase known
     ministry tokens. Heuristic — when uncertain, leave as-is.
  4. Empty / placeholder strings get an extracted value or
     "Tidak Diketahui".

The script writes back to JSONL in place. Run scripts.build_db
afterwards to refresh laws.db.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "data" / "laws"

PLACEHOLDER_RE = re.compile(
    r"^(?:[a-z]+-(?:\?|[a-f0-9\-]{4,}|detail-\d+))$|^(?:kpu|bkpm|kemkes|bps|bnpt)-\?$",
    re.IGNORECASE,
)

# Tokens we always uppercase when found inside a slug-style number.
# Roman numerals and ministry abbreviations that are conventionally CAPS.
SLUG_UPPER_TOKENS = {
    "pmk", "kmk", "pp", "uu", "perpres", "kepmen",
    "permen", "permendag", "permenkeu", "permenkes", "permenhut", "permentan",
    "permenkominfo", "permenaker", "permenpan", "permenperin", "permenpora",
    "menhut", "menlhk", "mendag", "menkeu", "menkes", "mentan", "mendagri",
    "menpan", "menag", "kemnaker", "kemenkeu", "kemenpora", "kemkes",
    "kemenkop", "kemendag", "kemendikbud", "kemenhub", "kemensos", "kemenag",
    "kapolri", "djbc", "djpb", "djpu", "djpl", "djka",
    "esdm", "mb", "mem", "hk", "kp", "kpt", "kep", "kpts",
    "rb", "kpa", "ses", "sj", "set", "setjen", "setneg",
    "skj", "sm", "ind", "pkp", "ppa", "lhk",
    "m", "p", "per", "kpts",
}
ROMAN_RE = re.compile(r"^(?:i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3}|xiv|xv|xvi{0,3}|xix|xx|xxi{0,3}|xxiv|xxv)$", re.IGNORECASE)


# Phrases that indicate the upcoming "Nomor X" refers to a DIFFERENT law
# (the one being amended/repealed/cited), not the law in this row.
_REFERENCE_PREFIX_RE = re.compile(
    r"(?:Perubahan|Pencabutan|Atas|Sebagaimana|Mencabut|Menetapkan|Mengubah)\b"
    r"[\s\S]{0,40}$",
    re.IGNORECASE,
)


def _is_reference_match(title: str, match_start: int) -> bool:
    """True if the "Nomor X" we just matched is preceded by a phrase like
    'Perubahan Atas …' (i.e. it points at the amended law, not this one)."""
    head = title[: match_start].rstrip()
    if not head:
        return False
    return bool(_REFERENCE_PREFIX_RE.search(head[-60:]))


def _title_extract(title: str, year: int | None) -> str | None:
    """Try the canonical "Nomor X..." patterns inside title_id.

    Skips matches that follow "Perubahan Atas / Pencabutan ..." since
    those reference the amended law, not the current one. Prefers a
    match whose 4-digit year matches the row's `year` column."""
    if not title:
        return None
    t = title.strip()

    candidates: list[tuple[str, int | None, int]] = []

    # Pattern A: "Nomor X Tahun YYYY"
    for m in re.finditer(
        r"\b(?:Nomor|No\.?|Number)\s*[:.]?\s*([0-9][\w./-]*?)\s+(?:Tahun|Of)\s+(\d{4})",
        t, re.IGNORECASE,
    ):
        if _is_reference_match(t, m.start()):
            continue
        cand = f"{m.group(1).strip()} Tahun {m.group(2)}"
        candidates.append((cand, int(m.group(2)), m.start()))

    # Pattern B: "Nomor X.Y/CODE/.../YYYY" composite
    for m in re.finditer(
        r"\b(?:Nomor|No\.?)\s*[:.]?\s*([0-9][\w.]*\/[\w.]+(?:\/[\w.]+){1,4}\/(\d{4}))",
        t, re.IGNORECASE,
    ):
        if _is_reference_match(t, m.start()):
            continue
        cand = m.group(1).rstrip(".,;)")
        candidates.append((cand, int(m.group(2)), m.start()))

    # Pattern C: "Nomor X/CODE..." without trailing year
    for m in re.finditer(
        r"\b(?:Nomor|No\.?)\s*[:.]?\s*([0-9][\w./-]*\/[\w./-]+(?:\/[\w./-]+){1,4})",
        t, re.IGNORECASE,
    ):
        if _is_reference_match(t, m.start()):
            continue
        cand = m.group(1).rstrip(".,;)")
        if "/" in cand:
            candidates.append((cand, None, m.start()))

    if not candidates:
        return None

    # Prefer ones whose year aligns with the row's year column
    if year is not None:
        for cand, cy, _ in candidates:
            if cy == year:
                return cand
    # Otherwise the first non-reference match
    return candidates[0][0]


def _strip_redundant_year_suffix(s: str, year: int | None) -> str:
    """Drop trailing " Tahun YYYY" when the leading slug already ends in YYYY."""
    m = re.match(r"^(.*?)\s+Tahun\s+(\d{4})\s*$", s, re.IGNORECASE)
    if not m:
        return s
    head, yr = m.group(1).strip(), m.group(2)
    # If the head already ends in -YYYY or /YYYY (same year), drop the tail
    if re.search(rf"[-/]{yr}$", head):
        return head
    return s


def _decode_slug(s: str) -> str:
    """Convert "144-pmk-07-2009" → "144/PMK.07/2009"-style canonical form.

    Conservative: only acts on lowercase-plus-hyphen patterns whose first
    segment is digits and last segment is a 4-digit year. Other slugs are
    returned unchanged so we don't break already-canonical strings."""
    if not re.match(r"^[a-z0-9]([\w.\-/]*[a-z0-9])?$", s.strip(), re.IGNORECASE):
        return s
    if "-" not in s or "/" in s:
        return s

    parts = s.split("-")
    if len(parts) < 3:
        return s
    if not parts[0].lstrip("0").isdigit() and not (
        len(parts[0]) == 1 and parts[0].lower() in ("p", "m")
    ):
        # Doesn't start with a recognizable number/prefix
        return s
    if not re.fullmatch(r"\d{4}", parts[-1]):
        return s

    out_parts: list[str] = []
    i = 0
    while i < len(parts):
        tok = parts[i]
        if i == 0 and tok.lower() == "p" and len(parts) > 1 and parts[1].isdigit():
            # "p-56-menhut-ii-2014" → "P.56/..."
            out_parts.append(f"P.{parts[1]}")
            i += 2
            continue
        if i == 0 and tok.lower() == "m" and len(parts) > 2 and parts[1].isalpha():
            # "m-dag-per-1-2017" — actually rare; "01-m-dag-per-1-2017" more common
            pass

        # Try to merge "{ALPHA}-{2DIGIT}" pairs into "ALPHA.NN" (PMK style)
        if (
            tok.isalpha()
            and i + 1 < len(parts)
            and re.fullmatch(r"\d{2,3}", parts[i + 1])
            and tok.lower() in {"pmk", "kmk", "pmk."}
        ):
            out_parts.append(f"{tok.upper()}.{parts[i + 1]}")
            i += 2
            continue

        # Roman numeral? uppercase
        if ROMAN_RE.match(tok):
            out_parts.append(tok.upper())
            i += 1
            continue

        # Known token? uppercase
        if tok.lower() in SLUG_UPPER_TOKENS:
            out_parts.append(tok.upper())
            i += 1
            continue

        # Pure digit?
        if tok.isdigit():
            out_parts.append(tok)
            i += 1
            continue

        # Mixed letters — uppercase if all lower
        if tok.islower():
            out_parts.append(tok.upper())
        else:
            out_parts.append(tok)
        i += 1

    # Insert "M-{X}" combination: if we have e.g. ["1", "M", "DAG", "PER", "1", "2017"]
    # we want "1/M-DAG/PER/1/2017". The "M" and following ministry token glue.
    glued: list[str] = []
    j = 0
    while j < len(out_parts):
        tok = out_parts[j]
        if (
            tok == "M"
            and j + 1 < len(out_parts)
            and out_parts[j + 1].isalpha()
            and len(out_parts[j + 1]) <= 6
            and out_parts[j + 1] != "M"
        ):
            glued.append(f"M-{out_parts[j + 1]}")
            j += 2
            continue
        glued.append(tok)
        j += 1

    return "/".join(glued)


def _broken_dash(s: str) -> bool:
    """e.g. "18- Tahun 2026" — the part after the dash is missing/empty."""
    return bool(re.match(r"^\d+-\s+Tahun\s+\d{4}$", s.strip(), re.IGNORECASE))


def normalize(row: dict) -> str | None:
    """Return a new law_number, or None to keep the existing value.

    Order: clean up the existing value first (slug decode, strip
    redundant "Tahun YYYY", drop "Nomor " prefix). Only fall back to
    title-based extraction when the current value is empty, a known
    placeholder, or a broken-dash artefact. This prevents pulling the
    "Perubahan Atas Peraturan ... Nomor X Tahun Y" reference into the
    current row."""
    cur = (row.get("law_number") or "").strip()
    title = row.get("title_id") or ""
    year = row.get("year")

    # Empty / placeholder / broken — try title extraction
    if not cur or PLACEHOLDER_RE.match(cur) or _broken_dash(cur):
        derived = _title_extract(title, year)
        if derived:
            return derived
        if not cur:
            return "Tidak Diketahui"
        return None  # leave placeholder for phase-2 re-fetch

    # Strip redundant " Tahun YYYY" tail
    new = _strip_redundant_year_suffix(cur, year)

    # Strip leading "Nomor "
    if new.lower().startswith("nomor "):
        new = new[6:].strip()

    # Lowercase "tahun" canonicalisation
    new = re.sub(r"\bTAHUN\b", "Tahun", new)

    # Slug decode (best-effort)
    decoded = _decode_slug(new)
    if decoded != new:
        new = decoded

    # Trim
    new = re.sub(r"\s+", " ", new).strip()

    if new != cur:
        return new
    return None


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    rows: list[dict] = []
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
