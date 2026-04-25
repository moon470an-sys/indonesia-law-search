import { path } from "@/lib/paths";

const SECONDARY = [
  { code: "berlaku",  label: "현행법령",   q: "status=berlaku" },
  { code: "history",  label: "연혁법령",   q: "status=diubah" },
  { code: "lama",     label: "근대법령",   q: "era=lama" },
  { code: "translation", label: "외국어번역", q: "translated=1" },
  { code: "recent",   label: "최신법령",   q: "recent=30" },
  { code: "treaty",   label: "조약",      q: "category=perjanjian" },
];

export default function SecondaryNav({ active }: { active?: string }) {
  return (
    <div className="border-b border-slate-200 bg-white">
      <ul className="mx-auto flex max-w-6xl gap-4 overflow-x-auto px-6 text-sm">
        {SECONDARY.map((s) => (
          <li key={s.code}>
            <a
              href={path(`/search/?${s.q}`)}
              className={
                active === s.code
                  ? "block whitespace-nowrap border-b-2 border-blue-700 px-2 py-2 font-semibold text-blue-700"
                  : "block whitespace-nowrap px-2 py-2 text-slate-600 hover:text-blue-700"
              }
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
