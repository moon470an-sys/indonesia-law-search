"""Quick DB verification script — run after crawl + translation import."""
from __future__ import annotations

from crawler import db


def main() -> None:
    with db.connect() as c:
        print("--- 전체 행 ---")
        rows = c.execute(
            "SELECT id, ministry_code, law_number, title_ko, categories "
            "FROM laws ORDER BY id"
        ).fetchall()
        for r in rows:
            print(f"  id={r['id']} {r['ministry_code']} {r['law_number']}")
            print(f"    title_ko={r['title_ko']}")
            print(f"    categories={r['categories']}")

        cnt_pending = c.execute(
            "SELECT COUNT(*) FROM laws WHERE title_ko IS NULL"
        ).fetchone()[0]
        cnt_total = c.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
        print(f"\n총 {cnt_total}건 / 미번역 {cnt_pending}건")

        for query in ("가격", "ICP", "원유"):
            print(f"\n--- FTS5 검색: '{query}' ---")
            results = c.execute(
                """
                SELECT laws.id, laws.title_ko
                  FROM laws_fts
                  JOIN laws ON laws.id = laws_fts.rowid
                 WHERE laws_fts MATCH ?
                 ORDER BY rank
                """,
                (query,),
            ).fetchall()
            for r in results:
                print(f"  {r['id']}: {r['title_ko']}")
            if not results:
                print("  (결과 없음)")


if __name__ == "__main__":
    main()
