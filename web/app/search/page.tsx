import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResults";
import { listMinistries, search } from "@/lib/db";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

const FIELDS = [
  { code: "title",         label: "법령명" },
  { code: "body",          label: "법령본문" },
  { code: "article_body",  label: "조문내용" },
  { code: "article_title", label: "조문제목" },
  { code: "addendum",      label: "부칙" },
  { code: "amendment",     label: "제정·개정문" },
];

export default function SearchPage() {
  const laws = search({ limit: 5000 });
  const ministries = listMinistries();

  return (
    <div className="space-y-6">
      <SearchBox />

      <ul className="flex gap-1 overflow-x-auto border-b border-slate-200 text-sm">
        {FIELDS.map((f) => (
          <li key={f.code}>
            <a
              href={path(f.code === "title" ? "/search/" : `/search/?field=${f.code}`)}
              className="block whitespace-nowrap px-4 py-2.5 font-medium text-slate-600 transition-colors hover:text-brand"
            >
              {f.label}
            </a>
          </li>
        ))}
      </ul>

      <Suspense fallback={<p className="text-sm text-slate-500">불러오는 중…</p>}>
        <SearchResults laws={laws} ministries={ministries} />
      </Suspense>
    </div>
  );
}
