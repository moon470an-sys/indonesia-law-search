import { Suspense } from "react";
import { notFound } from "next/navigation";
import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResults";
import { listAllMin, listMinistries } from "@/lib/db";
import { HIERARCHIES, classify, getHierarchy, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

const SLUG_TO_KEY: Record<string, HierarchyKey> = {
  uud: "UUD", tap: "TAP", uu: "UU", pp: "PP", perpres: "Perpres",
  permen: "Permen", kepmen: "Kepmen", perda_prov: "Perda_Prov",
  perda_kab: "Perda_Kab", lainnya: "Lainnya",
};
const SLUGS = Object.keys(SLUG_TO_KEY);

export function generateStaticParams() {
  return SLUGS.map((hierarchy) => ({ hierarchy }));
}

export default async function HierarchyIndexPage({
  params,
}: {
  params: Promise<{ hierarchy: string }>;
}) {
  const { hierarchy } = await params;
  if (!(hierarchy in SLUG_TO_KEY)) notFound();
  const key = SLUG_TO_KEY[hierarchy];
  const h = getHierarchy(key);

  const HARD_CAP = 2000;
  // pull only the rows in this hierarchy bucket
  const fullBucket = listAllMin().filter((l) => classify(l) === key);
  // 번역된 행 우선 + 최신 promulgation_date 순
  const sorted = [...fullBucket].sort((a, b) => {
    const ta = a.title_ko ? 0 : 1;
    const tb = b.title_ko ? 0 : 1;
    if (ta !== tb) return ta - tb;
    return (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? "");
  });
  const all = sorted.slice(0, HARD_CAP);
  const truncated = fullBucket.length > HARD_CAP;

  const ministries = listMinistries();
  const translated = fullBucket.filter((l) => l.title_ko != null).length;

  return (
    <div className="space-y-6">
      {/* 위계 헤더 — 색상 막대 */}
      <header
        className={`relative overflow-hidden rounded-lg border border-slate-200 bg-white p-6 shadow-sm`}
      >
        <span className={`absolute inset-y-0 left-0 w-1.5 ${h.classes.bgStrong}`} aria-hidden />
        <nav className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-brand">홈</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <a href={path("/search/")} className="hover:text-brand">검색</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <span>{h.name_ko}</span>
        </nav>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ring-1 ${h.classes.badge}`}>
            Rank {h.rank}
          </span>
          <span className="text-xs text-slate-500 italic">{h.name_id}</span>
        </div>
        <h1 className="mt-3 text-2xl font-bold text-slate-900 sm:text-[26px]">
          {h.name_ko}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          전체 <span className="font-bold text-slate-900 tabular-nums">{fullBucket.length.toLocaleString()}</span>건
          {" · "}
          한국어 번역 <span className="font-semibold tabular-nums">{translated.toLocaleString()}</span>건
          {truncated && (
            <span className="ml-2 text-xs text-amber-700">
              · 페이지 크기 보호를 위해 상위 {HARD_CAP.toLocaleString()}건만 표시
            </span>
          )}
        </p>
      </header>

      {/* 다른 위계로 빠른 이동 */}
      <nav className="flex flex-wrap gap-2 text-sm">
        {HIERARCHIES.filter((other) => other.key !== key).map((other) => {
          const slug = Object.entries(SLUG_TO_KEY).find(([, v]) => v === other.key)?.[0] ?? "";
          if (!slug) return null;
          return (
            <a
              key={other.key}
              href={path(`/search/${slug}/`)}
              className={`rounded-md border border-slate-200 bg-white px-3 py-1.5 transition hover:border-slate-400`}
            >
              <span className={`mr-1.5 inline-block size-1.5 rounded-full ${other.classes.bgStrong}`} aria-hidden />
              {other.name_ko}
            </a>
          );
        })}
      </nav>

      <SearchBox />

      <Suspense fallback={<p className="text-sm text-slate-500">불러오는 중…</p>}>
        <SearchResults laws={all} ministries={ministries} fixedHierarchy={key} />
      </Suspense>
    </div>
  );
}
