"""Fetch the latest hukumonline.com articles for the daily email digest.

hukumonline.com is behind Cloudflare's bot challenge, so plain httpx/curl
get a 403. Jina Reader (r.jina.ai) successfully proxies the page and
returns clean Markdown — we parse that for article entries.

Each entry comes back as:
  [<title> <description> <DD MMM YYYY>• <author>](https://www.hukumonline.com/berita/a/<slug>-lt<id>/)

Returns a list of dicts:
  {title, description, date_id, author, url}

Translation stays manual per CLAUDE.md (no external translation API);
the email surfaces Indonesian text with a Google Translate proxy link
appended for one-click Korean reading.
"""
from __future__ import annotations

import re
import urllib.request
from typing import Any

JINA_BASE = "https://r.jina.ai/"
LIST_URL = "https://www.hukumonline.com/berita/terbaru/"

# A "berita/a/<slug>-lt<id>/" path uniquely identifies an article entry.
ARTICLE_LINE_RX = re.compile(
    r"\[(?P<text>[^\]]+)\]\((?P<url>https://www\.hukumonline\.com/berita/a/[a-z0-9\-]+-lt[a-f0-9]+/?)\)",
    re.IGNORECASE,
)
# Each article's text payload contains "<title> <body> <DD MMM YYYY>• <author>".
DATE_AUTHOR_RX = re.compile(
    r"\s+(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})\s*[•·]\s*([^•·\[\]\(\)]+)$"
)


def _fetch_markdown(url: str, timeout: int = 30) -> str:
    """GET via Jina Reader. Falls back to empty string on any error."""
    req = urllib.request.Request(
        JINA_BASE + url,
        headers={"User-Agent": "jdih-daily/1.0 (+hukumonline-news)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _split_text(payload: str) -> tuple[str, str, str, str]:
    """Pull (title, description, date, author) out of the merged anchor text."""
    m = DATE_AUTHOR_RX.search(payload)
    date = ""
    author = ""
    if m:
        date = m.group(1).strip()
        author = m.group(2).strip().rstrip(")").strip()
        payload = payload[: m.start()].rstrip()
    # First "sentence-end" boundary separates title from description.
    parts = re.split(r"(?<=[A-Za-z])\.(?=\s)", payload, maxsplit=1)
    if len(parts) == 2 and len(parts[0]) > 5:
        title = parts[0].strip()
        description = parts[1].strip()
    else:
        # Fallback: split on first long token boundary
        title = payload.strip()
        description = ""
    return title[:200], description[:400], date, author


def fetch_latest(limit: int = 8) -> list[dict[str, Any]]:
    md = _fetch_markdown(LIST_URL)
    if not md:
        return []
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for m in ARTICLE_LINE_RX.finditer(md):
        url = m.group("url").rstrip("/") + "/"
        if url in seen:
            continue
        text = m.group("text")
        # Skip nav links: title-only with no date/author
        if "•" not in text and "·" not in text:
            continue
        title, description, date, author = _split_text(text)
        if not title:
            continue
        seen.add(url)
        out.append({
            "title": title,
            "description": description,
            "date_id": date,
            "author": author,
            "url": url,
        })
        if len(out) >= limit:
            break
    return out


if __name__ == "__main__":
    import json
    items = fetch_latest()
    print(json.dumps(items, ensure_ascii=False, indent=2))
