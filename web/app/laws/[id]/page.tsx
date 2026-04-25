import { notFound } from "next/navigation";
import { getById, listAllIds } from "@/lib/db";
import { CATEGORY_META, STATUS_META, STATUS_CLASSES } from "@/lib/meta";
import { path } from "@/lib/paths";

const TABS = [
  { code: "title",         label: "법령명" },
  { code: "body",          label: "법령본문" },
  { code: "article",       label: "조문내용" },
  { code: "article_title", label: "조문제목" },
  { code: "addendum",      label: "부칙" },
  { code: "amendment",     label: "제정·개정문" },
];

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

  const status = STATUS_META[law.status];

  return (
    <article className="space-y-6">
      {/* 메타정보 박스 */}
      <header className="rounded-md border border-slate-200 bg-white p-5">
        <div className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-blue-700">홈</a>
          {" / "}
          <a href={path(`/search/?category=${law.category}`)} className="hover:text-blue-700">
            {CATEGORY_META[law.category]?.name_ko}
          </a>
          {" / "}
          {law.ministry_name_ko ?? "—"}
        </div>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-bold leading-tight">{law.title_ko}</h1>
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_CLASSES[law.status]}`}
          >
            {status.name_ko}
          </span>
        </div>
        <p className="mt-1 text-sm italic text-slate-600">{law.title_id}</p>
        {law.title_en && (
          <p className="mt-0.5 text-xs text-slate-500">{law.title_en}</p>
        )}

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <Field label="법령번호" value={law.law_number} />
          <Field label="위계" value={law.law_type} />
          <Field label="제정일" value={law.enactment_date} />
          <Field label="공포일" value={law.promulgation_date} />
          <Field label="시행일" value={law.effective_date} />
          <Field label="소관부처" value={law.ministry_name_ko} />
          <Field label="분류" value={CATEGORY_META[law.category]?.name_ko} />
          <Field label="원본출처" value={prettySource(law.source)} />
        </dl>
      </header>

      {/* 좌측 탭 + 우측 콘텐츠 (탭 컨텐츠는 데이터 채워지면 의미 가짐) */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-[180px_1fr]">
        <nav className="space-y-1 text-sm">
          {TABS.map((t) => (
            <a
              key={t.code}
              href={`#${t.code}`}
              className="block rounded-md border border-slate-200 bg-white px-3 py-2 text-slate-700 hover:border-blue-300 hover:text-blue-700"
            >
              {t.label}
            </a>
          ))}
        </nav>

        <div className="space-y-6">
          <section id="title" className="rounded-md border border-slate-200 bg-white p-5">
            <h2 className="mb-2 text-base font-bold">한국어 요약</h2>
            <p className="text-sm leading-relaxed text-slate-800">
              {law.summary_ko ?? <span className="text-slate-400">아직 요약이 등록되지 않았습니다.</span>}
            </p>
            {law.categories && law.categories.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
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
          </section>

          <section id="body" className="rounded-md border border-slate-200 bg-white p-5">
            <h2 className="mb-2 text-base font-bold">인니어 원문</h2>
            <p className="text-sm leading-relaxed text-slate-700">{law.title_id}</p>
            <p className="mt-3 text-xs text-slate-400">
              조문 단위 본문은 후속 enrich 단계에서 채워집니다.
            </p>
          </section>

          <section id="amendment" className="rounded-md border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-base font-bold">원문 자료</h2>
            <ul className="space-y-1.5 text-sm">
              <li>
                <a
                  href={law.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-700 hover:underline"
                >
                  → 원본 페이지 ({prettySource(law.source)})
                </a>
              </li>
              {law.pdf_url_id && (
                <li>
                  <a
                    href={law.pdf_url_id}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-700 hover:underline"
                  >
                    → PDF 원문 다운로드 (인니어)
                  </a>
                </li>
              )}
              {law.pdf_url_en && (
                <li>
                  <a
                    href={law.pdf_url_en}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-700 hover:underline"
                  >
                    → 공식 영문 번역본 (Terjemahresmi)
                  </a>
                </li>
              )}
            </ul>
          </section>
        </div>
      </div>
    </article>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-medium text-slate-800">{value ?? "—"}</dd>
    </div>
  );
}

function prettySource(s: string): string {
  return {
    peraturan_go_id: "peraturan.go.id",
    jdih_dephub: "JDIH 교통부",
    jdih_esdm: "JDIH ESDM",
    jdih_bkpm: "JDIH BKPM",
    jdih_kemenkeu: "JDIH 재무부",
    jdih_kemendag: "JDIH 무역부",
    mk_go_id: "헌법재판소",
    mahkamahagung_go_id: "대법원",
    lainnya: "기타",
  }[s] ?? s;
}
