import { path } from "@/lib/paths";
import { CATEGORY_META, STATUS_META, type Law, type LawStatus } from "@/lib/db";

const STATUS_CLASSES: Record<LawStatus, string> = {
  berlaku:          "bg-emerald-50 text-emerald-700",
  diubah:           "bg-amber-50 text-amber-700",
  dicabut:          "bg-rose-50 text-rose-700",
  dicabut_sebagian: "bg-rose-50 text-rose-700",
  belum_berlaku:    "bg-slate-100 text-slate-600",
  tidak_diketahui:  "bg-slate-100 text-slate-600",
};

export default function LawTable({ laws }: { laws: Law[] }) {
  if (laws.length === 0) {
    return (
      <p className="rounded-md border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
        검색 결과가 없습니다.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2 text-left">법령명</th>
            <th className="px-3 py-2 text-left">위계</th>
            <th className="px-3 py-2 text-left">법령번호</th>
            <th className="px-3 py-2 text-left">소관부처</th>
            <th className="px-3 py-2 text-left">공포일</th>
            <th className="px-3 py-2 text-left">상태</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {laws.map((law) => {
            const status = STATUS_META[law.status];
            return (
              <tr key={law.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <a
                    href={path(`/laws/${law.id}/`)}
                    className="block font-semibold text-blue-800 hover:underline"
                  >
                    {law.title_ko ?? law.title_id}
                  </a>
                  {law.title_ko && (
                    <p className="mt-0.5 text-xs italic text-slate-500 line-clamp-1">
                      {law.title_id}
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                      {CATEGORY_META[law.category]?.name_ko ?? law.category}
                    </span>
                    {law.categories?.slice(0, 3).map((c) => (
                      <span
                        key={c}
                        className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-3 align-top text-xs text-slate-600">{law.law_type}</td>
                <td className="px-3 py-3 align-top text-xs text-slate-600">{law.law_number}</td>
                <td className="px-3 py-3 align-top text-xs text-slate-600">
                  {law.ministry_name_ko ?? "—"}
                </td>
                <td className="px-3 py-3 align-top text-xs text-slate-600">
                  {law.promulgation_date ?? "—"}
                </td>
                <td className="px-3 py-3 align-top">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_CLASSES[law.status]}`}
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
