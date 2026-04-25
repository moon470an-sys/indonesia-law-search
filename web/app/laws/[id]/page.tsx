import { notFound } from "next/navigation";
import { getById, listAllIds } from "@/lib/db";
import { CATEGORY_META, STATUS_META, STATUS_CLASSES } from "@/lib/meta";
import { classify, getHierarchy } from "@/lib/hierarchy";
import { path } from "@/lib/paths";

const TABS = [
  { code: "title",    label: "한국어 요약" },
  { code: "body",     label: "인니어 원문" },
  { code: "article",  label: "조문내용" },
  { code: "addendum", label: "부칙" },
  { code: "amendment", label: "제정·개정문" },
  { code: "links",    label: "원문 자료" },
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
  const h = getHierarchy(classify(law));

  return (
    <article className="space-y-8">
      {/* 메타 박스 — 좌측 위계 색상 막대 */}
      <header className={`relative overflow-hidden rounded-lg border border-slate-200 bg-white p-7 shadow-sm`}>
        <span className={`absolute inset-y-0 left-0 w-1.5 ${h.classes.bgStrong}`} aria-hidden />

        <nav className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-brand">홈</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <a
            href={path(`/search/?category=${law.category}`)}
            className="hover:text-brand"
          >
            {CATEGORY_META[law.category]?.name_ko}
          </a>
          {law.ministry_name_ko && (
            <>
              <span className="mx-1.5 text-slate-300">/</span>
              <span>{law.ministry_name_ko}</span>
            </>
          )}
        </nav>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ring-1 ${h.classes.badge}`}
          >
            Rank {h.rank} · {h.name_ko}
          </span>
          <span className="text-xs text-slate-500 italic">{h.name_id}</span>
        </div>

        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-bold leading-snug text-slate-900 sm:text-[26px]">
            {law.title_ko}
          </h1>
          <span
            className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${STATUS_CLASSES[law.status]}`}
          >
            {status.name_ko}
          </span>
        </div>
        <p className="mt-2 text-base italic leading-relaxed text-slate-600">
          {law.title_id}
        </p>
        {law.title_en && (
          <p className="mt-1 text-sm leading-relaxed text-slate-500">{law.title_en}</p>
        )}

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-slate-100 pt-5 text-sm sm:grid-cols-4">
          <Field label="법령번호" value={law.law_number} />
          <Field label="위계" value={`${law.law_type} (${h.name_ko})`} />
          <Field label="제정일" value={law.enactment_date} />
          <Field label="공포일" value={law.promulgation_date} />
          <Field label="시행일" value={law.effective_date} />
          <Field label="소관부처" value={law.ministry_name_ko} />
          <Field label="분류" value={CATEGORY_META[law.category]?.name_ko} />
          <Field label="원본출처" value={prettySource(law.source)} />
        </dl>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[200px_1fr]">
        <nav className="space-y-1.5 text-sm">
          {TABS.map((t) => (
            <a
              key={t.code}
              href={`#${t.code}`}
              className="block rounded-md border border-slate-200 bg-white px-4 py-2.5 font-medium text-slate-700 transition-colors hover:border-brand hover:text-brand"
            >
              {t.label}
            </a>
          ))}
        </nav>

        <div className="space-y-6">
          <Section id="title" heading="한국어 요약">
            <p className="text-[15px] leading-[1.85] text-slate-800">
              {law.summary_ko ?? (
                <span className="text-slate-400">아직 요약이 등록되지 않았습니다.</span>
              )}
            </p>
            {law.categories && law.categories.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {law.categories.map((c) => (
                  <span
                    key={c}
                    className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </Section>

          <Section id="body" heading="인니어 원문">
            <p className="text-[15px] leading-[1.85] text-slate-700">{law.title_id}</p>
            <p className="mt-3 text-xs text-slate-400">
              조문 단위 본문은 후속 enrich 단계에서 채워집니다.
            </p>
          </Section>

          <Section id="links" heading="원문 자료">
            <ul className="space-y-2 text-[15px]">
              <li>
                <a
                  href={law.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-brand hover:underline"
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
                    className="font-medium text-brand hover:underline"
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
                    className="font-medium text-brand hover:underline"
                  >
                    → 공식 영문 번역본 (Terjemahresmi)
                  </a>
                </li>
              )}
            </ul>
          </Section>
        </div>
      </div>
    </article>
  );
}

function Section({
  id,
  heading,
  children,
}: {
  id: string;
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="scroll-mt-24 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="mb-3 text-lg font-bold text-slate-900">{heading}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-[15px] font-medium text-slate-800 tabular-nums">
        {value ?? "—"}
      </dd>
    </div>
  );
}

function prettySource(s: string): string {
  return ({
    peraturan_go_id: "peraturan.go.id",
    jdih_dephub: "JDIH 교통부",
    jdih_esdm: "JDIH ESDM",
    jdih_bkpm: "JDIH BKPM",
    jdih_kemenkeu: "JDIH 재무부",
    jdih_kemendag: "JDIH 무역부",
    mk_go_id: "헌법재판소",
    mahkamahagung_go_id: "대법원",
    lainnya: "기타",
  } as Record<string, string>)[s] ?? s;
}
