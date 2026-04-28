import { notFound } from "next/navigation";
import { getById, listAllIds } from "@/lib/db";
import { CATEGORY_META, STATUS_META, STATUS_CLASSES } from "@/lib/meta";
import { classify, getHierarchy } from "@/lib/hierarchy";
import { path } from "@/lib/paths";
import { WaybackLink } from "@/components/WaybackLink";

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

      <Section id="links" heading="원문 자료">
        <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
          <strong>안내</strong> · 일부 도메인은 한국 통신망에서 직접 접속이 차단되거나
          원본 서버가 일시적으로 다운된 경우가 있습니다. 아래 4개 링크 중 하나를 시도하세요:
          <strong>🌐 텍스트로 보기</strong>(외부 서버로 라이브 페이지 fetch),
          <strong>📦 Wayback</strong>·<strong>🗃 archive.ph</strong>(보관된 캐시),
          <strong>🔎 Google</strong>(원본·아카이브 모두 안 될 때 다른 출처에서 본문 찾기).
        </p>
        <SourceLinks law={law} />
      </Section>
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

function SourceLinks({ law }: { law: { source_url: string; pdf_url_id: string | null; pdf_url_en: string | null; source: string } }) {
  const items: { label: string; url: string }[] = [
    { label: `원본 페이지 (${prettySource(law.source)})`, url: law.source_url },
  ];
  if (law.pdf_url_id) items.push({ label: "PDF 원문 (인니어)", url: law.pdf_url_id });
  if (law.pdf_url_en) items.push({ label: "공식 영문 번역본 (Terjemahresmi)", url: law.pdf_url_en });

  return (
    <ul className="space-y-3 text-[14px]">
      {items.map((it) => (
        <li key={it.url} className="rounded-md border border-slate-200 bg-slate-50/60 p-3">
          <p className="mb-1.5 text-xs font-bold text-slate-700">{it.label}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            <a
              href={it.url}
              target="_blank"
              rel="noreferrer"
              className="text-brand hover:underline"
              title="원본 사이트로 직접 이동 (한국에서 차단될 수 있음)"
            >
              ↗ 직접 열기
            </a>
            <WaybackLink url={it.url} label="📦 Wayback Machine" />
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * Wayback indexes peraturan.go.id snapshots under the `www.` host while our
 * DB stores the bare host. Without canonicalization the calendar page lists
 * 0 captures even when crawls exist. Rewrite known hosts so the link lands
 * on a populated calendar.
 */
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
