"use client";

// Two-link "find this page" cluster.
//
//   📦 Wayback (anchored to 2024-06)
//     Wayback Machine snapshot closest to June 2024 — dodges later
//     5xx captures that the latest-pointer often lands on.
//
//   🔎 Google
//     Fallback when no Wayback snapshot exists or the source itself
//     is currently down. The query is derived from the URL slug or,
//     when the slug is just a numeric id (e.g. /detail/2459), from
//     the law's Indonesian title — otherwise Google would just search
//     the bare ID and return junk.

export function WaybackLink({
  url,
  title,
  label: _label,
}: {
  url: string;
  /** Indonesian title — used as the Google query when the URL slug is
   *  meaningless (numeric id, single short token). */
  title?: string;
  label?: string;
}) {
  // _label kept for backward compatibility with the old single-link API.
  let googleQuery = "";
  try {
    const u = new URL(url);
    const last = u.pathname.split("/").filter(Boolean).pop() || "";
    const slug = last.replace(/\.(pdf|html?|aspx?)$/i, "").replace(/[-_]+/g, " ").trim();
    // A slug is only useful if it actually carries words. Pure numbers
    // (DB row ids on JDIH detail pages — "2459", "1208" etc.) and very
    // short tokens get discarded in favour of the law title.
    const isMeaningfulSlug = slug.length >= 6 && /[a-z]/i.test(slug);
    googleQuery = isMeaningfulSlug ? slug : "";
  } catch {
    /* leave as-is */
  }
  if (!googleQuery && title) {
    // Strip filler that doesn't help search — leading "Peraturan / Keputusan
    // / Undang-Undang ... Nomor" stays useful, but trailing "Tentang ..."
    // bodies are too long. Keep the first ~80 chars including the "Nomor X
    // Tahun YYYY" anchor.
    googleQuery = title.replace(/\s+/g, " ").trim().slice(0, 110);
  }
  if (!googleQuery) googleQuery = url;
  const gSearch =
    "https://www.google.com/search?q=" + encodeURIComponent(googleQuery);

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
        title={`Google 검색: ${googleQuery.slice(0, 60)}${googleQuery.length > 60 ? "…" : ""}`}
      >
        🔎 Google
      </a>
    </span>
  );
}
