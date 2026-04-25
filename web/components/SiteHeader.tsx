import { path } from "@/lib/paths";
import { HIERARCHIES } from "@/lib/hierarchy";

const SLUG: Record<string, string> = {
  UUD: "uud", TAP: "tap", UU: "uu", PP: "pp", Perpres: "perpres",
  Permen: "permen", Kepmen: "kepmen", Perda_Prov: "perda_prov",
  Perda_Kab: "perda_kab", Lainnya: "lainnya",
};

// 헤더 nav에 노출할 위계 (UUD/TAP/Lainnya는 데이터 풀이 적어 메뉴에서 제외)
const NAV_KEYS = ["UU", "PP", "Perpres", "Permen", "Kepmen", "Perda_Prov", "Perda_Kab"];

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
        <a href={path("/")} className="flex shrink-0 items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-md bg-brand text-base font-bold text-white shadow-sm">
            법
          </span>
          <span className="text-lg font-bold tracking-tight text-slate-900">
            인도네시아 법령정보센터
          </span>
        </a>

        <a
          href={path("/search/?ai=1")}
          className="hidden shrink-0 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100 md:inline-block"
          title="향후 확장 예정"
        >
          AI 법령검색
        </a>
      </div>
      <PrimaryNav />
    </header>
  );
}

function PrimaryNav() {
  const items = HIERARCHIES.filter((h) => NAV_KEYS.includes(h.key));
  return (
    <nav className="bg-brand text-white">
      <ul className="mx-auto flex max-w-7xl items-stretch overflow-x-auto px-2 text-[15px] font-medium">
        {items.map((h) => (
          <li key={h.key} className="relative">
            <a
              href={path(`/search/?hierarchy=${SLUG[h.key]}`)}
              className="flex items-center gap-2 whitespace-nowrap px-4 py-3.5 transition-colors hover:bg-brand-dark"
            >
              <span className="grid size-5 place-items-center rounded text-[10px] font-bold text-white/90 ring-1 ring-white/30 tabular-nums">
                {h.rank}
              </span>
              {h.name_ko}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
