"use client";

import { useState } from "react";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function SearchBox({
  defaultQuery = "",
}: {
  defaultQuery?: string;
}) {
  const [q, setQ] = useState(defaultQuery);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const url = new URL(`${BASE}/search/`, window.location.origin);
    if (q.trim()) url.searchParams.set("q", q.trim());
    window.location.assign(url.toString());
  }

  return (
    <form
      onSubmit={submit}
      className="flex w-full items-center gap-2 rounded-lg border border-slate-300 bg-white px-2 py-1.5 shadow-sm focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20"
    >
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="주제어, 법령명을 입력하세요"
        className="min-w-0 flex-1 border-0 bg-transparent px-3 py-2 text-base text-slate-900 placeholder:text-slate-400 focus:outline-none"
      />
      <button
        type="submit"
        className="shrink-0 rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white hover:bg-brand-dark"
      >
        검색
      </button>
    </form>
  );
}
