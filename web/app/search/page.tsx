import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResults";
import { listMinistries, search } from "@/lib/db";

export const dynamic = "force-static";

export default function SearchPage() {
  const laws = search({ limit: 5000 });
  const ministries = listMinistries();

  return (
    <div className="space-y-6">
      <SearchBox />
      <Suspense fallback={<p className="text-sm text-slate-500">불러오는 중…</p>}>
        <SearchResults laws={laws} ministries={ministries} />
      </Suspense>
    </div>
  );
}
