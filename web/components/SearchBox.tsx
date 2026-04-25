"use client";

import { useState } from "react";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function SearchBox({ defaultQuery = "" }: { defaultQuery?: string }) {
  const [q, setQ] = useState(defaultQuery);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const url = new URL(`${BASE}/search/`, window.location.origin);
    if (q.trim()) url.searchParams.set("q", q.trim());
    window.location.assign(url.toString());
  }

  return (
    <form onSubmit={submit} className="flex w-full gap-2">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="법령명 또는 키워드를 입력하세요"
        className="flex-1 rounded-md border border-slate-300 bg-white px-4 py-2 text-base shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <button
        type="submit"
        className="rounded-md bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        검색
      </button>
    </form>
  );
}
