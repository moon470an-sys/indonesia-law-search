import { Suspense } from "react";
import { notFound } from "next/navigation";
import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResults";
import { listAllMin, listMinistries } from "@/lib/db";
import { MINISTRIES, getMinistry } from "@/lib/ministries";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

export function generateStaticParams() {
  return MINISTRIES.map((m) => ({ code: m.code }));
}

export default async function MinistryIndexPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const meta = getMinistry(code);
  if (!meta) notFound();

  const HARD_CAP = 2000;
  const fullBucket = listAllMin().filter((l) => l.ministry_code === code);
  const sorted = [...fullBucket].sort((a, b) => {
    const ta = a.title_ko ? 0 : 1;
    const tb = b.title_ko ? 0 : 1;
    if (ta !== tb) return ta - tb;
    return (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? "");
  });
  const all = sorted.slice(0, HARD_CAP);
  const truncated = fullBucket.length > HARD_CAP;
  const translated = fullBucket.filter((l) => l.title_ko != null).length;
  const allMinistries = listMinistries();

  return (
    <div className="space-y-6">
      <header className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <nav className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-brand">홈</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <a href={path("/ministries/")} className="hover:text-brand">부처 디렉토리</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <span>{meta.name_ko}</span>
        </nav>
        <div className="mt-3 flex items-center gap-3">
          <span className="text-3xl" aria-hidden>{meta.icon}</span>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 sm:text-[26px]">
              {meta.name_ko}
            </h1>
            <p className="text-sm italic text-slate-500">{meta.name_id}</p>
          </div>
        </div>
        <p className="mt-3 text-sm text-slate-600">
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

      <SearchBox />

      <Suspense fallback={<p className="text-sm text-slate-500">불러오는 중…</p>}>
        <SearchResults laws={all} ministries={allMinistries} />
      </Suspense>
    </div>
  );
}
