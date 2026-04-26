"""Export ALL remaining pending rows (regardless of slug prefix) into chunks."""
from __future__ import annotations

from pathlib import Path
from crawler import db


def main() -> None:
    out_dir = Path("data/pending/auto")
    out_dir.mkdir(parents=True, exist_ok=True)
    with db.connect() as c:
        rows = c.execute(
            "SELECT id, category, law_type, law_number, title_id, "
            "       promulgation_date, source_url "
            "  FROM laws "
            " WHERE title_ko IS NULL AND source = 'peraturan_go_id' "
            " ORDER BY id DESC"
        ).fetchall()
    if not rows:
        print("none pending")
        return
    chunk_size = 500
    n = (len(rows) + chunk_size - 1) // chunk_size
    print(f"total {len(rows)} → {n} chunks")
    for ci in range(n):
        chunk = rows[ci * chunk_size : (ci + 1) * chunk_size]
        out = out_dir / f"remaining_chunk_{ci+1:03d}.md"
        lines = [
            f"# remaining {ci+1}/{n} ({len(chunk)} rows)",
            "",
            "| id | type | law_number | title_id | promulgation |",
            "|----|------|------------|----------|--------------|",
        ]
        for r in chunk:
            t = (r["title_id"] or "").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {r['id']} | {r['law_type']} | {r['law_number']} | {t} | "
                f"{r['promulgation_date'] or ''} |"
            )
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  wrote {out}")


if __name__ == "__main__":
    main()
