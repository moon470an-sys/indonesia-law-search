"use client";

// Two-link "find this page" cluster.
//
//   📦 Wayback (anchored to 2024-06)
//     Wayback Machine snapshot closest to June 2024 — dodges later
//     5xx captures that the latest-pointer often lands on.
//
//   🔎 Google
//     Fallback when no Wayback snapshot exists or the source itself
//     is currently down. The law-slug query usually surfaces news
//     articles, gov mirrors, or law-firm summaries containing the text.

export function WaybackLink({ url, label: _label }: { url: string; label: string }) {
  // _label kept for backward compatibility with the old single-link API.
  // Derive a Google query from the slug portion of the URL — last path
  // segment with hyphens turned into spaces, e.g. "uu-no-12-tahun-2025"
  // → "uu no 12 tahun 2025".
  let googleQuery = url;
  try {
    const u = new URL(url);
    const last = u.pathname.split("/").filter(Boolean).pop() || "";
    const slug = last.replace(/\.(pdf|html?|aspx?)$/i, "").replace(/[-_]+/g, " ").trim();
    if (slug.length >= 4) googleQuery = slug;
  } catch {
    /* leave as-is */
  }
  const gSearch =
    "https://www.google.com/search?q=" +
    encodeURIComponent(googleQuery);

  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      <a
        href={`https://web.archive.org/web/20240601000000/${url}`}
        target="_blank"
        rel="noreferrer"
        className="text-brand hover:underline"
        title="Wayback Machine 2024년 보관본"
      >
        📦 Wayback
      </a>
      <a
        href={gSearch}
        target="_blank"
        rel="noreferrer"
        className="text-brand hover:underline"
        title="Google 검색 — 원본 다운 또는 미아카이빙 시 다른 출처에서 본문 찾기"
      >
        🔎 Google
      </a>
    </span>
  );
}
