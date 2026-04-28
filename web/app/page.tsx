import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResultsClient";
import { listAllMin, listMinistries } from "@/lib/db";

export const dynamic = "force-static";

export default function HomePage() {
  const all = listAllMin();
  const ministries = listMinistries();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 sm:text-[26px]">
          법위계별 법령 분포
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          전체 <span className="font-bold text-slate-900 tabular-nums">{all.length.toLocaleString()}</span>건
        </p>
      </header>

      <SearchBox />

      <SearchResults laws={all} ministries={ministries} />
    </div>
  );
}
