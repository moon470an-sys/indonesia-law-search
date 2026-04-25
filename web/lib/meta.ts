// Pure metadata — safe to import from client components.
// (lib/db.ts pulls node:sqlite and must not be imported client-side.)

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

export const STATUS_CLASSES: Record<LawStatus, string> = {
  berlaku:          "bg-emerald-50 text-emerald-700",
  diubah:           "bg-amber-50 text-amber-700",
  dicabut:          "bg-rose-50 text-rose-700",
  dicabut_sebagian: "bg-rose-50 text-rose-700",
  belum_berlaku:    "bg-slate-100 text-slate-600",
  tidak_diketahui:  "bg-slate-100 text-slate-600",
};
