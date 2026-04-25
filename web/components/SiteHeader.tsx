import { path } from "@/lib/paths";
import SearchBox from "./SearchBox";

export default function SiteHeader() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
        <a href={path("/")} className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-md bg-blue-700 text-sm font-bold text-white">
            법
          </span>
          <span className="text-lg font-bold tracking-tight">
            인도네시아 법령정보센터
          </span>
        </a>

        <div className="flex-1">
          <SearchBox />
        </div>

        <a
          href={path("/search/?ai=1")}
          className="hidden rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100 md:inline-block"
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
  { code: "lainnya",    label: "기타 정보",     href: "/search/?category=lainnya" },
];

function PrimaryNav() {
  return (
    <nav className="bg-blue-700 text-white">
      <ul className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-2 text-sm font-medium">
        {PRIMARY.map((item) => (
          <li key={item.code}>
            <a
              href={path(item.href)}
              className="block whitespace-nowrap px-4 py-3 hover:bg-blue-600"
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
