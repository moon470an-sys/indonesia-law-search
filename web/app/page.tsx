import HierarchyMap from "@/components/HierarchyMap";
import LawTable from "@/components/LawTable";
import MinistryGrid from "@/components/MinistryGrid";
import PopularSearches from "@/components/PopularSearches";
import { listAllMin, listMinistries } from "@/lib/db";
import { path } from "@/lib/paths";

export default function HomePage() {
  const all = listAllMin();
  const recent = [...all]
    .filter((l) => l.title_ko)
    .sort((a, b) => (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? ""))
    .slice(0, 8);
  const ministries = listMinistries();

  return (
    <div className="space-y-12">
      <PopularSearches />

      <Section
        title="법위계별 분포"
        subtitle={`인도네시아 법령은 UU(법률) → PP(정부령) → Perpres(대통령령) → Permen(부령) → Perda(지방조례)의 수직 위계로 구성됩니다. 전체 ${all.length.toLocaleString()}건 메타가 등록되어 있습니다.`}
        href="/search/"
      >
        <HierarchyMap laws={all} />
      </Section>

      <Section title="최신법령" subtitle="최근 공포된 한국어 번역 8건" href="/search/?recent=30">
        <LawTable laws={recent} />
      </Section>

      <Section title="부처별 빠른 진입" subtitle="소관 부처로 검색" href="/search/">
        <MinistryGrid counts={ministries} />
      </Section>
    </div>
  );
}

function Section({
  title,
  subtitle,
  href,
  children,
}: {
  title: string;
  subtitle?: string;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="mb-5 flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 sm:text-2xl">{title}</h2>
          {subtitle && (
            <p className="mt-1 text-sm leading-relaxed text-slate-500">{subtitle}</p>
          )}
        </div>
        <a
          href={path(href)}
          className="shrink-0 text-sm font-medium text-brand hover:underline"
        >
          더보기 →
        </a>
      </header>
      {children}
    </section>
  );
}
