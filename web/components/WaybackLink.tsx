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
    const rawLast = last.replace(/\.(pdf|html?|aspx?)$/i, "");
    const slug = rawLast.replace(/[-_]+/g, " ").trim();
    // A slug is only useful if it actually carries words.
    // Reject:
    //  - pure numeric ids   ("2459", "1208" — JDIH /dokumen/detail/<id>)
    //  - very short tokens  (<6 chars)
    //  - opaque blobs       (e.g. polri PDF links serve base64 JSON
    //    starting with "eyJ"; long alnum strings with no separator
    //    are almost always encoded payload, not a slug)
    const isBase64Json = /^eyJ[A-Za-z0-9+/=]/.test(rawLast);
    const isLongOpaque =
      rawLast.length >= 25 && !/[-_./]/.test(rawLast);
    const hasLetters = /[a-z]/i.test(slug);
    const isMeaningfulSlug =
      slug.length >= 6 && hasLetters && !isBase64Json && !isLongOpaque;
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
