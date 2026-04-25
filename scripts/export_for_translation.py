"""Export pending laws (title_ko IS NULL) of one hierarchy as chunked MD files,
each suitable for a single sub-agent to translate in one pass.

Usage:
  python scripts/export_for_translation.py --hierarchy uu --chunk-size 500 \
                                            --out-dir data/pending/auto
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from crawler import db


HIERARCHY_PREFIXES: dict[str, set[str]] = {
    "uu":      {"uu", "perppu"},
    "pp":      {"pp"},
    "perpres": {"perpres"},
    "permen":  {
        "permen", "permenkeu", "permenhub", "permendag", "permenhut", "permentan",
        "permenkes", "permenag", "permenkum", "permenkumham", "permensos",
        "permenkop", "permenpera", "permenpkp", "permenpu", "permenkkp",
        "permenpar", "permenkominfo", "permenkomdigi", "permenperin",
        "permendikdasmen", "permenkebud", "permenpan", "permenpanrb",
        "permenkoinfra", "permenpppa", "permenppn", "permenmubpn",
        "permendagri", "permendikbud", "permendikbudristek", "permendiknas",
        "permendiktisaintek", "permenristekdikti", "permenristek", "permenhan",
        "permenaker", "permenakertrans", "permendesa", "permendespdt",
        "permenlu", "permenlh", "permenklhbph", "permenpora", "permenparekraf",
        "permenbudpar", "permensetneg", "permenimipas", "permenham", "permenko",
    },
    "kepmen":  {"kepmen"},
    "perda":   {"perda", "pergub", "perwako", "perwalkot", "perwali", "perbup"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hierarchy", required=True,
                    choices=list(HIERARCHY_PREFIXES))
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--out-dir", default="data/pending/auto")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap total rows (0 = all)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefixes = HIERARCHY_PREFIXES[args.hierarchy]

    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, category, law_type, law_number, title_id, "
            "       promulgation_date, source_url "
            "  FROM laws "
            " WHERE title_ko IS NULL AND source = 'peraturan_go_id' "
            " ORDER BY year DESC, id DESC"
        ).fetchall()

    filtered = []
    for r in rows:
        path_part = r["source_url"].split("peraturan.go.id", 1)[-1]
        m = re.match(r"^/id/([a-z]+)", path_part, re.IGNORECASE)
        if m and m.group(1).lower() in prefixes:
            filtered.append(r)

    if args.limit:
        filtered = filtered[: args.limit]

    if not filtered:
        print(f"no pending rows for {args.hierarchy}")
        return 0

    n_chunks = (len(filtered) + args.chunk_size - 1) // args.chunk_size
    print(f"{args.hierarchy}: {len(filtered)} pending rows → {n_chunks} chunks")

    for ci in range(n_chunks):
        chunk = filtered[ci * args.chunk_size : (ci + 1) * args.chunk_size]
        out = out_dir / f"{args.hierarchy}_chunk_{ci + 1:03d}.md"

        lines = [
            f"# {args.hierarchy.upper()} translation chunk {ci + 1}/{n_chunks} ({len(chunk)} rows)",
            "",
            "| id | type | law_number | title_id | promulgation |",
            "|----|------|------------|----------|--------------|",
        ]
        for r in chunk:
            title = (r["title_id"] or "").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {r['id']} | {r['law_type']} | {r['law_number']} | "
                f"{title} | {r['promulgation_date'] or ''} |"
            )
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  wrote {out} ({len(chunk)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
