"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import LawTable from "./LawTable";
import type { LawStatus } from "@/lib/meta";
import { HIERARCHIES, classify, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

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
  ministry_name_ko: string | null;
  promulgation_date: string | null;
  status: string;
  source_url: string;
};

type Ministry = { code: string; name_ko: string; count: number };

export default function SearchResults({
  laws,
  ministries,
  // when set, the page is already scoped to one hierarchy and we hide that facet
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

  const [grouped, setGrouped] = useState(true);

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
      out = out.filter((law) => {
        // best-effort: map ministry code via name_ko
        return law.ministry_name_ko === ministries.find((m) => m.code === ministry)?.name_ko;
      });
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
  }, [laws, q, hierarchySlug, ministry, statusParam, onlyTranslated, recent, fixedHierarchy, ministries]);

  const groups = useMemo(() => {
    const map = new Map<HierarchyKey, Row[]>();
    for (const law of filtered) {
      const k = classify(law);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(law);
    }
    return HIERARCHIES
      .map((h) => ({ h, items: map.get(h.key) ?? [] }))
      .filter((g) => g.items.length > 0);
  }, [filtered]);

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

        <FilterBox title="번역 상태">
          <FilterLink href={link({ translated: undefined })} active={!onlyTranslated}>
            전체 (번역+미번역)
          </FilterLink>
          <FilterLink href={link({ translated: "1" })} active={onlyTranslated}>
            한국어 번역만 <Count n={transCount} />
          </FilterLink>
        </FilterBox>

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
                onClick={() => setGrouped(true)}
                className={
                  "rounded px-3 py-1.5 font-semibold transition " +
                  (grouped ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900")
                }
              >
                위계별
              </button>
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
                <LawTable laws={items.slice(0, 200)} compact />
                {items.length > 200 && (
                  <div className="border-t border-slate-100 bg-slate-50 px-5 py-2.5 text-xs text-slate-500">
                    상위 200건만 표시됩니다 — 전체 {items.length.toLocaleString()}건은{" "}
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
          <LawTable laws={filtered.slice(0, 500)} />
        )}
      </div>
    </div>
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
