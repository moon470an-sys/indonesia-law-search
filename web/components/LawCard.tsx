import type { Law } from "@/lib/db";
import { path } from "@/lib/paths";

export default function LawCard({ law }: { law: Law }) {
  return (
    <a
      href={path(`/laws/${law.id}/`)}
      className="block rounded-lg border bg-white p-4 shadow-sm transition hover:shadow-md"
    >
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className="rounded bg-slate-100 px-2 py-0.5">{law.ministry_name_ko}</span>
        {law.law_type && <span>{law.law_type}</span>}
        {law.issuance_date && <span>· {law.issuance_date}</span>}
      </div>
      <h3 className="mt-2 text-base font-semibold leading-snug">
        {law.title_ko ?? law.title_id}
      </h3>
      {law.title_ko && (
        <p className="mt-1 text-xs text-slate-500 line-clamp-2">{law.title_id}</p>
      )}
      {law.summary_ko && (
        <p className="mt-2 text-sm text-slate-700 line-clamp-3">{law.summary_ko}</p>
      )}
      {law.categories && law.categories.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {law.categories.map((c) => (
            <span
              key={c}
              className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}
