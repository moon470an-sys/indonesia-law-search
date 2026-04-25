import LawCard from "@/components/LawCard";
import MinistryFilter from "@/components/MinistryFilter";
import SearchBox from "@/components/SearchBox";
import { listMinistries, search } from "@/lib/db";

export const dynamic = "force-static";

type SearchParams = { q?: string; ministry?: string };

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { q = "", ministry } = await searchParams;
  const results = search({ q, ministry, limit: 100 });
  const ministries = listMinistries();

  const baseHref = `/search/${q ? `?q=${encodeURIComponent(q)}` : ""}`;

  return (
    <div className="space-y-6">
      <SearchBox defaultQuery={q} />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
        <MinistryFilter
          ministries={ministries}
          active={ministry}
          baseHref={baseHref}
        />
        <div>
          <p className="mb-3 text-sm text-slate-600">
            {results.length === 0
              ? "검색 결과가 없습니다."
              : `${results.length}건의 결과 ${q ? `"${q}"` : ""}`}
          </p>
          <div className="grid gap-3">
            {results.map((law) => (
              <LawCard key={law.id} law={law} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
