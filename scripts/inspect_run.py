"""Quick post-run inspection: count rows by source/category and show a sample."""
from __future__ import annotations

from crawler import db


def main() -> None:
    with db.connect() as c:
        total = c.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
        print(f"=== TOTAL: {total} laws ===\n")

        print("-- by source --")
        for r in c.execute(
            "SELECT source, COUNT(*) AS n FROM laws GROUP BY source ORDER BY n DESC"
        ):
            print(f"  {r['source']:25} {r['n']}")

        print("\n-- by category --")
        for r in c.execute(
            "SELECT category, COUNT(*) AS n FROM laws GROUP BY category ORDER BY n DESC"
        ):
            print(f"  {r['category']:15} {r['n']}")

        print("\n-- by law_type --")
        for r in c.execute(
            "SELECT law_type, COUNT(*) AS n FROM laws GROUP BY law_type ORDER BY n DESC"
        ):
            print(f"  {r['law_type']:30} {r['n']}")

        print("\n-- sample rows from peraturan_go_id (first 10) --")
        rows = c.execute(
            "SELECT id, category, law_type, law_number, title_id, source_url "
            "FROM laws WHERE source='peraturan_go_id' "
            "ORDER BY id LIMIT 10"
        ).fetchall()
        if not rows:
            print("  (no peraturan_go_id rows)")
        for r in rows:
            print(
                f"  #{r['id']} [{r['category']}/{r['law_type']}] "
                f"{r['law_number']!r}\n      title_id={r['title_id']!r}\n"
                f"      source_url={r['source_url']}"
            )


if __name__ == "__main__":
    main()
