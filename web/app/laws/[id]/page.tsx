import { notFound } from "next/navigation";
import { getById, listAllIds } from "@/lib/db";
import { path } from "@/lib/paths";

export function generateStaticParams() {
  return listAllIds().map((id) => ({ id: String(id) }));
}

export default async function LawDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const law = getById(Number(id));
  if (!law || !law.title_ko) notFound();

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <header>
        <div className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-blue-700">
            홈
          </a>{" "}
          / {law.ministry_name_ko}
        </div>
        <h1 className="mt-2 text-2xl font-bold leading-tight">{law.title_ko}</h1>
        <p className="mt-2 text-sm italic text-slate-600">{law.title_id}</p>
      </header>

      <dl className="grid grid-cols-1 gap-3 rounded-lg border bg-white p-4 text-sm sm:grid-cols-2">
        <Field label="법령 번호" value={law.law_number} />
        <Field label="법령 종류" value={law.law_type} />
        <Field label="제정일" value={law.issuance_date} />
        <Field label="시행일" value={law.effective_date} />
        <Field label="상태" value={law.status} />
        <Field label="부처" value={law.ministry_name_ko} />
      </dl>

      {law.summary_ko && (
        <section>
          <h2 className="mb-2 text-base font-semibold">한국어 요약</h2>
          <p className="text-sm leading-relaxed text-slate-800">{law.summary_ko}</p>
        </section>
      )}

      {law.categories && law.categories.length > 0 && (
        <section>
          <h2 className="mb-2 text-base font-semibold">분야</h2>
          <div className="flex flex-wrap gap-1.5">
            {law.categories.map((c) => (
              <span
                key={c}
                className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700"
              >
                {c}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg border bg-white p-4 text-sm">
        <h2 className="mb-3 text-base font-semibold">원문 링크</h2>
        <ul className="space-y-1.5">
          <li>
            <a
              href={law.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-blue-700 hover:underline"
            >
              JDIH 페이지 (정부 공식)
            </a>
          </li>
          {law.pdf_url && (
            <li>
              <a
                href={law.pdf_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-700 hover:underline"
              >
                PDF 원문 다운로드
              </a>
            </li>
          )}
        </ul>
      </section>
    </article>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-medium">{value ?? "—"}</dd>
    </div>
  );
}
