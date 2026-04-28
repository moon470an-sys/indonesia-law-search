"use client";

// SearchResults uses useSearchParams(), which forces a Suspense boundary in
// Next 15. With `output: 'export'`, the server prerenders both the Suspense
// fallback (inside <main>) AND the resolved tree (in a trailing
// `<div hidden id="S:n">` after the footer). The client-side reconcile that
// would swap them never runs in the static export, so the hidden tree leaks
// below the footer — users see the sidebar/results twice.
//
// Loading SearchResults via `next/dynamic({ ssr: false })` skips the SSR
// pass entirely: prerender renders only the fallback, and the real tree
// mounts on the client where it belongs.
import dynamic from "next/dynamic";

const SearchResults = dynamic(() => import("./SearchResults"), {
  ssr: false,
  loading: () => (
    <p className="text-sm text-slate-500">불러오는 중…</p>
  ),
});

export default SearchResults;
