"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import LawTable from "./LawTable";
import type { Law, LawCategory, LawStatus } from "@/lib/meta";
import { CATEGORY_META } from "@/lib/meta";
import { HIERARCHIES, classify, getHierarchy, type HierarchyKey } from "@/lib/hierarchy";
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

type Ministry = { code: string; name_ko: string; count: number };

export default function SearchResults({
  laws,
  ministries,
}: {
  laws: Law[];
  ministries: Ministry[];
}) {
  const sp = useSearchParams();
  const q = (sp.get("q") ?? "").trim();
  const category = sp.get("category");
  const ministry = sp.get("ministry");
  const statusParam = sp.get("status");
  const hierarchySlug = sp.get("hierarchy");
  const recent = sp.get("recent");

  // local UI state: grouping mode (default ON when no query, OFF when searching)
  const [grouped, setGrouped] = useState(true);

  const filtered = useMemo(() => {
    let out = laws;

    if (q) {
      const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
      out = out.filter((law) => {
        const hay = (
          (law.title_ko ?? "") + " " +
          (law.title_id ?? "") + " " +
          (law.summary_ko ?? "") + " " +
          (law.law_number ?? "") + " " +
          (law.law_type ?? "") + " " +
          (law.keywords ?? []).join(" ") + " " +
          (law.categories ?? []).join(" ")
        ).toLowerCase();
        return tokens.every((t) => hay.includes(t));
      });
    }

    if (category && category in CATEGORY_META) {
      out = out.filter((law) => law.category === category);
    }
    if (ministry) {
      out = out.filter((law) => law.ministry_code === ministry);
    }
    if (statusParam && (STATUSES as string[]).includes(statusParam)) {
      out = out.filter((law) => law.status === statusParam);
    }
    if (hierarchySlug && hierarchySlug in HIERARCHY_SLUG) {
      const target = HIERARCHY_SLUG[hierarchySlug];
      out = out.filter((law) => classify(law) === target);
    }
    if (recent) {
      const n = Math.max(1, Math.min(500, Number(recent) || 30));
      out = [...out]
        .sort((a, b) => (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? ""))
        .slice(0, n);
    }

    return out;
  }, [laws, q, category, ministry, statusParam, hierarchySlug, recent]);

  // Group by hierarchy (only when grouped mode)
  const groups = useMemo(() => {
    const map = new Map<HierarchyKey, Law[]>();
    for (const law of filtered) {
      const k = classify(law);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(law);
    }
    return HIERARCHIES
      .map((h) => ({ h, items: map.get(h.key) ?? [] }))
      .filter((g) => g.items.length > 0);
  }, [filtered]);

  // Filter link helper
  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  const link = (extra: Record<string, string | undefined>) => {
    const p = new URLSearchParams(baseParams);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v); else p.delete(k);
    }
    return path(`/search/${p.toString() ? "?" + p : ""}`);
  };

  const activeHierarchy = hierarchySlug ? HIERARCHY_SLUG[hierarchySlug] : null;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[260px_1fr]">
      <aside className="space-y-4 text-sm">
        <FilterBox title="법위계">
          <FilterLink href={link({ hierarchy: undefined })} active={!activeHierarchy}>
            전체
            <Count n={laws.length} />
          </FilterLink>
          {HIERARCHIES.map((h) => {
            const cnt = laws.filter((l) => classify(l) === h.key).length;
            if (cnt === 0) return null;
            return (
              <FilterLink
                key={h.key}
                href={link({ hierarchy: SLUG_OF[h.key] })}
                active={activeHierarchy === h.key}
                accent={h.classes.text}
                dot={h.classes.bgStrong}
              >
                {h.name_ko}
                <Count n={cnt} />
              </FilterLink>
            );
          })}
        </FilterBox>

        {ministries.length > 0 && (
          <FilterBox title="소관 부처">
            <FilterLink href={link({ ministry: undefined })} active={!ministry}>
              전체
            </FilterLink>
            {ministries.map((m) => (
              <FilterLink
                key={m.code}
                href={link({ ministry: m.code })}
                active={ministry === m.code}
              >
                {m.name_ko}
                <Count n={m.count} />
              </FilterLink>
            ))}
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

          {filtered.length > 0 && (
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
        ) : grouped ? (
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
                <LawTable laws={items} compact />
              </section>
            ))}
          </div>
        ) : (
          <LawTable laws={filtered} />
        )}
      </div>
    </div>
  );
}

function Count({ n }: { n: number }) {
  return (
    <span className="text-xs font-semibold text-slate-400 tabular-nums">{n}</span>
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
  href,
  active,
  accent,
  dot,
  children,
}: {
  href: string;
  active: boolean;
  accent?: string;
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
            : `${accent ?? "text-slate-700"} hover:bg-slate-50 hover:text-slate-900`)
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
