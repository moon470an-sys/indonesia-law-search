"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import LawTable, { type SortKey, type SortDir } from "./LawTable";
import type { LawStatus } from "@/lib/meta";
import { HIERARCHIES, classify, getHierarchy, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

const PER_PAGE = 20;

const STATUSES: LawStatus[] = [
  "berlaku", "diubah", "dicabut", "dicabut_sebagian",
  "belum_berlaku", "tidak_diketahui",
];

const HIERARCHY_SLUG: Record<string, HierarchyKey> = {
  uud: "UUD", tap: "TAP", uu: "UU", pp: "PP",
  perpres: "Perpres", permen: "Permen", kepmen: "Kepmen",
  perda_prov: "Perda_Prov", perda_kab: "Perda_Kab", lainnya: "Lainnya",
};

const SLUG_OF: Record<HierarchyKey, string> = Object.fromEntries(
  Object.entries(HIERARCHY_SLUG).map(([slug, key]) => [key, slug])
) as Record<HierarchyKey, string>;

type Row = {
  id: number;
  category: string;
  law_type: string;
  law_number: string;
  title_id: string;
  title_ko: string | null;
  ministry_code: string | null;
  ministry_name_ko: string | null;
  promulgation_date: string | null;
  status: string;
  source: string;
  source_url: string;
};

const SOURCE_LABEL: Record<string, string> = {
  peraturan_go_id: "peraturan.go.id (정부 통합)",
  jdih_dephub: "JDIH 교통부",
  jdih_esdm: "JDIH 에너지광물자원부",
  jdih_bkpm: "JDIH 투자조정청",
  jdih_kemenkeu: "JDIH 재무부",
  jdih_kemendag: "JDIH 무역부",
  jdih_kemnaker: "JDIH 인력부",
  jdih_kemkes: "JDIH 보건부",
  jdih_kemenag: "JDIH 종교부",
  jdih_kemenpppa: "JDIH 여성·아동권익부",
  jdih_kemenpora: "JDIH 청소년·체육부",
  jdih_kemhan: "JDIH 국방부",
  jdih_kpu: "JDIH 선거관리위원회(KPU)",
  jdih_polri: "JDIH 국가경찰청(POLRI)",
  jdih_brin: "JDIH 국가연구혁신청(BRIN)",
  jdih_bmkg: "JDIH 기상기후지구물리청(BMKG)",
  jdih_bps: "JDIH 중앙통계청(BPS)",
  jdih_bnn: "JDIH 마약수사청(BNN)",
  jdih_bnpt: "JDIH 테러대응청(BNPT)",
  jdih_atrbpn: "JDIH 토지·공간행정부",
  jdih_pkp: "JDIH 주거단지부",
  jdih_kejaksaan: "JDIH 검찰청",
  mk_go_id: "헌법재판소",
  mahkamahagung_go_id: "대법원",
  lainnya: "기타",
};

type Ministry = { code: string; name_ko: string; count: number };

/**
 * Extract the region name (Provinsi X / Kabupaten Y / Kota Z) from a Perda
 * title. Returns canonicalized "<Provinsi|Kabupaten|Kota> <Name>" or empty
 * string when no pattern matches.
 */
function extractRegion(title: string): string {
  if (!title) return "";
  // Patterns ordered most-specific first.
  const patterns: [RegExp, (m: RegExpMatchArray) => string][] = [
    // "Peraturan Daerah Provinsi X Nomor ..."
    [/Peraturan\s+Daerah\s+Provinsi\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Provinsi ${m[1].trim()}`],
    // "Peraturan Daerah Kabupaten X Nomor ..."
    [/Peraturan\s+Daerah\s+Kabupaten\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kabupaten ${m[1].trim()}`],
    // "Peraturan Daerah Kota X Nomor ..."
    [/Peraturan\s+Daerah\s+Kota\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kota ${m[1].trim()}`],
    // "Peraturan Gubernur X Nomor ..."
    [/Peraturan\s+Gubernur\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Provinsi ${m[1].trim()}`],
    // "Peraturan Bupati X Nomor ..."
    [/Peraturan\s+Bupati\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kabupaten ${m[1].trim()}`],
    // "Peraturan Wali Kota X Nomor ..." or "Peraturan Walikota X Nomor ..."
    [/Peraturan\s+Wali\s*[Kk]ota\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kota ${m[1].trim()}`],
    // "Peraturan Daerah Khusus Ibu Kota Jakarta" (DKI)
    [/Peraturan\s+Daerah\s+(?:Khusus\s+)?(?:Provinsi\s+)?(?:Daerah\s+Khusus\s+Ibukota\s+Jakarta|DKI\s+Jakarta)/i,
      () => "Provinsi DKI Jakarta"],
    // "Keputusan Gubernur/Bupati/Walikota X" (Perda 카테고리에 들어가는 결정)
    [/Keputusan\s+Gubernur\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Provinsi ${m[1].trim()}`],
    [/Keputusan\s+Bupati\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kabupaten ${m[1].trim()}`],
    [/Keputusan\s+Wali\s*[Kk]ota\s+([A-Z][\w\sA-Za-z'-]+?)\s+(?:Nomor|No\.|Tahun)/i,
      (m) => `Kota ${m[1].trim()}`],
  ];
  for (const [re, build] of patterns) {
    const m = title.match(re);
    if (m) return build(m).replace(/\s{2,}/g, " ").slice(0, 60);
  }
  return "";
}

export default function SearchResults({
  laws,
  ministries,
  fixedHierarchy,
}: {
  laws: Row[];
  ministries: Ministry[];
  fixedHierarchy?: HierarchyKey;
}) {
  const sp = useSearchParams();
  const q = (sp.get("q") ?? "").trim();
  const hierarchySlug = sp.get("hierarchy");
  const ministry = sp.get("ministry");
  const source = sp.get("source");
  const statusParam = sp.get("status");
  const onlyTranslated = sp.get("translated") === "1";
  const recent = sp.get("recent");

  const [page, setPage] = useState(1);
  // Per-hierarchy expand/collapse state for the sidebar sub-buckets.
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const toggle = (k: string) =>
    setExpanded((s) => ({ ...s, [k]: !s[k] }));

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const handleSort = (k: SortKey) => {
    if (sortKey !== k) {
      setSortKey(k);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      // Third click clears the sort and falls back to the default order.
      setSortKey(null);
      setSortDir("asc");
    }
  };

  const filtered = useMemo(() => {
    let out = laws;

    if (q) {
      const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
      out = out.filter((law) => {
        const hay = (
          (law.title_ko ?? "") + " " +
          (law.title_id ?? "") + " " +
          (law.law_number ?? "") + " " +
          (law.law_type ?? "") + " " +
          (law.ministry_name_ko ?? "")
        ).toLowerCase();
        return tokens.every((t) => hay.includes(t));
      });
    }

    if (!fixedHierarchy && hierarchySlug && hierarchySlug in HIERARCHY_SLUG) {
      const target = HIERARCHY_SLUG[hierarchySlug];
      out = out.filter((law) => classify(law) === target);
    }
    if (ministry) {
      if (ministry.startsWith("region:")) {
        const target = ministry.slice("region:".length);
        out = out.filter((law) => extractRegion(law.title_id || "") === target);
      } else {
        out = out.filter((law) => law.ministry_code === ministry);
      }
    }
    if (statusParam && (STATUSES as string[]).includes(statusParam)) {
      out = out.filter((law) => law.status === statusParam);
    }
    if (source) {
      out = out.filter((law) => law.source === source);
    }
    if (onlyTranslated) {
      out = out.filter((law) => law.title_ko != null);
    }
    if (recent) {
      const n = Math.max(1, Math.min(500, Number(recent) || 30));
      out = [...out]
        .sort((a, b) => (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? ""))
        .slice(0, n);
    }

    return out;
  }, [laws, q, hierarchySlug, ministry, source, statusParam, onlyTranslated, recent, fixedHierarchy]);

  // Reset to page 1 whenever the filter or sort changes
  useEffect(() => {
    setPage(1);
  }, [q, hierarchySlug, ministry, source, statusParam, onlyTranslated, recent, sortKey, sortDir]);

  // Numeric prefix from "12 Tahun 2025" / "76/2024" / "76 of 2024" forms,
  // used so 법령번호 sorts numerically instead of "1, 10, 11, 2, 20…".
  const lawNumberKey = (s: string | null | undefined): number => {
    if (!s) return Number.NEGATIVE_INFINITY;
    const m = s.match(/\d+/);
    return m ? Number(m[0]) : Number.NEGATIVE_INFINITY;
  };

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const dir = sortDir === "asc" ? 1 : -1;
    const arr = [...filtered];
    arr.sort((a, b) => {
      const cmp = (() => {
        switch (sortKey) {
          case "title": {
            const ax = (a.title_ko || a.title_id || "").toLowerCase();
            const bx = (b.title_ko || b.title_id || "").toLowerCase();
            return ax.localeCompare(bx, "ko");
          }
          case "hierarchy":
            return getHierarchy(classify(a)).rank - getHierarchy(classify(b)).rank;
          case "law_number":
            return lawNumberKey(a.law_number) - lawNumberKey(b.law_number);
          case "ministry":
            return (a.ministry_name_ko ?? "").localeCompare(b.ministry_name_ko ?? "", "ko");
          case "promulgation_date":
            return (a.promulgation_date ?? "").localeCompare(b.promulgation_date ?? "");
          case "status":
            return (a.status ?? "").localeCompare(b.status ?? "");
          default:
            return 0;
        }
      })();
      return cmp * dir;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const pageRows = sorted.slice((safePage - 1) * PER_PAGE, safePage * PER_PAGE);

  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  const link = (extra: Record<string, string | undefined>) => {
    const p = new URLSearchParams(baseParams);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v); else p.delete(k);
    }
    return path(`/search/${p.toString() ? "?" + p : ""}`);
  };
  // Hierarchy navigation always resets the active text-search query so the
  // user can browse the full bucket without their previous keyword acting
  // as an implicit AND filter.
  const hLink = (extra: Record<string, string | undefined>) =>
    link({ ...extra, q: undefined });

  const activeHierarchy = fixedHierarchy ?? (hierarchySlug ? HIERARCHY_SLUG[hierarchySlug] : null);
  const transCount = laws.filter((l) => l.title_ko != null).length;

  // Sub-buckets for hierarchies that benefit from a 2nd-level breakdown:
  //   Permen / Kepmen     → by ministry (장관별)
  //   Perda_Prov / Perda_Kab → by region extracted from title_id (지역별)
  const subBucketKeys: HierarchyKey[] = ["Permen", "Kepmen", "Perda_Prov", "Perda_Kab"];
  const subBuckets = useMemo(() => {
    const out: Record<string, { code: string; label: string; count: number }[]> = {};
    const isPerda = (k: HierarchyKey) => k === "Perda_Prov" || k === "Perda_Kab";
    for (const key of subBucketKeys) {
      const counts = new Map<string, { label: string; count: number }>();
      for (const law of laws) {
        if (classify(law) !== key) continue;
        let code: string;
        let label: string;
        if (isPerda(key)) {
          const region = extractRegion(law.title_id || "");
          code = region ? `region:${region}` : "__none__";
          label = region || "(지역 미상)";
        } else {
          code = law.ministry_code || "__none__";
          label = law.ministry_name_ko || (code === "__none__" ? "(미분류)" : code);
        }
        const cur = counts.get(code) ?? { label, count: 0 };
        cur.count += 1;
        counts.set(code, cur);
      }
      out[key] = Array.from(counts.entries())
        .map(([code, v]) => ({ code, label: v.label, count: v.count }))
        .sort((a, b) => b.count - a.count);
    }
    return out;
  }, [laws]);

  // Source distribution for the "원본 출처" sidebar box. Counts honour every
  // active filter EXCEPT `source` itself so the user can see how many rows
  // each crawler contributed to the rest-of-filters subset, even while a
  // source pin is active.
  const filteredIgnoringSource = useMemo(() => {
    let out = laws;
    if (q) {
      const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
      out = out.filter((law) => {
        const hay = (
          (law.title_ko ?? "") + " " +
          (law.title_id ?? "") + " " +
          (law.law_number ?? "") + " " +
          (law.law_type ?? "") + " " +
          (law.ministry_name_ko ?? "")
        ).toLowerCase();
        return tokens.every((t) => hay.includes(t));
      });
    }
    if (!fixedHierarchy && hierarchySlug && hierarchySlug in HIERARCHY_SLUG) {
      const target = HIERARCHY_SLUG[hierarchySlug];
      out = out.filter((law) => classify(law) === target);
    }
    if (ministry) {
      if (ministry.startsWith("region:")) {
        const target = ministry.slice("region:".length);
        out = out.filter((law) => extractRegion(law.title_id || "") === target);
      } else {
        out = out.filter((law) => law.ministry_code === ministry);
      }
    }
    if (statusParam && (STATUSES as string[]).includes(statusParam)) {
      out = out.filter((law) => law.status === statusParam);
    }
    if (onlyTranslated) out = out.filter((law) => law.title_ko != null);
    return out;
  }, [laws, q, hierarchySlug, ministry, statusParam, onlyTranslated, fixedHierarchy]);
  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const law of filteredIgnoringSource) {
      const k = law.source || "lainnya";
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([code, count]) => ({
        code,
        label: SOURCE_LABEL[code] ?? code,
        count,
      }))
      .sort((a, b) => b.count - a.count);
  }, [filteredIgnoringSource]);

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[260px_1fr]">
      <aside className="space-y-4 text-sm">
        {!fixedHierarchy && (
          <FilterBox title="법위계">
            {HIERARCHIES.map((h) => {
              const cnt = laws.filter((l) => classify(l) === h.key).length;
              if (cnt === 0) return null;
              const isActive = activeHierarchy === h.key;
              const buckets = subBuckets[h.key as string];
              const hasBuckets = Array.isArray(buckets) && buckets.length > 0;
              // Auto-expand the active hierarchy's sub-list so the user can
              // see where they currently are; otherwise honor the toggle state.
              const isOpen = hasBuckets && (expanded[h.key] || (isActive && !!ministry));
              return (
                <li key={h.key}>
                  <div className="flex items-center gap-1">
                    <FilterLink
                      href={hLink({ hierarchy: SLUG_OF[h.key], ministry: undefined })}
                      active={isActive && !ministry}
                      dot={h.classes.bgStrong}
                      nested={false}
                    >
                      {h.name_ko} <Count n={cnt} />
                    </FilterLink>
                    {hasBuckets && (
                      <button
                        type="button"
                        onClick={() => toggle(h.key)}
                        aria-label={isOpen ? "하위 분류 숨기기" : "하위 분류 펼치기"}
                        className="ml-auto rounded px-1.5 py-0.5 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                      >
                        {isOpen ? "▾" : "▸"}
                      </button>
                    )}
                  </div>
                  {isOpen && (
                    <ul className="mb-1 ml-4 mt-0.5 space-y-0.5 border-l border-slate-200 pl-2">
                      {buckets.map((b) => {
                        const codeForLink =
                          b.code === "__none__" ? undefined : b.code;
                        const subActive = ministry === codeForLink;
                        return (
                          <FilterLink
                            key={b.code}
                            href={hLink({
                              hierarchy: SLUG_OF[h.key],
                              ministry: codeForLink,
                            })}
                            active={subActive}
                            nested
                          >
                            {b.label} <Count n={b.count} />
                          </FilterLink>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </FilterBox>
        )}

        <FilterBox title="원본 출처">
          <FilterLink
            href={link({ source: undefined })}
            active={!source}
          >
            전체 <Count n={filteredIgnoringSource.length} />
          </FilterLink>
          {sourceCounts.map((s) => (
            <FilterLink
              key={s.code}
              href={link({ source: source === s.code ? undefined : s.code })}
              active={source === s.code}
            >
              {s.label} <Count n={s.count} />
            </FilterLink>
          ))}
        </FilterBox>

      </aside>

      <div className="space-y-5">
        {q && (
          <p className="text-sm text-slate-500">
            검색어: "<span className="font-medium text-slate-800">{q}</span>"
          </p>
        )}

        {filtered.length === 0 ? (
          <p className="rounded-lg border border-slate-200 bg-white p-8 text-center text-base text-slate-500">
            검색 결과가 없습니다.
          </p>
        ) : (
          <>
            <PageInfo
              page={safePage}
              perPage={PER_PAGE}
              total={filtered.length}
            />
            <LawTable
              laws={pageRows}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
            />
            <Pager
              page={safePage}
              totalPages={totalPages}
              onChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}

function PageInfo({ page, perPage, total }: { page: number; perPage: number; total: number }) {
  const from = (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);
  return (
    <p className="text-xs text-slate-500 tabular-nums">
      {from.toLocaleString()}–{to.toLocaleString()} / {total.toLocaleString()}건 (페이지 {page})
    </p>
  );
}

function Pager({
  page, totalPages, onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;

  // Build a compact page-number window around the current page.
  const window = 2;
  const pages: (number | "…")[] = [];
  const push = (n: number) => {
    if (pages[pages.length - 1] !== n) pages.push(n);
  };
  push(1);
  if (page - window > 2) pages.push("…");
  for (let n = Math.max(2, page - window); n <= Math.min(totalPages - 1, page + window); n++) {
    push(n);
  }
  if (page + window < totalPages - 1) pages.push("…");
  if (totalPages > 1) push(totalPages);

  const go = (n: number) => () => {
    onChange(n);
    if (typeof window !== "undefined" && typeof globalThis !== "undefined") {
      // scroll to top of results so users see the new page
      try { (globalThis as { scrollTo?: (o: ScrollToOptions) => void }).scrollTo?.({ top: 0, behavior: "smooth" }); }
      catch { /* ignore */ }
    }
  };

  return (
    <nav className="flex flex-wrap items-center justify-center gap-1 pt-2">
      <button
        type="button"
        onClick={go(Math.max(1, page - 1))}
        disabled={page === 1}
        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 disabled:opacity-40"
      >
        ← 이전
      </button>
      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`e${i}`} className="px-1 text-xs text-slate-400">…</span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={go(p)}
            className={
              "min-w-[36px] rounded-md border px-2.5 py-1.5 text-xs font-semibold tabular-nums transition " +
              (p === page
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-400")
            }
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        onClick={go(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 disabled:opacity-40"
      >
        다음 →
      </button>
    </nav>
  );
}

function Count({ n }: { n: number }) {
  return (
    <span className="ml-auto text-xs font-semibold text-slate-400 tabular-nums">{n}</span>
  );
}

function FilterBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
        {title}
      </h4>
      <ul className="space-y-1">{children}</ul>
    </div>
  );
}

function FilterLink({
  href, active, dot, children, nested,
}: {
  href: string;
  active: boolean;
  dot?: string;
  children: React.ReactNode;
  /** when true, render the link directly without wrapping <li> (parent already provides one) */
  nested?: boolean;
}) {
  const anchor = (
    <a
      href={href}
      className={
        "flex items-center gap-2 rounded-md transition-colors " +
        (nested ? "px-1.5 py-1 text-[13px] " : "px-2 py-1.5 ") +
        (active
          ? "bg-slate-900 font-semibold text-white"
          : "text-slate-700 hover:bg-slate-50 hover:text-slate-900")
      }
    >
      {dot && !active && (
        <span className={`size-2 shrink-0 rounded-full ${dot}`} aria-hidden />
      )}
      <span className="flex-1">{children}</span>
    </a>
  );
  if (nested) return <li>{anchor}</li>;
  return <li>{anchor}</li>;
}
