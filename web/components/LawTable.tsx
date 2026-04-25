import { path } from "@/lib/paths";
import { CATEGORY_META, STATUS_META, STATUS_CLASSES, type Law } from "@/lib/meta";

export default function LawTable({ laws }: { laws: Law[] }) {
  if (laws.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-8 text-center text-base text-slate-500">
        검색 결과가 없습니다.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-[15px]">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-5 py-3 text-left">법령명</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">위계</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">법령번호</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">소관</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">공포일</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">상태</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {laws.map((law) => {
            const status = STATUS_META[law.status];
            return (
              <tr key={law.id} className="transition-colors hover:bg-blue-50/40">
                <td className="px-5 py-4 align-top">
                  <a
                    href={path(`/laws/${law.id}/`)}
                    className="block text-[15px] font-semibold leading-snug text-slate-900 hover:text-brand hover:underline"
                  >
                    {law.title_ko ?? law.title_id}
                  </a>
                  {law.title_ko && (
                    <p className="mt-1 text-[13px] italic leading-relaxed text-slate-500 line-clamp-2">
                      {law.title_id}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                      {CATEGORY_META[law.category]?.name_ko ?? law.category}
                    </span>
                    {law.categories?.slice(0, 4).map((c) => (
                      <span
                        key={c}
                        className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap">
                  {law.law_type}
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap">
                  {law.law_number}
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap">
                  {law.ministry_name_ko ?? "—"}
                </td>
                <td className="px-3 py-4 align-top text-sm text-slate-600 whitespace-nowrap tabular-nums">
                  {law.promulgation_date ?? "—"}
                </td>
                <td className="px-3 py-4 align-top">
                  <span
                    className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${STATUS_CLASSES[law.status]}`}
                  >
                    {status.name_ko}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
