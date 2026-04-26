"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import LawTable from "./LawTable";
import type { LawStatus } from "@/lib/meta";
import { HIERARCHIES, classify, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

const PER_PAGE = 50;

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
  source_url: string;
};

type Ministry = { code: string; name_ko: string; count: number };

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
  const statusParam = sp.get("status");
  const onlyTranslated = sp.get("translated") === "1";
  const recent = sp.get("recent");

  const [grouped, setGrouped] = useState(false);
  const [page, setPage] = useState(1);

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
      out = out.filter((law) => law.ministry_code === ministry);
    }
    if (statusParam && (STATUSES as string[]).includes(statusParam)) {
      out = out.filter((law) => law.status === statusParam);
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
  }, [laws, q, hierarchySlug, ministry, statusParam, onlyTranslated, recent, fixedHierarchy]);

  // Reset to page 1 whenever the filter / mode set changes
  useEffect(() => {
    setPage(1);
  }, [q, hierarchySlug, ministry, statusParam, onlyTranslated, recent, grouped]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PER_PAGE, safePage * PER_PAGE);

  const groups = useMemo(() => {
    if (!grouped) return [];
    const map = new Map<HierarchyKey, Row[]>();
    for (const law of filtered) {
      const k = classify(law);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(law);
    }
    return HIERARCHIES
      .map((h) => ({ h, items: map.get(h.key) ?? [] }))
      .filter((g) => g.items.length > 0);
  }, [filtered, grouped]);

  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  const link = (extra: Record<string, string | undefined>) => {
    const p = new URLSearchParams(baseParams);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v); else p.delete(k);
    }
    return path(`/search/${p.toString() ? "?" + p : ""}`);
  };

  const activeHierarchy = fixedHierarchy ?? (hierarchySlug ? HIERARCHY_SLUG[hierarchySlug] : null);
  const transCount = laws.filter((l) => l.title_ko != null).length;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[260px_1fr]">
      <aside className="space-y-4 text-sm">
        {!fixedHierarchy && (
          <FilterBox title="법위계">
            <FilterLink href={link({ hierarchy: undefined })} active={!activeHierarchy}>
              전체 <Count n={laws.length} />
            </FilterLink>
            {HIERARCHIES.map((h) => {
              const cnt = laws.filter((l) => classify(l) === h.key).length;
              if (cnt === 0) return null;
              return (
                <FilterLink
                  key={h.key}
                  href={link({ hierarchy: SLUG_OF[h.key] })}
                  active={activeHierarchy === h.key}
                  dot={h.classes.bgStrong}
                >
                  {h.name_ko} <Count n={cnt} />
                </FilterLink>
              );
            })}
          </FilterBox>
        )}

        <FilterBox title="상태">
          <FilterLink href={link({ status: undefined })} active={!statusParam}>전체</FilterLink>
          <FilterLink href={link({ status: "berlaku" })} active={statusParam === "berlaku"}>
            현행 (Berlaku)
          </FilterLink>
          <FilterLink href={link({ status: "diubah" })} active={statusParam === "diubah"}>
            개정 (Diubah)
          </FilterLink>
          <FilterLink href={link({ status: "dicabut" })} active={statusParam === "dicabut"}>
            폐지 (Dicabut)
          </FilterLink>
        </FilterBox>
      </aside>

      <div className="space-y-5">
        <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-slate-200 pb-3">
          <p className="text-base text-slate-700">
            {filtered.length === 0 ? (
              "검색 결과가 없습니다."
            ) : (
              <>
                <span className="text-2xl font-bold text-slate-900 tabular-nums">
                  {filtered.length.toLocaleString()}
                </span>
                <span className="ml-1 font-semibold text-slate-700">건</span>
                <span className="ml-1 text-slate-500">의 결과</span>
                {q ? (
                  <span className="ml-2 text-slate-500">
                    · "<span className="font-medium text-slate-800">{q}</span>"
                  </span>
                ) : null}
              </>
            )}
          </p>

          {filtered.length > 0 && !fixedHierarchy && (
            <div className="inline-flex rounded-md border border-slate-200 bg-white p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setGrouped(false)}
                className={
                  "rounded px-3 py-1.5 font-semibold transition " +
                  (!grouped ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900")
                }
              >
                전체 목록
              </button>
              <button
                type="button"
                onClick={() => setGrouped(true)}
                className={
                  "rounded px-3 py-1.5 font-semibold transition " +
                  (grouped ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900")
                }
              >
                위계별
              </button>
            </div>
          )}
        </header>

        {filtered.length === 0 ? (
          <p className="rounded-lg border border-slate-200 bg-white p-8 text-center text-base text-slate-500">
            검색 결과가 없습니다.
          </p>
        ) : grouped && !fixedHierarchy ? (
          <div className="space-y-6">
            {groups.map(({ h, items }) => (
              <section
                key={h.key}
                className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
              >
                <header
                  className={`flex items-center justify-between border-l-4 ${h.classes.border} ${h.classes.bg} px-5 py-3`}
                >
                  <div>
                    <p className={`text-[11px] font-bold uppercase tracking-wider ${h.classes.text}`}>
                      Rank {h.rank}
                    </p>
                    <h3 className="text-base font-bold text-slate-900">
                      {h.name_ko}
                      <span className="ml-2 text-sm font-normal italic text-slate-500">
                        {h.name_id}
                      </span>
                    </h3>
                  </div>
                  <p className="text-sm font-semibold text-slate-700 tabular-nums">
                    {items.length.toLocaleString()}건
                  </p>
                </header>
                <LawTable laws={items.slice(0, 50)} compact />
                {items.length > 50 && (
                  <div className="border-t border-slate-100 bg-slate-50 px-5 py-2.5 text-xs text-slate-500">
                    상위 50건만 표시됩니다 — 전체 {items.length.toLocaleString()}건은{" "}
                    <a
                      href={path(`/search/${SLUG_OF[h.key]}/`)}
                      className="font-semibold text-brand hover:underline"
                    >
                      {h.name_ko} 인덱스 →
                    </a>
                  </div>
                )}
              </section>
            ))}
          </div>
        ) : (
          <>
            <PageInfo
              page={safePage}
              perPage={PER_PAGE}
              total={filtered.length}
            />
            <LawTable laws={pageRows} />
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
  href, active, dot, children,
}: {
  href: string;
  active: boolean;
  dot?: string;
  children: React.ReactNode;
}) {
  return (
    <li>
      <a
        href={href}
        className={
          "flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors " +
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
    </li>
  );
}
