import { MINISTRIES, getMinistry } from "@/lib/ministries";
import { path } from "@/lib/paths";

export default function MinistryGrid({
  counts,
  limit = 12,
}: {
  counts: { code: string; count: number }[];
  limit?: number;
}) {
  const sorted = [...counts]
    .filter((c) => getMinistry(c.code))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        {sorted.map((c) => {
          const m = getMinistry(c.code)!;
          return (
            <a
              key={c.code}
              href={path(`/ministries/${c.code}/`)}
              className="flex flex-col items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-5 text-center transition hover:border-brand hover:bg-blue-50/40 hover:shadow-sm"
            >
              <span className="text-3xl" aria-hidden>{m.icon}</span>
              <span className="text-[13px] font-semibold leading-tight text-slate-800">
                {m.name_ko}
              </span>
              <span className="text-xs text-slate-500 tabular-nums">
                {c.count.toLocaleString()}건
              </span>
            </a>
          );
        })}
      </div>
      <div className="flex justify-end">
        <a
          href={path("/ministries/")}
          className="text-sm font-medium text-brand hover:underline"
        >
          전체 {MINISTRIES.length}개 부처 →
        </a>
      </div>
    </div>
  );
}
