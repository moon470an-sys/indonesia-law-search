"""Quick post-enrich inspection."""
from __future__ import annotations

from crawler import db


def main() -> None:
    with db.connect() as c:
        precise = c.execute(
            "SELECT COUNT(*) FROM laws "
            "WHERE source='peraturan_go_id' "
            "  AND promulgation_date IS NOT NULL "
            "  AND promulgation_date NOT LIKE '____-01-01'"
        ).fetchone()[0]
        with_enact = c.execute(
            "SELECT COUNT(*) FROM laws "
            "WHERE source='peraturan_go_id' AND enactment_date IS NOT NULL"
        ).fetchone()[0]
        relations = c.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        total_pgid = c.execute(
            "SELECT COUNT(*) FROM laws WHERE source='peraturan_go_id'"
        ).fetchone()[0]

        print(f"peraturan_go_id rows:          {total_pgid:>6}")
        print(f"  precise promulgation_date:   {precise:>6}")
        print(f"  enactment_date populated:    {with_enact:>6}")
        print(f"relations rows:                {relations:>6}")

        print("\n-- by hierarchy (UU only filter) --")
        for r in c.execute(
            "SELECT law_type, COUNT(*) AS n, "
            "  SUM(CASE WHEN promulgation_date NOT LIKE '____-01-01' THEN 1 ELSE 0 END) AS p, "
            "  SUM(CASE WHEN enactment_date IS NOT NULL THEN 1 ELSE 0 END) AS e "
            "FROM laws WHERE source='peraturan_go_id' "
            "GROUP BY law_type "
            "ORDER BY n DESC LIMIT 15"
        ):
            print(f"  {r['law_type']:25} n={r['n']:>5} promul={r['p']:>5} enact={r['e']:>5}")

        print("\n-- sample 5 UU rows with new dates --")
        for r in c.execute(
            "SELECT id, law_number, title_id, enactment_date, promulgation_date, status "
            "FROM laws WHERE source='peraturan_go_id' AND law_type='UU' "
            "  AND promulgation_date IS NOT NULL AND promulgation_date NOT LIKE '____-01-01' "
            "LIMIT 5"
        ):
            print(f"  #{r['id']} {r['law_number']}")
            print(f"    title_id={r['title_id'][:80]!r}")
            print(f"    enact={r['enactment_date']}  promul={r['promulgation_date']}  status={r['status']}")


if __name__ == "__main__":
    main()
