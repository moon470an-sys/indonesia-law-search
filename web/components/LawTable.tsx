"use client";

import { path } from "@/lib/paths";
import { STATUS_META, STATUS_CLASSES, type LawStatus } from "@/lib/meta";
import { classify } from "@/lib/hierarchy";
import HierarchyBadge from "./HierarchyBadge";

type Row = {
  id: number;
  category: string;
  law_type: string;
  law_number: string;
  title_id: string;
  title_ko: string | null;
  ministry_name_ko: string | null;
  promulgation_date: string | null;
  status: string;
  source_url: string;
};

export type SortKey =
  | "title"
  | "hierarchy"
  | "law_number"
  | "ministry"
  | "promulgation_date"
  | "status";
export type SortDir = "asc" | "desc";

export default function LawTable({
  laws,
  compact = false,
  sortKey,
  sortDir,
  onSort,
}: {
  laws: Row[];
  compact?: boolean;
  sortKey?: SortKey | null;
  sortDir?: SortDir;
  onSort?: (key: SortKey) => void;
}) {
  if (laws.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-8 text-center text-base text-slate-500">
        검색 결과가 없습니다.
      </p>
    );
  }

  return (
    <div
      className={
        compact
          ? "overflow-x-auto"
          : "overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm"
      }
    >
      <table className="w-full text-[15px]">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-5 py-3 text-left">
              <SortHeader k="title" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                법령명
              </SortHeader>
            </th>
            {!compact && (
              <th className="px-3 py-3 text-left whitespace-nowrap">
                <SortHeader k="hierarchy" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  위계
                </SortHeader>
              </th>
            )}
            <th className="px-3 py-3 text-left whitespace-nowrap">
              <SortHeader k="law_number" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                법령번호
              </SortHeader>
            </th>
            <th className="px-3 py-3 text-left whitespace-nowrap">
              <SortHeader k="ministry" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                출처
              </SortHeader>
            </th>
            <th className="px-3 py-3 text-left whitespace-nowrap">
              <SortHeader k="promulgation_date" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                제정일
              </SortHeader>
            </th>
            <th className="px-3 py-3 text-left whitespace-nowrap">
              <SortHeader k="status" sortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                상태
              </SortHeader>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {laws.map((law) => {
            const translated = !!law.title_ko;
            const status = STATUS_META[(law.status as LawStatus)] ?? STATUS_META.berlaku;
            const cls = STATUS_CLASSES[(law.status as LawStatus)] ?? STATUS_CLASSES.berlaku;
            const detailHref = translated
              ? path(`/laws/${law.id}/`)
              : law.source_url;
            return (
              <tr key={law.id} className="transition-colors hover:bg-blue-50/40">
                <td className="px-5 py-4 align-top">
                  <a
                    href={detailHref}
                    target={translated ? undefined : "_blank"}
                    rel={translated ? undefined : "noreferrer"}
                    className="block text-[15px] font-semibold leading-snug text-slate-900 hover:text-brand hover:underline"
                  >
                    {translated ? law.title_ko : law.title_id}
                  </a>
                  {!translated && (
                    <div className="mt-2">
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-200">
                        미번역
                      </span>
                    </div>
                  )}
                </td>
                {!compact && (
                  <td className="px-3 py-4 align-top whitespace-nowrap">
                    <HierarchyBadge law={law} />
                  </td>
                )}
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap tabular-nums">
                  {law.law_number}
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap">
                  {law.ministry_name_ko ?? sourceLabel(law)}
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-600 whitespace-nowrap tabular-nums">
                  {law.promulgation_date ?? "—"}
                </td>
                <td className="px-3 py-4 align-top">
                  <span
                    className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${cls}`}
                  >
                    {status.name_ko}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * For laws whose ministry_name_ko is NULL — almost always national/local
 * statutes from peraturan.go.id (UU / PP / Perpres / UUD / Perda) — fall
 * back to the issuing body inferred from the hierarchy. For Perda we try
 * to extract the region (Provinsi/Kabupaten/Kota X) from the title.
 */
function sourceLabel(law: { law_type: string; title_id?: string; category?: string | null; source_url?: string | null; title_ko?: string | null }): string {
  const h = classify(law);
  if (h === "UUD") return "헌법기관";
  if (h === "TAP") return "MPR (인민협의회)";
  if (h === "UU") return "국회·정부 (DPR/Pemerintah)";
  if (h === "PP") return "정부 (Pemerintah)";
  if (h === "Perpres") return "대통령 (Presiden)";
  if (h === "Perda_Prov" || h === "Perda_Kab") {
    const region = extractRegionLabel(law.title_id || "");
    if (region) return region;
    return h === "Perda_Prov" ? "주 정부 (Pemda Provinsi)" : "시·군 (Pemda Kab/Kota)";
  }
  return "—";
}

function extractRegionLabel(title: string): string {
  if (!title) return "";
  const patterns: [RegExp, (m: RegExpMatchArray) => string][] = [
    [/Peraturan\s+Daerah\s+Provinsi\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Provinsi ${m[1].trim()}`],
    [/Peraturan\s+Daerah\s+Kabupaten\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Kabupaten ${m[1].trim()}`],
    [/Peraturan\s+Daerah\s+Kota\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Kota ${m[1].trim()}`],
    [/Peraturan\s+Gubernur\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Provinsi ${m[1].trim()}`],
    [/Peraturan\s+Bupati\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Kabupaten ${m[1].trim()}`],
    [/Peraturan\s+Wali\s*[Kk]ota\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i, (m) => `Kota ${m[1].trim()}`],
  ];
  for (const [re, build] of patterns) {
    const m = title.match(re);
    if (m) return build(m).slice(0, 40);
  }
  return "";
}

function SortHeader({
  k,
  sortKey,
  sortDir,
  onSort,
  children,
}: {
  k: SortKey;
  sortKey?: SortKey | null;
  sortDir?: SortDir;
  onSort?: (key: SortKey) => void;
  children: React.ReactNode;
}) {
  if (!onSort) return <>{children}</>;
  const active = sortKey === k;
  const arrow = !active ? "↕" : sortDir === "asc" ? "▲" : "▼";
  return (
    <button
      type="button"
      onClick={() => onSort(k)}
      className={
        "inline-flex items-center gap-1 font-semibold uppercase tracking-wider transition-colors " +
        (active ? "text-slate-900" : "text-slate-500 hover:text-slate-800")
      }
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      <span>{children}</span>
      <span className="text-[10px] opacity-70" aria-hidden>
        {arrow}
      </span>
    </button>
  );
}
