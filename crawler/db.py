"""SQLite + FTS5 schema for Indonesian law metadata."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "laws.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS laws (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ministry_code   TEXT NOT NULL,
    ministry_name_ko TEXT NOT NULL,
    law_type        TEXT,
    law_number      TEXT NOT NULL,
    title_id        TEXT NOT NULL,
    title_ko        TEXT,
    summary_ko      TEXT,
    issuance_date   TEXT,
    effective_date  TEXT,
    status          TEXT,
    pdf_url         TEXT,
    source_url      TEXT NOT NULL,
    categories      TEXT,
    keywords        TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ministry_code, law_number)
);

CREATE INDEX IF NOT EXISTS idx_laws_ministry ON laws (ministry_code);
CREATE INDEX IF NOT EXISTS idx_laws_issuance ON laws (issuance_date DESC);
CREATE INDEX IF NOT EXISTS idx_laws_pending  ON laws (title_ko) WHERE title_ko IS NULL;

CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(
    title_id,
    title_ko,
    summary_ko,
    keywords,
    content='laws',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS laws_ai AFTER INSERT ON laws BEGIN
    INSERT INTO laws_fts (rowid, title_id, title_ko, summary_ko, keywords)
    VALUES (new.id, new.title_id, new.title_ko, new.summary_ko, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS laws_ad AFTER DELETE ON laws BEGIN
    INSERT INTO laws_fts (laws_fts, rowid, title_id, title_ko, summary_ko, keywords)
    VALUES ('delete', old.id, old.title_id, old.title_ko, old.summary_ko, old.keywords);
END;

CREATE TRIGGER IF NOT EXISTS laws_au AFTER UPDATE ON laws BEGIN
    INSERT INTO laws_fts (laws_fts, rowid, title_id, title_ko, summary_ko, keywords)
    VALUES ('delete', old.id, old.title_id, old.title_ko, old.summary_ko, old.keywords);
    INSERT INTO laws_fts (rowid, title_id, title_ko, summary_ko, keywords)
    VALUES (new.id, new.title_id, new.title_ko, new.summary_ko, new.keywords);
END;
"""


@contextmanager
def connect(path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path | str = DB_PATH) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def upsert_law(conn: sqlite3.Connection, row: dict) -> int:
    """Insert or update a law row by (ministry_code, law_number).

    Existing translations (title_ko, summary_ko, categories, keywords) are
    preserved when re-crawling overwrites metadata.
    """
    if isinstance(row.get("categories"), (list, tuple)):
        row["categories"] = json.dumps(row["categories"], ensure_ascii=False)
    if isinstance(row.get("keywords"), (list, tuple)):
        row["keywords"] = json.dumps(row["keywords"], ensure_ascii=False)

    row.setdefault("updated_at", datetime.utcnow().isoformat(timespec="seconds"))

    sql = """
    INSERT INTO laws (
        ministry_code, ministry_name_ko, law_type, law_number,
        title_id, title_ko, summary_ko,
        issuance_date, effective_date, status,
        pdf_url, source_url, categories, keywords, updated_at
    ) VALUES (
        :ministry_code, :ministry_name_ko, :law_type, :law_number,
        :title_id, :title_ko, :summary_ko,
        :issuance_date, :effective_date, :status,
        :pdf_url, :source_url, :categories, :keywords, :updated_at
    )
    ON CONFLICT (ministry_code, law_number) DO UPDATE SET
        law_type        = excluded.law_type,
        title_id        = excluded.title_id,
        issuance_date   = excluded.issuance_date,
        effective_date  = excluded.effective_date,
        status          = excluded.status,
        pdf_url         = excluded.pdf_url,
        source_url      = excluded.source_url,
        updated_at      = excluded.updated_at
    """
    cur = conn.execute(sql, {
        "title_ko": None, "summary_ko": None,
        "categories": None, "keywords": None,
        "law_type": None, "issuance_date": None,
        "effective_date": None, "status": None,
        "pdf_url": None,
        **row,
    })
    if cur.lastrowid:
        return cur.lastrowid
    found = conn.execute(
        "SELECT id FROM laws WHERE ministry_code=? AND law_number=?",
        (row["ministry_code"], row["law_number"]),
    ).fetchone()
    return found["id"]


def pending_translations(conn: sqlite3.Connection, ministry_code: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM laws WHERE title_ko IS NULL"
    params: tuple = ()
    if ministry_code:
        sql += " AND ministry_code = ?"
        params = (ministry_code,)
    sql += " ORDER BY issuance_date DESC, id DESC"
    return conn.execute(sql, params).fetchall()


def apply_translation(conn: sqlite3.Connection, *, law_id: int, title_ko: str,
                      summary_ko: str | None, categories: Iterable[str] | None,
                      keywords: Iterable[str] | None) -> None:
    conn.execute(
        """
        UPDATE laws
           SET title_ko   = ?,
               summary_ko = ?,
               categories = ?,
               keywords   = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            title_ko,
            summary_ko,
            json.dumps(list(categories), ensure_ascii=False) if categories else None,
            json.dumps(list(keywords), ensure_ascii=False) if keywords else None,
            law_id,
        ),
    )


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
