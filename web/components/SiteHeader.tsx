import { path } from "@/lib/paths";
import SearchBox from "./SearchBox";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-4 md:gap-6">
        <a href={path("/")} className="flex shrink-0 items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-md bg-brand text-base font-bold text-white shadow-sm">
            법
          </span>
          <span className="text-lg font-bold tracking-tight text-slate-900">
            인도네시아 법령정보센터
          </span>
        </a>

        <div className="order-3 w-full md:order-2 md:flex-1">
          <SearchBox />
        </div>

        <a
          href={path("/search/?ai=1")}
          className="order-2 hidden shrink-0 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100 md:order-3 md:inline-block"
          title="향후 확장 예정"
        >
          AI 법령검색
        </a>
      </div>
      <PrimaryNav />
    </header>
  );
}

const PRIMARY = [
  { code: "peraturan",  label: "법령",         href: "/search/?category=peraturan" },
  { code: "keputusan",  label: "행정규칙",      href: "/search/?category=keputusan" },
  { code: "lampiran",   label: "별표·서식",    href: "/search/?category=lampiran" },
  { code: "perda",      label: "지방법규",      href: "/search/?category=perda" },
  { code: "putusan",    label: "판례·해석례",   href: "/search/?category=putusan" },
  { code: "kepkl",      label: "부처별 결정",   href: "/search/?category=kepkl" },
  { code: "perjanjian", label: "조약",         href: "/search/?category=perjanjian" },
  { code: "lainnya",    label: "기타",         href: "/search/?category=lainnya" },
];

function PrimaryNav() {
  return (
    <nav className="bg-brand text-white">
      <ul className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-2 text-[15px] font-medium">
        {PRIMARY.map((item) => (
          <li key={item.code}>
            <a
              href={path(item.href)}
              className="block whitespace-nowrap px-4 py-3.5 transition-colors hover:bg-brand-dark"
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
