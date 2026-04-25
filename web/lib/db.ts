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

export type LawCategory =
  | "peraturan"
  | "keputusan"
  | "lampiran"
  | "perda"
  | "putusan"
  | "kepkl"
  | "perjanjian"
  | "lainnya";

export type LawStatus =
  | "berlaku"
  | "diubah"
  | "dicabut"
  | "dicabut_sebagian"
  | "belum_berlaku"
  | "tidak_diketahui";

export type Law = {
  id: number;
  slug: string | null;
  category: LawCategory;
  law_type: string;
  law_number: string;
  year: number | null;
  title_id: string;
  title_ko: string | null;
  title_en: string | null;
  summary_ko: string | null;
  ministry_code: string | null;
  ministry_name_ko: string | null;
  region_code: string | null;
  enactment_date: string | null;
  promulgation_date: string | null;
  effective_date: string | null;
  repealed_date: string | null;
  status: LawStatus;
  era: string;
  source: string;
  source_url: string;
  pdf_url_id: string | null;
  pdf_url_en: string | null;
  categories: string[] | null;
  keywords: string[] | null;
};

export const CATEGORY_META: Record<LawCategory, { name_ko: string; tag_ko: string }> = {
  peraturan:  { name_ko: "법령",         tag_ko: "Peraturan" },
  keputusan:  { name_ko: "행정규칙",      tag_ko: "Keputusan" },
  lampiran:   { name_ko: "별표·서식",     tag_ko: "Lampiran" },
  perda:      { name_ko: "지방법규",      tag_ko: "Perda" },
  putusan:    { name_ko: "판례·해석례",   tag_ko: "Putusan" },
  kepkl:      { name_ko: "부처별 결정",   tag_ko: "Keputusan K/L" },
  perjanjian: { name_ko: "조약",         tag_ko: "Perjanjian" },
  lainnya:    { name_ko: "기타",         tag_ko: "Lainnya" },
};

export const STATUS_META: Record<LawStatus, { name_ko: string; color: string }> = {
  berlaku:          { name_ko: "현행",       color: "emerald" },
  diubah:           { name_ko: "개정",       color: "amber" },
  dicabut:          { name_ko: "폐지",       color: "rose" },
  dicabut_sebagian: { name_ko: "일부폐지",   color: "rose" },
  belum_berlaku:    { name_ko: "미시행",     color: "slate" },
  tidak_diketahui:  { name_ko: "미상",       color: "slate" },
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

export function listMinistries(): { code: string; name_ko: string; count: number }[] {
  return db()
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
    .all() as { code: string; name_ko: string; count: number }[];
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
  for (const c of Object.keys(CATEGORY_META)) out[c] = 0;
  for (const r of rows) out[r.category] = r.count;
  return out as Record<LawCategory, number>;
}

export type SearchOpts = {
  q?: string;
  category?: LawCategory;
  ministry?: string;
  status?: LawStatus;
  era?: "modern" | "lama" | "kolonial";
  field?: "title" | "body" | "article_title" | "article_body" | "addendum" | "amendment";
  limit?: number;
};

export function search(opts: SearchOpts): Law[] {
  const limit = opts.limit ?? 50;
  const where: string[] = ["laws.title_ko IS NOT NULL"];
  const params: SQLInputValue[] = [];
  let from = "FROM laws";
  let order = "ORDER BY laws.promulgation_date DESC, laws.id DESC";

  const q = opts.q?.trim();
  if (q) {
    const fts = ftsQuery(q);
    if (opts.field === "article_title" || opts.field === "article_body") {
      from = "FROM articles_fts JOIN articles ON articles.id = articles_fts.rowid JOIN laws ON laws.id = articles.law_id";
      where.push("articles_fts MATCH ?");
      params.push(fts);
      order = "ORDER BY rank";
    } else if (opts.field === "addendum") {
      from = "FROM addenda_fts JOIN addenda ON addenda.id = addenda_fts.rowid JOIN laws ON laws.id = addenda.law_id";
      where.push("addenda_fts MATCH ?");
      params.push(fts);
      order = "ORDER BY rank";
    } else {
      // title 검색이 기본 (body는 향후 별도 column 추가 시 확장)
      from = "FROM laws_fts JOIN laws ON laws.id = laws_fts.rowid";
      where.push("laws_fts MATCH ?");
      params.push(fts);
      order = "ORDER BY rank";
    }
  }

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

  const sql = `SELECT laws.* ${from} WHERE ${where.join(" AND ")} ${order} LIMIT ?`;
  params.push(limit);
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
