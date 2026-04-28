"use client";

// Multi-source "view this page" cluster.
//
// Wayback alone is unreliable: many JDIH URLs aren't archived, and even
// when they are the latest snapshot is sometimes a captured 5xx page.
// We render three alternatives so at least one always works:
//
//   1. r.jina.ai — Jina Reader proxy. Fetches the LIVE page through
//      Jina's network (US/global IPs, bypasses Korean blocks) and
//      returns clean Markdown. Works for any reachable URL, no archive
//      dependency, no auth. This is the primary "just show me the
//      content" path.
//
//   2. Wayback Machine — anchored to mid-2024 to dodge any later 5xx
//      captures. Falls back to Wayback's "Save Page Now" 404 page when
//      no snapshot exists.
//
//   3. archive.today — independent archive operating outside Wayback.
//      Often has snapshots Wayback doesn't.
//
// All three open in new tabs so the user can chain through them.

export function WaybackLink({ url, label: _label }: { url: string; label: string }) {
  // _label kept in props for backward compatibility with the old single-link API.
  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      <a
        href={`https://r.jina.ai/${url}`}
        target="_blank"
        rel="noreferrer"
        className="text-brand hover:underline"
        title="Jina Reader 우회 — 실제 페이지를 외부 서버 통해 fetch + 본문만 추출"
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
    </span>
  );
}
