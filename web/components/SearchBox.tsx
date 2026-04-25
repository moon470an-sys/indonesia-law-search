"use client";

import { useState } from "react";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function SearchBox({
  defaultQuery = "",
  defaultField = "title",
  inline = false,
}: {
  defaultQuery?: string;
  defaultField?: string;
  inline?: boolean;
}) {
  const [q, setQ] = useState(defaultQuery);
  const [field, setField] = useState(defaultField);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const url = new URL(`${BASE}/search/`, window.location.origin);
    if (q.trim()) url.searchParams.set("q", q.trim());
    if (field && field !== "title") url.searchParams.set("field", field);
    window.location.assign(url.toString());
  }

  return (
    <form
      onSubmit={submit}
      className={
        inline
          ? "flex w-full items-center gap-2"
          : "flex w-full items-center gap-2 rounded-md border border-slate-300 bg-white px-2 py-1 shadow-sm focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500"
      }
    >
      <select
        value={field}
        onChange={(e) => setField(e.target.value)}
        className="shrink-0 rounded border-0 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 focus:outline-none"
        aria-label="검색 옵션"
      >
        <option value="title">법령명</option>
        <option value="body">법령본문</option>
        <option value="article_body">조문내용</option>
        <option value="article_title">조문제목</option>
        <option value="addendum">부칙</option>
        <option value="amendment">제정·개정문</option>
      </select>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="주제어, 법령명을 입력하세요"
        className="min-w-0 flex-1 border-0 bg-transparent px-2 py-1.5 text-sm focus:outline-none"
      />
      <button
        type="submit"
        className="shrink-0 rounded-md bg-blue-700 px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-800"
      >
        검색
      </button>
      <a
        href={`${BASE}/search/`}
        className="hidden shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 md:inline-block"
      >
        상세검색
      </a>
    </form>
  );
}
