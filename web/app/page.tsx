import LawCard from "@/components/LawCard";
import MinistryFilter from "@/components/MinistryFilter";
import SearchBox from "@/components/SearchBox";
import { listMinistries, listRecent } from "@/lib/db";

export default function HomePage() {
  const recent = listRecent(20);
  const ministries = listMinistries();

  return (
    <div className="space-y-8">
      <section className="rounded-xl bg-gradient-to-br from-blue-600 to-blue-800 p-8 text-white shadow">
        <h1 className="text-2xl font-bold">인도네시아 법령을 한국어로 검색하세요</h1>
        <p className="mt-2 text-sm text-blue-100">
          교통부, ESDM, BKPM, 재무부, 무역부 — 5개 부처의 JDIH 법령 정보를 매일 갱신합니다.
        </p>
        <div className="mt-6">
          <SearchBox />
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
        <MinistryFilter ministries={ministries} baseHref="/search/" />
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">최근 공포된 법령</h2>
          {recent.length === 0 ? (
            <p className="text-sm text-slate-500">아직 등록된 법령이 없습니다.</p>
          ) : (
            <div className="grid gap-3">
              {recent.map((law) => (
                <LawCard key={law.id} law={law} />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
