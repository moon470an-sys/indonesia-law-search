import LawTable from "@/components/LawTable";
import MinistryGrid from "@/components/MinistryGrid";
import PopularSearches from "@/components/PopularSearches";
import { CATEGORY_META, categoryCounts, listMinistries, listRecent, type LawCategory } from "@/lib/db";
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
    <div className="space-y-8">
      <PopularSearches />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="최신법령" href="/search/?recent=30" subtitle="최근 공포된 법령 10건">
          <LawTable laws={recent} />
        </Card>

        <div className="space-y-6">
          <Card title="법령 카테고리" href="/search/" subtitle="1차 메뉴별 등록 건수">
            <ul className="grid grid-cols-2 gap-2 text-sm">
              {categoryOrder.map((c) => (
                <li key={c}>
                  <a
                    href={path(`/search/?category=${c}`)}
                    className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2 hover:border-blue-300"
                  >
                    <span className="font-medium text-slate-700">
                      {CATEGORY_META[c].name_ko}
                    </span>
                    <span className="text-xs text-slate-400">
                      {counts[c]}건
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="부처별 빠른 진입" href="/search/" subtitle="소관 부처로 검색">
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
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-800">{title}</h2>
          {subtitle && (
            <p className="text-xs text-slate-500">{subtitle}</p>
          )}
        </div>
        <a
          href={path(href)}
          className="text-xs text-blue-700 hover:underline"
        >
          더보기 →
        </a>
      </div>
      {children}
    </section>
  );
}
