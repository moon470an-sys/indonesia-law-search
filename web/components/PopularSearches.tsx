import { path } from "@/lib/paths";

const POPULAR = [
  { term: "SIUPAL", note: "선박운송업 면허" },
  { term: "PMA", note: "외국인투자" },
  { term: "Cabotage", note: "카보타지" },
  { term: "OSS", note: "원스톱 통합 서비스" },
  { term: "BPJS", note: "사회보장보험" },
  { term: "TKDN", note: "현지조달비율" },
  { term: "Halal", note: "할랄 인증" },
  { term: "DNI", note: "투자 네거티브 리스트" },
];

export default function PopularSearches() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
      <span className="font-bold text-slate-700">인기 검색어</span>
      {POPULAR.map((p, i) => (
        <a
          key={p.term}
          href={path(`/search/?q=${encodeURIComponent(p.term)}`)}
          className="text-slate-600 transition-colors hover:text-brand"
          title={p.note}
        >
          <span className="mr-1 text-xs font-semibold text-slate-400">
            {i + 1}.
          </span>
          {p.term}
        </a>
      ))}
    </div>
  );
}
