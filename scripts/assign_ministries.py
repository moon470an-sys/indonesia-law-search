"""Re-assign ministry_code/ministry_name_ko on every law row based on its
peraturan.go.id slug type (UU/PP/Perpres get NULL ministry).

Run after a bulk crawl, before Pages deploy.
"""
from __future__ import annotations

import re
import sys

from crawler import db


SLUG_RE = re.compile(r"^/id/([a-z]+)", re.IGNORECASE)

# slug → (ministry_code, ministry_name_ko). None code = NULL out.
MAPPING: dict[str, tuple[str | None, str | None]] = {
    # National-level (no ministry — issued by parliament/president):
    "uu":               (None, None),
    "perppu":           (None, None),
    "pp":               (None, None),
    "perpres":          (None, None),
    "tap":              (None, None),

    # Permen / Kepmen by ministry slug
    "permenkeu":        ("kemenkeu",        "재무부"),
    "permenhub":        ("kemenhub",        "교통부"),
    "permendag":        ("kemendag",        "무역부"),
    "permenhut":        ("kemenhut",        "산림부"),
    "permentan":        ("kementan",        "농업부"),
    "permenkes":        ("kemenkes",        "보건부"),
    "permenag":         ("kemenag",         "종교부"),
    "permenkum":        ("kumham",          "법무인권부"),
    "permenkumham":     ("kumham",          "법무인권부"),
    "permensos":        ("kemensos",        "사회부"),
    "permenkop":        ("kemenkopukm",     "협동조합·중소기업부"),
    "permenpera":       ("kemenpera",       "주거공급부"),
    "permenpkp":        ("kemenpkp",        "주거단지부"),
    "permenpu":         ("kemenpu",         "공공사업부"),
    "permenkkp":        ("kemenkkp",        "해양수산부"),
    "permenpar":        ("kemenpar",        "관광부"),
    "permenkominfo":    ("kemenkominfo",    "통신정보부"),
    "permenkomdigi":    ("kemenkomdigi",    "통신디지털부"),
    "permenperin":      ("kemenperin",      "산업부"),
    "permendikdasmen":  ("kemendikdasmen",  "초중등교육부"),
    "permenkebud":      ("kemenkebud",      "문화부"),
    "permenpan":        ("kemenpanrb",      "행정개혁부"),
    "permenpanrb":      ("kemenpanrb",      "행정개혁부"),
    "permendagri":      ("kemendagri",      "내무부"),
    "permendikbud":     ("kemendikbud",     "교육문화부"),
    "permendikbudristek":("kemendikbud",    "교육문화부"),
    "permendiknas":     ("kemendikbud",     "교육문화부"),
    "permendiktisaintek":("kemendiktisaintek","고등과학기술부"),
    "permenristekdikti":("kemenristek",     "연구기술부"),
    "permenristek":     ("kemenristek",     "연구기술부"),
    "permenhan":        ("kemenhan",        "국방부"),
    "permenaker":       ("kemenaker",       "인력부"),
    "permenakertrans":  ("kemenaker",       "인력부"),
    "permendesa":       ("kemendesa",       "마을부"),
    "permendespdt":     ("kemendesa",       "마을부"),
    "permenlu":         ("kemenlu",         "외무부"),
    "permenlh":         ("kemenlh",         "환경부"),
    "permenklhbph":     ("kemenlh",         "환경부"),
    "permenpora":       ("kemenpora",       "청년체육부"),
    "permenparekraf":   ("kemenparekraf",   "관광·창조경제부"),
    "permenbudpar":     ("kemenparekraf",   "관광·창조경제부"),
    "permensetneg":     ("kemensetneg",     "국가비서실"),
    "permenimipas":     ("kemenimipas",     "이민·교정부"),
    "permenham":        ("kumham",          "법무인권부"),
    "permenko":         ("kemenko",         "조정부"),
    "permentrans":      ("kemenaker",       "인력부"),
    "permenkoinfra":    ("kemenkoinfra",    "인프라·지역개발 조정부"),
    "permenpppa":       ("kemenpppa",       "여성·아동권익부"),
    "permenppn":        ("bappenas",        "국가개발기획부"),
    "permenmubpn":      ("atrbpn",          "토지·공간행정부"),

    # Generic Permen / Kepmen — keep kumham as fallback
    "permen":           ("kumham",          "법무인권부"),
    "kepmen":           ("kumham",          "법무인권부"),

    # Perda 패밀리는 region 단위 — ministry NULL
    "perda":            (None, None),
    "pergub":           (None, None),
    "perwako":          (None, None),
    "perwalkot":        (None, None),
    "perwali":          (None, None),
    "perbup":           (None, None),
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    counts: dict[str, int] = {}
    unknown: dict[str, int] = {}
    null_count = 0

    with db.connect() as conn:
        # Re-apply ministries seed (idempotent INSERT OR IGNORE)
        conn.executescript(db.SCHEMA)

        rows = conn.execute(
            "SELECT id, source_url FROM laws WHERE source = 'peraturan_go_id'"
        ).fetchall()

        updates: list[tuple[str | None, str | None, int]] = []
        for r in rows:
            url = r["source_url"]
            m = SLUG_RE.search(url.replace("https://peraturan.go.id", ""))
            if not m:
                unknown.setdefault("(no slug)", 0)
                unknown["(no slug)"] += 1
                continue
            slug_type = m.group(1).lower()
            if slug_type in MAPPING:
                code, name = MAPPING[slug_type]
                updates.append((code, name, r["id"]))
                key = code or "(NULL)"
                counts[key] = counts.get(key, 0) + 1
                if code is None:
                    null_count += 1
            else:
                unknown[slug_type] = unknown.get(slug_type, 0) + 1

        print(f"Targeted updates: {len(updates)} rows")
        print(f"Mapped to NULL ministry: {null_count}")
        for code, n in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {code:20} {n}")
        if unknown:
            print("Unknown slugs (left untouched):")
            for s, n in sorted(unknown.items(), key=lambda x: -x[1]):
                print(f"  {s:25} {n}")

        if dry:
            print("\n(dry-run; no DB writes)")
            return 0

        conn.executemany(
            "UPDATE laws SET ministry_code = ?, ministry_name_ko = ? WHERE id = ?",
            updates,
        )
        print(f"\nApplied {len(updates)} updates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
