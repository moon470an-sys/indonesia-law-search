"use client";

import { useState } from "react";

// Smart Wayback link.
//
// On click we hit the Wayback CDX API to find the latest status-200 snapshot
// (skipping snapshots that captured a 5xx error page) and navigate to that
// exact timestamp. Falls back to:
//   1. /save/?url=<url>     if the URL has zero captures
//   2. /web/2-star/<url>    calendar if the API is unreachable (network)
//
// Canonicalizes peraturan.go.id → www.peraturan.go.id so Wayback's URL key
// matches the snapshots actually filed there.
export function WaybackLink({ url, label }: { url: string; label: string }) {
  const [busy, setBusy] = useState(false);
  const target = canonicalize(url);

  async function handleClick(e: React.MouseEvent<HTMLAnchorElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      // Availability API has CORS enabled (Access-Control-Allow-Origin: *)
      // and returns the closest *200 OK* snapshot — automatically skipping
      // 5xx-captured snapshots. Required: full URL with https:// prefix.
      const apiUrl =
        "https://archive.org/wayback/available" +
        `?url=${encodeURIComponent(target)}`;
      const r = await fetch(apiUrl, { mode: "cors" });
      if (r.ok) {
        const data: unknown = await r.json();
        const closest = (data as {
          archived_snapshots?: { closest?: { url?: string; available?: boolean } };
        })?.archived_snapshots?.closest;
        if (closest?.available && closest.url) {
          // closest.url comes back as http://; force https for mixed-content safety
          const cached = closest.url.replace(/^http:\/\//, "https://");
          window.open(cached, "_blank", "noopener");
          return;
        }
      }
      // No snapshot → offer Save Page Now form (always works)
      window.open(
        `https://web.archive.org/save/?url=${encodeURIComponent(target)}`,
        "_blank",
        "noopener",
      );
    } catch {
      // Network/CORS failure → fallback to calendar
      window.open(
        `https://web.archive.org/web/2*/${target}`,
        "_blank",
        "noopener",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <a
      href={`https://web.archive.org/web/2*/${target}`}
      onClick={handleClick}
      target="_blank"
      rel="noreferrer"
      className="text-brand hover:underline"
      title="가장 최근 정상(200 OK) 캡처로 직접 이동 — 보관본 없으면 Save Page Now"
    >
      {busy ? "📦 ..." : label}
    </a>
  );
}

function canonicalize(rawUrl: string): string {
  try {
    const u = new URL(rawUrl);
    if (u.hostname === "peraturan.go.id") {
      u.hostname = "www.peraturan.go.id";
      return u.toString();
    }
  } catch {
    /* leave as-is */
  }
  return rawUrl;
}
