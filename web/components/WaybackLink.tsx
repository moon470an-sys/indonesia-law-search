"use client";

// Wayback link with mid-2024 anchor timestamp.
//
// /web/20240601000000/<url> tells Wayback to find the snapshot closest to
// June 2024. This deliberately avoids the September 2024 cluster where
// peraturan.go.id was returning HTTP 500 errors (so those captures are
// useless 500-pages frozen forever in Wayback). For URLs first archived
// after mid-2024 the redirect still resolves to the nearest snapshot in
// either direction. For URLs with zero captures Wayback returns its 404
// page, which itself shows the Save Page Now form.
//
// Pure HTML link — no JS, no fetch, no CORS. The previous approaches that
// called CDX or availability APIs from the client were either CORS-blocked
// or returned intermittent empty responses, so users always saw the
// fallback calendar (perceived as broken).

export function WaybackLink({ url, label }: { url: string; label: string }) {
  return (
    <a
      href={`https://web.archive.org/web/20240601000000/${url}`}
      target="_blank"
      rel="noreferrer"
      className="text-brand hover:underline"
      title="Wayback Machine 2024년 보관본 — 보관본 없으면 Save Page Now 페이지로 이동"
    >
      {label}
    </a>
  );
}
