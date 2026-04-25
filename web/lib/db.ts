import path from "node:path";
import { DatabaseSync, type SQLInputValue } from "node:sqlite";

const DB_PATH =
  process.env.LAWS_DB_PATH ??
  path.resolve(process.cwd(), "..", "data", "laws.db");

let _db: DatabaseSync | null = null;

function db(): DatabaseSync {
  if (_db) return _db;
  _db = new DatabaseSync(DB_PATH, { readOnly: true });
  return _db;
}

export type Law = {
  id: number;
  ministry_code: string;
  ministry_name_ko: string;
  law_type: string | null;
  law_number: string;
  title_id: string;
  title_ko: string | null;
  summary_ko: string | null;
  issuance_date: string | null;
  effective_date: string | null;
  status: string | null;
  pdf_url: string | null;
  source_url: string;
  categories: string[] | null;
  keywords: string[] | null;
};

function parseList(raw: unknown): string[] | null {
  if (typeof raw !== "string" || !raw) return null;
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

function hydrate(row: Record<string, unknown>): Law {
  return {
    ...(row as unknown as Law),
    categories: parseList(row.categories),
    keywords: parseList(row.keywords),
  };
}

export function listRecent(limit = 20): Law[] {
  const rows = db()
    .prepare(
      `SELECT * FROM laws
       WHERE title_ko IS NOT NULL
       ORDER BY issuance_date DESC, id DESC
       LIMIT ?`,
    )
    .all(limit) as Record<string, unknown>[];
  return rows.map(hydrate);
}

export function getById(id: number): Law | null {
  const row = db()
    .prepare("SELECT * FROM laws WHERE id = ?")
    .get(id) as Record<string, unknown> | undefined;
  return row ? hydrate(row) : null;
}

export function listAllIds(): number[] {
  return (
    db()
      .prepare("SELECT id FROM laws WHERE title_ko IS NOT NULL")
      .all() as { id: number }[]
  ).map((r) => r.id);
}

export function listMinistries(): { code: string; name_ko: string; count: number }[] {
  return db()
    .prepare(
      `SELECT ministry_code AS code, ministry_name_ko AS name_ko, COUNT(*) AS count
         FROM laws
        WHERE title_ko IS NOT NULL
     GROUP BY ministry_code, ministry_name_ko
     ORDER BY count DESC`,
    )
    .all() as { code: string; name_ko: string; count: number }[];
}

export function search(opts: {
  q?: string;
  ministry?: string;
  limit?: number;
}): Law[] {
  const limit = opts.limit ?? 50;
  let sql: string;
  let params: SQLInputValue[];

  if (opts.q && opts.q.trim()) {
    const q = ftsQuery(opts.q.trim());
    if (opts.ministry) {
      sql = `
        SELECT laws.*
          FROM laws_fts
          JOIN laws ON laws.id = laws_fts.rowid
         WHERE laws_fts MATCH ?
           AND laws.title_ko IS NOT NULL
           AND laws.ministry_code = ?
         ORDER BY rank
         LIMIT ?
      `;
      params = [q, opts.ministry, limit];
    } else {
      sql = `
        SELECT laws.*
          FROM laws_fts
          JOIN laws ON laws.id = laws_fts.rowid
         WHERE laws_fts MATCH ?
           AND laws.title_ko IS NOT NULL
         ORDER BY rank
         LIMIT ?
      `;
      params = [q, limit];
    }
  } else if (opts.ministry) {
    sql = `
      SELECT * FROM laws
       WHERE title_ko IS NOT NULL
         AND ministry_code = ?
       ORDER BY issuance_date DESC, id DESC
       LIMIT ?
    `;
    params = [opts.ministry, limit];
  } else {
    sql = `
      SELECT * FROM laws
       WHERE title_ko IS NOT NULL
       ORDER BY issuance_date DESC, id DESC
       LIMIT ?
    `;
    params = [limit];
  }

  const rows = db().prepare(sql).all(...params) as Record<string, unknown>[];
  return rows.map(hydrate);
}

function ftsQuery(input: string): string {
  return input
    .split(/\s+/)
    .filter(Boolean)
    .map((tok) => `"${tok.replace(/"/g, '""')}"*`)
    .join(" ");
}
