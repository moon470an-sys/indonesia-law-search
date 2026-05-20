"""번역 메모리 (Translation Memory).

법령 제목(인니어 → 한국어) 번역 쌍을 SQLite에 누적해 재사용한다.
laws.db와 분리된 자체 DB(data/translation_memory.db)를 쓴다 — 번역 메모리는
크롤 스키마와 수명·관심사가 다르고, 마이그레이션·백업을 독립적으로 다루기 위해서다.

용도:
  - 재번역 멱등성: 같은 title_id는 이미 번역된 결과를 그대로 재사용.
  - 보일러플레이트 제목("Pencabutan ...", "Perubahan atas ..." 류) 중복 제거.
  - 향후 pre-fill 파이프라인의 lookup 백엔드 (지금은 독립 모듈로만 제공).

이 모듈은 일일 자동화 파이프라인을 건드리지 않는다. harvest로 과거 번역을
한 번 적재해두면, 이후 호출자가 tm_lookup/tm_store로 자유롭게 쓸 수 있다.

CLI:
  python -m crawler.translation_memory --harvest      # laws.db에서 번역쌍 적재
  python -m crawler.translation_memory --stats        # 적재 현황
  python -m crawler.translation_memory --lookup "..." # 단건 조회
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

TM_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "translation_memory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tm (
    title_id   TEXT PRIMARY KEY,         -- 인니어 원제목 (정확매칭 키)
    title_ko   TEXT NOT NULL,            -- 한국어 번역
    law_type   TEXT,                     -- 법령 종류 (참고용)
    freq       INTEGER NOT NULL DEFAULT 1,
    first_seen REAL NOT NULL,
    last_seen  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tm_law_type ON tm (law_type);
"""


@contextmanager
def connect(path: Path | str = TM_DB_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def tm_lookup(title_id: str, *, path: Path | str = TM_DB_PATH) -> str | None:
    """정확매칭으로 한국어 번역 반환. 없으면 None. 조회 시 last_seen 갱신은 안 함(읽기 전용)."""
    if not title_id:
        return None
    with connect(path) as conn:
        row = conn.execute("SELECT title_ko FROM tm WHERE title_id = ?", (title_id,)).fetchone()
        return row["title_ko"] if row else None


def tm_store(title_id: str, title_ko: str, law_type: str | None = None,
             *, path: Path | str = TM_DB_PATH) -> None:
    """번역쌍 저장 (upsert). 같은 title_id가 이미 있으면 번역을 갱신하고 freq를 올린다."""
    if not title_id or not title_ko:
        return
    now = time.time()
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO tm (title_id, title_ko, law_type, freq, first_seen, last_seen)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(title_id) DO UPDATE SET
                title_ko  = excluded.title_ko,
                law_type  = COALESCE(excluded.law_type, tm.law_type),
                freq      = tm.freq + 1,
                last_seen = excluded.last_seen
            """,
            (title_id, title_ko, law_type, now, now),
        )


def tm_harvest(laws_db_path: Path | str | None = None,
               *, path: Path | str = TM_DB_PATH) -> dict:
    """laws.db의 번역된 모든 제목을 번역 메모리에 적재.

    laws 외에 articles/attachments의 title_id/title_ko 쌍도 함께 수집한다.
    반환: {"laws": n, "articles": n, "attachments": n, "total_rows": n}.
    """
    # crawler.db에서 DB_PATH를 가져오되, 인자로 override 가능.
    if laws_db_path is None:
        from crawler.db import DB_PATH as laws_db_path  # noqa: N811

    counts = {"laws": 0, "articles": 0, "attachments": 0}
    src = sqlite3.connect(laws_db_path)
    src.row_factory = sqlite3.Row
    now = time.time()
    try:
        with connect(path) as conn:
            for table, has_law_type in (("laws", True), ("articles", False), ("attachments", False)):
                cols = "title_id, title_ko" + (", law_type" if has_law_type else "")
                try:
                    rows = src.execute(
                        f"SELECT {cols} FROM {table} "
                        "WHERE title_ko IS NOT NULL AND title_ko != '' "
                        "AND title_id IS NOT NULL AND title_id != ''"
                    ).fetchall()
                except sqlite3.OperationalError:
                    continue  # 테이블/컬럼 없으면 skip
                for r in rows:
                    lt = r["law_type"] if has_law_type else None
                    conn.execute(
                        """
                        INSERT INTO tm (title_id, title_ko, law_type, freq, first_seen, last_seen)
                        VALUES (?, ?, ?, 1, ?, ?)
                        ON CONFLICT(title_id) DO UPDATE SET
                            title_ko  = excluded.title_ko,
                            law_type  = COALESCE(excluded.law_type, tm.law_type),
                            last_seen = excluded.last_seen
                        """,
                        (r["title_id"], r["title_ko"], lt, now, now),
                    )
                    counts[table] += 1
    finally:
        src.close()
    counts["total_rows"] = sum(counts.values())
    return counts


def tm_stats(path: Path | str = TM_DB_PATH) -> dict:
    if not Path(path).exists():
        return {"total": 0, "by_law_type": {}}
    with connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM tm").fetchone()["n"]
        by_type = {
            r["law_type"] or "(none)": r["n"]
            for r in conn.execute(
                "SELECT law_type, COUNT(*) AS n FROM tm GROUP BY law_type ORDER BY n DESC"
            ).fetchall()
        }
        return {"total": total, "by_law_type": by_type}


def _main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="번역 메모리 관리")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--harvest", action="store_true", help="laws.db에서 번역쌍 적재")
    g.add_argument("--stats", action="store_true", help="적재 현황 출력")
    g.add_argument("--lookup", metavar="TITLE_ID", help="단건 정확매칭 조회")
    args = ap.parse_args(argv)

    if args.harvest:
        counts = tm_harvest()
        print(f"harvested: laws={counts['laws']} articles={counts['articles']} "
              f"attachments={counts['attachments']} (total upserts={counts['total_rows']})")
        st = tm_stats()
        print(f"TM total entries: {st['total']}")
    elif args.stats:
        st = tm_stats()
        print(f"TM total entries: {st['total']}")
        for lt, n in st["by_law_type"].items():
            print(f"  {lt}: {n}")
    elif args.lookup:
        ko = tm_lookup(args.lookup)
        print(ko if ko is not None else "(no match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
