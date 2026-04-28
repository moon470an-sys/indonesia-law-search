import { path } from "@/lib/paths";
import { STATUS_META, STATUS_CLASSES, type LawStatus } from "@/lib/meta";
import HierarchyBadge from "./HierarchyBadge";

type Row = {
  id: number;
  category: string;
  law_type: string;
  law_number: string;
  title_id: string;
  title_ko: string | null;
  ministry_name_ko: string | null;
  promulgation_date: string | null;
  status: string;
  source_url: string;
};

export default function LawTable({
  laws,
  compact = false,
}: {
  laws: Row[];
  compact?: boolean;
}) {
  if (laws.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-8 text-center text-base text-slate-500">
        검색 결과가 없습니다.
      </p>
    );
  }

  return (
    <div
      className={
        compact
          ? "overflow-x-auto"
          : "overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm"
      }
    >
      <table className="w-full text-[15px]">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-5 py-3 text-left">법령명</th>
            {!compact && (
              <th className="px-3 py-3 text-left whitespace-nowrap">위계</th>
            )}
            <th className="px-3 py-3 text-left whitespace-nowrap">법령번호</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">소관</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">공포일</th>
            <th className="px-3 py-3 text-left whitespace-nowrap">상태</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {laws.map((law) => {
            const translated = !!law.title_ko;
            const status = STATUS_META[(law.status as LawStatus)] ?? STATUS_META.berlaku;
            const cls = STATUS_CLASSES[(law.status as LawStatus)] ?? STATUS_CLASSES.berlaku;
            const detailHref = translated
              ? path(`/laws/${law.id}/`)
              : law.source_url;
            return (
              <tr key={law.id} className="transition-colors hover:bg-blue-50/40">
                <td className="px-5 py-4 align-top">
                  <a
                    href={detailHref}
                    target={translated ? undefined : "_blank"}
                    rel={translated ? undefined : "noreferrer"}
                    className="block text-[15px] font-semibold leading-snug text-slate-900 hover:text-brand hover:underline"
                  >
                    {translated ? law.title_ko : law.title_id}
                  </a>
                  {!translated && (
                    <div className="mt-2">
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-200">
                        미번역
                      </span>
                    </div>
                  )}
                </td>
                {!compact && (
                  <td className="px-3 py-4 align-top whitespace-nowrap">
                    <HierarchyBadge law={law} />
                  </td>
                )}
                <td className="px-3 py-4 align-top text-sm text-slate-700 whitespace-nowrap tabular-nums">
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
                    className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${cls}`}
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
