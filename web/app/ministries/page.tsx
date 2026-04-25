import { listMinistries } from "@/lib/db";
import { GROUP_LABEL, MINISTRIES } from "@/lib/ministries";
import { path } from "@/lib/paths";

export const dynamic = "force-static";

export default function MinistriesDirectory() {
  const counts = new Map(listMinistries().map((m) => [m.code, m.count] as const));

  // group → ministries[] (filtering to those with rows)
  const groups = new Map<string, typeof MINISTRIES>();
  for (const m of MINISTRIES) {
    if ((counts.get(m.code) ?? 0) === 0) continue;
    const arr = groups.get(m.group) ?? [];
    arr.push(m);
    groups.set(m.group, arr);
  }
  // sort within each group by count desc
  for (const arr of groups.values()) {
    arr.sort((a, b) => (counts.get(b.code) ?? 0) - (counts.get(a.code) ?? 0));
  }

  const groupOrder: (keyof typeof GROUP_LABEL)[] = ["ekonomi", "polkam", "kesra", "infra", "lainnya"];

  return (
    <div className="space-y-8">
      <header>
        <nav className="text-xs text-slate-500">
          <a href={path("/")} className="hover:text-brand">홈</a>
          <span className="mx-1.5 text-slate-300">/</span>
          <span>부처 디렉토리</span>
        </nav>
        <h1 className="mt-2 text-2xl font-bold text-slate-900 sm:text-[26px]">
          부처 디렉토리
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          peraturan.go.id에 등록된 인도네시아 정부부처 {Array.from(counts.values()).filter((c) => c > 0).length}곳 ·
          전체 {Array.from(counts.values()).reduce((s, c) => s + c, 0).toLocaleString()}건
        </p>
      </header>

      {groupOrder.map((g) => {
        const arr = groups.get(g);
        if (!arr || arr.length === 0) return null;
        return (
          <section key={g}>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
              {GROUP_LABEL[g]}
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {arr.map((m) => (
                <a
                  key={m.code}
                  href={path(`/ministries/${m.code}/`)}
                  className="group flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-4 transition hover:border-brand hover:shadow-sm"
                >
                  <span className="text-2xl" aria-hidden>{m.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-slate-900 group-hover:text-brand">
                      {m.name_ko}
                    </p>
                    <p className="mt-0.5 truncate text-[11px] italic text-slate-500">
                      {m.name_id}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-slate-700 tabular-nums">
                      {(counts.get(m.code) ?? 0).toLocaleString()}건
                    </p>
                  </div>
                </a>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
