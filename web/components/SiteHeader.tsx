import { path } from "@/lib/paths";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center px-6 py-4">
        <a href={path("/")} className="flex shrink-0 items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-md bg-brand text-base font-bold text-white shadow-sm">
            법
          </span>
          <span className="text-lg font-bold tracking-tight text-slate-900">
            인도네시아 법령정보센터
          </span>
        </a>
      </div>
    </header>
  );
}
