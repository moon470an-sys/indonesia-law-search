import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResults";
import { listAllMin, listMinistries, type LawMin } from "@/lib/db";
import { classify, HIERARCHIES } from "@/lib/hierarchy";

export const dynamic = "force-static";

const PER_HIERARCHY = 200;

export default function HomePage() {
  const all = listAllMin();
  const ministries = listMinistries();

  // Bucket by hierarchy, take the most recent N per bucket so the inline
  // payload stays small while every hierarchy shows up grouped.
  const buckets = new Map<string, LawMin[]>();
  for (const law of all) {
    const k = classify(law);
    const arr = buckets.get(k) ?? [];
    arr.push(law);
    buckets.set(k, arr);
  }

  const sample: LawMin[] = [];
  // Iterate in canonical hierarchy rank so the SearchResults grouped layout
  // is stable even when buckets are sliced.
  for (const h of HIERARCHIES) {
    const items = buckets.get(h.key);
    if (!items || items.length === 0) continue;
    items.sort((a, b) => {
      const ta = a.title_ko ? 0 : 1;
      const tb = b.title_ko ? 0 : 1;
      if (ta !== tb) return ta - tb;
      return (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? "");
    });
    sample.push(...items.slice(0, PER_HIERARCHY));
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 sm:text-[26px]">
          법위계별 법령 분포
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          전체 <span className="font-bold text-slate-900 tabular-nums">{all.length.toLocaleString()}</span>건 중
          위계별 최신 {PER_HIERARCHY.toLocaleString()}건씩을 표시합니다. 각 그룹의 ‘인덱스 →’를 통해 전체 목록으로 이동할 수 있습니다.
        </p>
      </header>

      <SearchBox />

      <Suspense fallback={<p className="text-sm text-slate-500">불러오는 중…</p>}>
        <SearchResults laws={sample} ministries={ministries} />
      </Suspense>
    </div>
  );
}
