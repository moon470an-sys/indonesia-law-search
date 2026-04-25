import type { Law } from "@/lib/meta";
import { HIERARCHIES, classify, type HierarchyKey } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

const SLUG: Record<HierarchyKey, string> = {
  UUD:        "uud",
  TAP:        "tap",
  UU:         "uu",
  PP:         "pp",
  Perpres:    "perpres",
  Permen:     "permen",
  Kepmen:     "kepmen",
  Perda_Prov: "perda_prov",
  Perda_Kab:  "perda_kab",
  Lainnya:    "lainnya",
};

export default function HierarchyMap({ laws }: { laws: Law[] }) {
  // Bucket laws by hierarchy
  const buckets = new Map<HierarchyKey, Law[]>();
  for (const law of laws) {
    const k = classify(law);
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k)!.push(law);
  }

  // Render buckets in canonical rank order (only those with data)
  const populated = HIERARCHIES.filter((h) => (buckets.get(h.key)?.length ?? 0) > 0);

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {populated.map((h) => {
        const items = buckets.get(h.key)!;
        const recent = [...items]
          .sort((a, b) => (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? ""))
          .slice(0, 3);

        return (
          <a
            key={h.key}
            href={path(`/search/?hierarchy=${SLUG[h.key]}`)}
            className={`group relative flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 transition hover:shadow-lg hover:ring-2 ${h.classes.ring}`}
          >
            {/* 좌측 색상 강조 막대 */}
            <span
              className={`absolute inset-y-3 left-0 w-1 rounded-r ${h.classes.bgStrong}`}
              aria-hidden
            />

            {/* 헤더: 위계 이름 + 카운트 */}
            <header className="flex items-baseline justify-between gap-2 pl-3">
              <div>
                <p className={`text-xs font-bold uppercase tracking-wider ${h.classes.text}`}>
                  Rank {h.rank}
                </p>
                <h3 className="mt-0.5 text-lg font-bold leading-tight text-slate-900">
                  {h.name_ko}
                </h3>
                <p className="mt-0.5 text-xs text-slate-500">{h.name_id}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-slate-900 tabular-nums">
                  {items.length.toLocaleString()}
                </p>
                <p className="text-xs text-slate-500">건</p>
              </div>
            </header>

            {/* 최근 3건 */}
            <ul className="space-y-1.5 border-t border-slate-100 pl-3 pt-3 text-[13px]">
              {recent.map((law) => (
                <li
                  key={law.id}
                  className="line-clamp-1 text-slate-600 group-hover:text-slate-800"
                >
                  · {law.title_ko ?? law.title_id}
                </li>
              ))}
            </ul>

            <span className={`mt-auto pl-3 text-xs font-semibold ${h.classes.text}`}>
              모두 보기 →
            </span>
          </a>
        );
      })}
    </div>
  );
}
