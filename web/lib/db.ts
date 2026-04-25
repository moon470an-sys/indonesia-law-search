import path from "node:path";
import { DatabaseSync, type SQLInputValue } from "node:sqlite";
import type { Law, LawCategory, LawStatus } from "./meta";

export type { Law, LawCategory, LawStatus } from "./meta";
export { CATEGORY_META, STATUS_META, STATUS_CLASSES } from "./meta";

const DB_PATH =
  process.env.LAWS_DB_PATH ??
  path.resolve(process.cwd(), "..", "data", "laws.db");

let _db: DatabaseSync | null = null;

function db(): DatabaseSync {
  if (_db) return _db;
  _db = new DatabaseSync(DB_PATH, { readOnly: true });
  return _db;
}

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
  // node:sqlite returns rows that aren't plain objects; copy explicitly
  // so they can be passed to Client Components.
  const r = row as Record<string, unknown>;
  return {
    id: r.id as number,
    slug: (r.slug as string | null) ?? null,
    category: r.category as Law["category"],
    law_type: r.law_type as string,
    law_number: r.law_number as string,
    year: (r.year as number | null) ?? null,
    title_id: r.title_id as string,
    title_ko: (r.title_ko as string | null) ?? null,
    title_en: (r.title_en as string | null) ?? null,
    summary_ko: (r.summary_ko as string | null) ?? null,
    ministry_code: (r.ministry_code as string | null) ?? null,
    ministry_name_ko: (r.ministry_name_ko as string | null) ?? null,
    region_code: (r.region_code as string | null) ?? null,
    enactment_date: (r.enactment_date as string | null) ?? null,
    promulgation_date: (r.promulgation_date as string | null) ?? null,
    effective_date: (r.effective_date as string | null) ?? null,
    repealed_date: (r.repealed_date as string | null) ?? null,
    status: r.status as Law["status"],
    era: r.era as string,
    source: r.source as string,
    source_url: r.source_url as string,
    pdf_url_id: (r.pdf_url_id as string | null) ?? null,
    pdf_url_en: (r.pdf_url_en as string | null) ?? null,
    categories: parseList(r.categories),
    keywords: parseList(r.keywords),
  };
}

export function listRecent(limit = 20): Law[] {
  const rows = db()
    .prepare(
      `SELECT * FROM laws
       WHERE title_ko IS NOT NULL
       ORDER BY promulgation_date DESC, id DESC
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

/**
 * Minimal projection used by hierarchy index pages. Avoids inlining the heavy
 * fields (categories/keywords/summary_ko) when listing 5,000+ rows.
 */
export type LawMin = {
  id: number;
  category: string;
  law_type: string;
  law_number: string;
  title_id: string;
  title_ko: string | null;
  ministry_name_ko: string | null;
  year: number | null;
  promulgation_date: string | null;
  status: string;
  source_url: string;
  pdf_url_id: string | null;
};

export function listAllMin(): LawMin[] {
  const rows = db()
    .prepare(
      `SELECT id, category, law_type, law_number, title_id, title_ko,
              ministry_name_ko, year, promulgation_date, status,
              source_url, pdf_url_id
         FROM laws`,
    )
    .all() as Record<string, unknown>[];
  return rows.map((r) => ({
    id: r.id as number,
    category: r.category as string,
    law_type: r.law_type as string,
    law_number: r.law_number as string,
    title_id: r.title_id as string,
    title_ko: (r.title_ko as string | null) ?? null,
    ministry_name_ko: (r.ministry_name_ko as string | null) ?? null,
    year: (r.year as number | null) ?? null,
    promulgation_date: (r.promulgation_date as string | null) ?? null,
    status: r.status as string,
    source_url: r.source_url as string,
    pdf_url_id: (r.pdf_url_id as string | null) ?? null,
  }));
}

export function listMinistries(): { code: string; name_ko: string; count: number }[] {
  const rows = db()
    .prepare(
      `SELECT ministry_code AS code,
              COALESCE(ministry_name_ko, ministry_code) AS name_ko,
              COUNT(*) AS count
         FROM laws
        WHERE title_ko IS NOT NULL
          AND ministry_code IS NOT NULL
     GROUP BY ministry_code, ministry_name_ko
     ORDER BY count DESC`,
    )
    .all() as Record<string, unknown>[];
  return rows.map((r) => ({
    code: r.code as string,
    name_ko: r.name_ko as string,
    count: r.count as number,
  }));
}

export function categoryCounts(): Record<LawCategory, number> {
  const rows = db()
    .prepare(
      `SELECT category, COUNT(*) AS count
         FROM laws
        WHERE title_ko IS NOT NULL
     GROUP BY category`,
    )
    .all() as { category: LawCategory; count: number }[];
  const out: Record<string, number> = {};
  const allCats: LawCategory[] = ["peraturan","keputusan","lampiran","perda","putusan","kepkl","perjanjian","lainnya"];
  for (const c of allCats) out[c] = 0;
  for (const r of rows) out[r.category] = r.count;
  return out as Record<LawCategory, number>;
}

export type SearchOpts = {
  q?: string;
  category?: LawCategory;
  ministry?: string;
  status?: LawStatus;
  era?: "modern" | "lama" | "kolonial";
  limit?: number;
};

export function search(opts: SearchOpts): Law[] {
  const limit = opts.limit ?? 50;
  const where: string[] = ["laws.title_ko IS NOT NULL"];
  const params: SQLInputValue[] = [];

  if (opts.category) {
    where.push("laws.category = ?");
    params.push(opts.category);
  }
  if (opts.ministry) {
    where.push("laws.ministry_code = ?");
    params.push(opts.ministry);
  }
  if (opts.status) {
    where.push("laws.status = ?");
    params.push(opts.status);
  }
  if (opts.era) {
    where.push("laws.era = ?");
    params.push(opts.era);
  }

  const sql =
    `SELECT laws.* FROM laws WHERE ${where.join(" AND ")} ` +
    `ORDER BY laws.promulgation_date DESC, laws.id DESC LIMIT ?`;
  params.push(limit);
  const rows = db().prepare(sql).all(...params) as Record<string, unknown>[];
  return rows.map(hydrate);
}
