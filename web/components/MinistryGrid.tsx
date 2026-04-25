import { path } from "@/lib/paths";

const MINISTRIES = [
  { code: "kemenhub",  label: "교통부",          icon: "🚢" },
  { code: "esdm",      label: "에너지광물자원부", icon: "⚡" },
  { code: "bkpm",      label: "투자조정청",       icon: "📈" },
  { code: "kemenkeu",  label: "재무부",          icon: "💰" },
  { code: "kemendag",  label: "무역부",          icon: "🛳" },
  { code: "kumham",    label: "법무인권부",       icon: "⚖️" },
];

export default function MinistryGrid({
  counts,
}: {
  counts: { code: string; count: number }[];
}) {
  const map = new Map(counts.map((c) => [c.code, c.count] as const));
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
      {MINISTRIES.map((m) => {
        const cnt = map.get(m.code) ?? 0;
        return (
          <a
            key={m.code}
            href={path(`/search/?ministry=${m.code}`)}
            className="flex flex-col items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-5 text-center transition hover:border-brand hover:bg-blue-50/40 hover:shadow-sm"
          >
            <span className="text-3xl" aria-hidden>
              {m.icon}
            </span>
            <span className="text-sm font-semibold text-slate-800">{m.label}</span>
            <span className="text-xs text-slate-500 tabular-nums">
              {cnt.toLocaleString()}건
            </span>
          </a>
        );
      })}
    </div>
  );
}
