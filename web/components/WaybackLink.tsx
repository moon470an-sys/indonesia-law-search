"use client";

import { useState } from "react";

/**
 * Smart Wayback link.
 *
 * On click we hit the Wayback CDX API to find the *latest status-200* snapshot
 * (skipping snapshots that captured a 5xx error page) and navigate to that
 * exact timestamp. Falls back to:
 *   1. /web/<url> (latest, regardless of status) if CDX is reachable but has
 *      no 200 captures
 *   2. /save/?url=<url> if the URL has zero captures
 *   3. /web/2*/url calendar if the API is unreachable (network failure)
 *
 * Canonicalizes peraturan.go.id → www.peraturan.go.id so Wayback's URL key
 * matches the snapshots actually filed there.
 */
export function WaybackLink({ url, label }: { url: string; label: string }) {
  const [busy, setBusy] = useState(false);
  const target = canonicalize(url);

  async function handleClick(e: React.MouseEvent<HTMLAnchorElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const cdxUrl =
        "https://web.archive.org/cdx/search/cdx" +
        `?url=${encodeURIComponent(target)}` +
        "&output=json&filter=statuscode:200&limit=-1";
      const r = await fetch(cdxUrl, { mode: "cors" });
      if (r.ok) {
        const rows: unknown = await r.json();
        // CDX returns [["urlkey","timestamp","original",...], ["...",...]]
        const arr = Array.isArray(rows) ? (rows as string[][]) : [];
        if (arr.length > 1) {
          const last = arr[arr.length - 1];
          const ts = last[1];
          const original = last[2] || target;
          window.open(
            `https://web.archive.org/web/${ts}/${original}`,
            "_blank",
            "noopener",
          );
          return;
        }
      }
      // No 200 capture → offer Save Page Now
      window.open(
        `https://web.archive.org/save/?url=${encodeURIComponent(target)}`,
        "_blank",
        "noopener",
      );
    } catch {
      // Network or CORS failure → fall back to calendar
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
