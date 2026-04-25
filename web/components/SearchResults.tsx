"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import LawTable from "./LawTable";
import type { Law, LawCategory, LawStatus } from "@/lib/meta";
import { CATEGORY_META } from "@/lib/meta";
import { path } from "@/lib/paths";

const STATUSES: LawStatus[] = [
  "berlaku", "diubah", "dicabut", "dicabut_sebagian",
  "belum_berlaku", "tidak_diketahui",
];
const ERAS = ["modern", "lama", "kolonial"] as const;

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
  const status = sp.get("status");
  const era = sp.get("era");
  const recent = sp.get("recent");

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
    if (status && (STATUSES as string[]).includes(status)) {
      out = out.filter((law) => law.status === status);
    }
    if (era && (ERAS as readonly string[]).includes(era)) {
      out = out.filter((law) => law.era === era);
    }
    if (recent) {
      // simple "recent N days" by promulgation_date sort, top N rows
      const n = Math.max(1, Math.min(200, Number(recent) || 30));
      out = [...out]
        .sort((a, b) => (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? ""))
        .slice(0, n);
    }

    return out;
  }, [laws, q, category, ministry, status, era, recent]);

  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);

  const link = (extra: Record<string, string | undefined>) => {
    const p = new URLSearchParams(baseParams);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    return path(`/search/${p.toString() ? "?" + p : ""}`);
  };

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
      <aside className="space-y-4 text-sm">
        <FilterBox title="1차 메뉴">
          <FilterLink href={link({ category: undefined })} active={!category}>
            전체 ({laws.length})
          </FilterLink>
          {(Object.keys(CATEGORY_META) as LawCategory[]).map((c) => {
            const cnt = laws.filter((l) => l.category === c).length;
            if (cnt === 0) return null;
            return (
              <FilterLink
                key={c}
                href={link({ category: c })}
                active={category === c}
                count={cnt}
              >
                {CATEGORY_META[c].name_ko}
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
                count={m.count}
              >
                {m.name_ko}
              </FilterLink>
            ))}
          </FilterBox>
        )}

        <FilterBox title="상태">
          <FilterLink href={link({ status: undefined })} active={!status}>
            전체
          </FilterLink>
          <FilterLink href={link({ status: "berlaku" })} active={status === "berlaku"}>
            현행 (Berlaku)
          </FilterLink>
          <FilterLink href={link({ status: "diubah" })} active={status === "diubah"}>
            개정 (Diubah)
          </FilterLink>
          <FilterLink href={link({ status: "dicabut" })} active={status === "dicabut"}>
            폐지 (Dicabut)
          </FilterLink>
        </FilterBox>
      </aside>

      <div className="space-y-3">
        <p className="text-sm text-slate-600">
          {filtered.length === 0 ? (
            "검색 결과가 없습니다."
          ) : (
            <>
              <span className="font-bold text-slate-900">{filtered.length}건</span> 의 결과
              {q ? <> · <span className="font-medium">"{q}"</span></> : null}
            </>
          )}
        </p>
        <LawTable laws={filtered} />
      </div>
    </div>
  );
}

function FilterBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h4>
      <ul className="space-y-1">{children}</ul>
    </div>
  );
}

function FilterLink({
  href, active, count, children,
}: {
  href: string;
  active: boolean;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-center justify-between">
      <a
        href={href}
        className={
          active
            ? "font-semibold text-blue-700"
            : "text-slate-600 hover:text-blue-700"
        }
      >
        {children}
      </a>
      {typeof count === "number" && (
        <span className="text-[11px] text-slate-400">{count}</span>
      )}
    </li>
  );
}
