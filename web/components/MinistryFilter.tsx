import { path } from "@/lib/paths";

type Ministry = { code: string; name_ko: string; count: number };

export default function MinistryFilter({
  ministries,
  active,
  baseHref,
}: {
  ministries: Ministry[];
  active?: string;
  baseHref: string;
}) {
  const base = path(baseHref);
  const sep = base.includes("?") ? "&" : "?";

  return (
    <aside className="rounded-lg border bg-white p-4">
      <h4 className="text-sm font-semibold text-slate-700">부처</h4>
      <ul className="mt-3 space-y-1 text-sm">
        <li>
          <a
            href={base}
            className={
              active
                ? "text-slate-600 hover:text-blue-700"
                : "font-semibold text-blue-700"
            }
          >
            전체
          </a>
        </li>
        {ministries.map((m) => (
          <li key={m.code} className="flex items-center justify-between">
            <a
              href={`${base}${sep}ministry=${m.code}`}
              className={
                active === m.code
                  ? "font-semibold text-blue-700"
                  : "text-slate-600 hover:text-blue-700"
              }
            >
              {m.name_ko}
            </a>
            <span className="text-xs text-slate-400">{m.count}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
