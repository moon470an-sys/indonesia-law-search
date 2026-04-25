import LawTable from "@/components/LawTable";
import MinistryGrid from "@/components/MinistryGrid";
import PopularSearches from "@/components/PopularSearches";
import { categoryCounts, listMinistries, listRecent } from "@/lib/db";
import { CATEGORY_META, type LawCategory } from "@/lib/meta";
import { path } from "@/lib/paths";

export default function HomePage() {
  const recent = listRecent(10);
  const ministries = listMinistries();
  const counts = categoryCounts();
  const categoryOrder: LawCategory[] = [
    "peraturan", "keputusan", "lampiran", "perda",
    "putusan", "kepkl", "perjanjian", "lainnya",
  ];

  return (
    <div className="space-y-10">
      <PopularSearches />

      <section className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
        <Card title="최신법령" subtitle="최근 공포된 법령 10건" href="/search/?recent=30">
          <LawTable laws={recent} />
        </Card>

        <div className="space-y-8">
          <Card
            title="법령 카테고리"
            subtitle="1차 메뉴별 등록 건수"
            href="/search/"
          >
            <ul className="grid grid-cols-2 gap-2 text-sm">
              {categoryOrder.map((c) => (
                <li key={c}>
                  <a
                    href={path(`/search/?category=${c}`)}
                    className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3.5 py-2.5 transition-colors hover:border-brand hover:bg-blue-50/40"
                  >
                    <span className="font-medium text-slate-800">
                      {CATEGORY_META[c].name_ko}
                    </span>
                    <span className="text-xs font-semibold text-slate-500 tabular-nums">
                      {counts[c].toLocaleString()}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </Card>

          <Card
            title="부처별 빠른 진입"
            subtitle="소관 부처로 검색"
            href="/search/"
          >
            <MinistryGrid counts={ministries} />
          </Card>
        </div>
      </section>
    </div>
  );
}

function Card({
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
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>
          )}
        </div>
        <a
          href={path(href)}
          className="shrink-0 text-sm font-medium text-brand hover:underline"
        >
          더보기 →
        </a>
      </div>
      {children}
    </section>
  );
}
