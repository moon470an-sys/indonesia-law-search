import SearchBox from "@/components/SearchBox";
import SearchResults from "@/components/SearchResultsClient";
import { listAllMin, listMinistries } from "@/lib/db";
import { HIERARCHIES, classify, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

const SLUG: Record<HierarchyKey, string> = {
  UUD: "uud", TAP: "tap", UU: "uu", PP: "pp", Perpres: "perpres",
  Permen: "permen", Kepmen: "kepmen", Perda_Prov: "perda_prov",
  Perda_Kab: "perda_kab", Lainnya: "lainnya",
};

export default function SearchPage() {
  const all = listAllMin();
  // /search/ 메인은 번역된 행만 inline (현재 전체 inline은 25MB+ 무리)
  const translated = all.filter((l) => l.title_ko != null);
  const ministries = listMinistries();

  // 미번역 카운트는 위계별 안내 카드용
  const untranslatedByHierarchy = new Map<HierarchyKey, number>();
  for (const law of all) {
    if (law.title_ko != null) continue;
    const k = classify(law);
    untranslatedByHierarchy.set(k, (untranslatedByHierarchy.get(k) ?? 0) + 1);
  }

  return (
    <div className="space-y-6">
      <SearchBox />

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 md:grid-cols-5">
        {HIERARCHIES.filter((h) => (untranslatedByHierarchy.get(h.key) ?? 0) > 0).map((h) => {
          const cnt = untranslatedByHierarchy.get(h.key) ?? 0;
          return (
            <a
              key={h.key}
              href={path(`/search/${SLUG[h.key]}/`)}
              className={`flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2 transition hover:border-slate-400`}
            >
              <span className="flex items-center gap-1.5">
                <span className={`size-2 rounded-full ${h.classes.bgStrong}`} aria-hidden />
                <span className="font-semibold text-slate-700">{h.name_ko}</span>
              </span>
              <span className="text-slate-400 tabular-nums">+{cnt.toLocaleString()}</span>
            </a>
          );
        })}
      </div>

      <SearchResults laws={translated} ministries={ministries} />
    </div>
  );
}
