import LawTable from "@/components/LawTable";
import SearchBox from "@/components/SearchBox";
import {
  CATEGORY_META, listMinistries, search,
  type LawCategory, type LawStatus,
} from "@/lib/db";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

type SearchParams = {
  q?: string;
  field?: string;
  category?: string;
  ministry?: string;
  status?: string;
  era?: string;
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const q = sp.q ?? "";
  const category = isCategory(sp.category) ? (sp.category as LawCategory) : undefined;
  const ministry = sp.ministry || undefined;
  const status = isStatus(sp.status) ? (sp.status as LawStatus) : undefined;
  const era = sp.era === "modern" || sp.era === "lama" || sp.era === "kolonial"
    ? sp.era as "modern" | "lama" | "kolonial"
    : undefined;
  const field = (sp.field ?? "title") as
    | "title" | "body" | "article_title" | "article_body" | "addendum" | "amendment";

  const results = search({ q, category, ministry, status, era, field, limit: 100 });
  const ministries = listMinistries();

  return (
    <div className="space-y-6">
      <SearchBox defaultQuery={q} defaultField={field} />

      <SearchTabs active={field} q={q} />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
        <Sidebar
          q={q}
          category={category}
          ministry={ministry}
          status={status}
          era={era}
          ministries={ministries}
        />
        <div className="space-y-3">
          <ResultHeader count={results.length} q={q} />
          <LawTable laws={results} />
        </div>
      </div>
    </div>
  );
}

function isCategory(v: string | undefined): boolean {
  return !!v && v in CATEGORY_META;
}
function isStatus(v: string | undefined): boolean {
  return !!v && [
    "berlaku","diubah","dicabut","dicabut_sebagian",
    "belum_berlaku","tidak_diketahui",
  ].includes(v);
}

const FIELDS = [
  { code: "title",         label: "법령명" },
  { code: "body",          label: "법령본문" },
  { code: "article_body",  label: "조문내용" },
  { code: "article_title", label: "조문제목" },
  { code: "addendum",      label: "부칙" },
  { code: "amendment",     label: "제정·개정문" },
];

function SearchTabs({ active, q }: { active: string; q: string }) {
  return (
    <ul className="flex gap-1 overflow-x-auto border-b border-slate-200 text-sm">
      {FIELDS.map((f) => {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (f.code !== "title") params.set("field", f.code);
        const href = path(`/search/${params.toString() ? "?" + params : ""}`);
        return (
          <li key={f.code}>
            <a
              href={href}
              className={
                active === f.code
                  ? "block whitespace-nowrap border-b-2 border-blue-700 px-4 py-2 font-semibold text-blue-700"
                  : "block whitespace-nowrap px-4 py-2 text-slate-600 hover:text-blue-700"
              }
            >
              {f.label}
            </a>
          </li>
        );
      })}
    </ul>
  );
}

function ResultHeader({ count, q }: { count: number; q: string }) {
  return (
    <p className="text-sm text-slate-600">
      {count === 0 ? (
        "검색 결과가 없습니다."
      ) : (
        <>
          <span className="font-bold text-slate-900">{count}건</span> 의 결과
          {q ? <> · <span className="font-medium">"{q}"</span></> : null}
        </>
      )}
    </p>
  );
}

function Sidebar({
  q, category, ministry, status, era, ministries,
}: {
  q: string;
  category: LawCategory | undefined;
  ministry: string | undefined;
  status: LawStatus | undefined;
  era: string | undefined;
  ministries: { code: string; name_ko: string; count: number }[];
}) {
  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);

  const link = (extra: Record<string, string | undefined>) => {
    const p = new URLSearchParams(baseParams);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v);
    }
    return path(`/search/${p.toString() ? "?" + p : ""}`);
  };

  return (
    <aside className="space-y-4 text-sm">
      <FilterBox title="1차 메뉴">
        <FilterLink href={link({ category: undefined })} active={!category}>
          전체
        </FilterLink>
        {(Object.keys(CATEGORY_META) as LawCategory[]).map((c) => (
          <FilterLink key={c} href={link({ category: c })} active={category === c}>
            {CATEGORY_META[c].name_ko}
          </FilterLink>
        ))}
      </FilterBox>

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

      <FilterBox title="시대">
        <FilterLink href={link({ era: undefined })} active={!era}>
          전체
        </FilterLink>
        <FilterLink href={link({ era: "modern" })} active={era === "modern"}>
          현행
        </FilterLink>
        <FilterLink href={link({ era: "lama" })} active={era === "lama"}>
          근대
        </FilterLink>
        <FilterLink href={link({ era: "kolonial" })} active={era === "kolonial"}>
          식민지 시대
        </FilterLink>
      </FilterBox>
    </aside>
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
