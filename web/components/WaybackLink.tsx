"use client";

// Four-way "find this page" cluster.
//
// Reality check: when the source site is down AND the URL was never
// archived, no link can show its content. The four options below cover
// every case we can serve:
//
//   1. 🌐 텍스트로 보기 (r.jina.ai)
//      Jina Reader proxy fetches the LIVE page through Jina's network
//      (US/global IPs, bypasses Korean ISP blocks) and returns clean
//      Markdown. Works whenever the source is up.
//
//   2. 📦 Wayback (anchored to 2024-06)
//      Closest snapshot near June 2024 — dodges later 5xx captures
//      that Wayback's /web/<url> latest-pointer often lands on.
//
//   3. 🗃 archive.ph
//      Independent archive operating outside Wayback. Different
//      snapshot universe, sometimes has captures Wayback doesn't.
//
//   4. 🔎 Google 검색
//      Fallback when (a) source site is currently down, (b) Wayback
//      has zero captures, and (c) archive.ph has no snapshot. The
//      law number/year query usually surfaces news articles, gov
//      mirror sites, or law-firm summaries that contain the text.
//
// All four open in new tabs so the user can chain through them.

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
        href={`https://r.jina.ai/${url}`}
        target="_blank"
        rel="noreferrer"
        className="text-brand hover:underline"
        title="Jina Reader 우회 — 외부 서버 통해 라이브 페이지 fetch + 본문만 추출"
      >
        🌐 텍스트로 보기
      </a>
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
        href={`https://archive.ph/${url}`}
        target="_blank"
        rel="noreferrer"
        className="text-brand hover:underline"
        title="archive.today 보관본 (Wayback과 별개 아카이브)"
      >
        🗃 archive.ph
      </a>
      <a
        href={gSearch}
        target="_blank"
        rel="noreferrer"
        className="text-slate-500 hover:underline"
        title="Google 검색 — 원본 다운 + 미아카이빙 시 다른 출처에서 본문 찾기"
      >
        🔎 Google
      </a>
    </span>
  );
}
