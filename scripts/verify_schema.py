"""Verify the new DB schema after init_db()."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "laws.db"


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    print("=== 테이블 ===")
    for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ):
        print(" ", r["name"])

    print("\n=== FTS5 가상 테이블 ===")
    for r in con.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND sql LIKE '%fts5%' ORDER BY name"
    ):
        print(" ", r["name"])

    print("\n=== 트리거 ===")
    for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
    ):
        print(" ", r["name"])

    print("\n=== 인덱스 ===")
    for r in con.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        print(" ", r["name"])

    print("\n=== 시드 ministries ===")
    for r in con.execute(
        "SELECT code, name_ko, name_id, kind FROM ministries ORDER BY code"
    ):
        print(f"  {r['code']:10} {r['name_ko']:12} ({r['name_id']}) [{r['kind']}]")

    print("\n=== PRAGMA integrity_check ===")
    for r in con.execute("PRAGMA integrity_check"):
        print(" ", r[0])

    print("\n=== 핵심 테이블 컬럼 수 ===")
    for table in (
        "laws", "law_versions", "articles", "addenda", "attachments",
        "amendments", "relations", "court_cases", "legal_terms",
        "popular_searches", "curated_laws",
    ):
        cnt = len(con.execute(f"PRAGMA table_info({table})").fetchall())
        print(f"  {table:18} {cnt} columns")


if __name__ == "__main__":
    main()
