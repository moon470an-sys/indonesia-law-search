"""High-throughput peraturan.go.id metadata scraper.

Designed to be invoked once per hierarchy (uu / pp / perpres / permen / kepmen / perda),
typically as one job in a GitHub Actions matrix. Each invocation:

  1. fetches list pages /<slug>?page=<n> in chunks (default 20 at a time, sem=10)
  2. parses div.wrapper rows
  3. emits one JSONL line per law to the output path
  4. stops when a whole chunk returns 0 rows

The scraper does *not* hit detail pages or PDFs — list pages already carry the
title, slug, year and PDF URL. Detail-level enrichment is a follow-up step.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

BASE = "https://peraturan.go.id"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("peraturan_full")

# slug → (default law_type, default category)
SECTIONS: dict[str, tuple[str, str]] = {
    "uu":      ("UU",      "peraturan"),
    "pp":      ("PP",      "peraturan"),
    "perpres": ("Perpres", "peraturan"),
    "permen":  ("Permen",  "peraturan"),
    "kepmen":  ("Kepmen",  "keputusan"),
    "perda":   ("Perda",   "perda"),
}

SLUG_TYPE_MAP = {
    "uu":              "UU",
    "perppu":          "Perppu",
    "pp":              "PP",
    "perpres":         "Perpres",
    "permen":          "Permen",
    "permenkeu":       "Permenkeu",
    "permenhub":       "Permenhub",
    "permendag":       "Permendag",
    "permenhut":       "Permenhut",
    "permentan":       "Permentan",
    "permenkes":       "Permenkes",
    "permenkomdigi":   "Permenkomdigi",
    "permenkominfo":   "Permenkominfo",
    "permenkop":       "Permenkop",
    "permenkum":       "Permenkumham",
    "permenkumham":    "Permenkumham",
    "permenpar":       "Permenpar",
    "permenpu":        "Permenpu",
    "permenpkp":       "PermenPKP",
    "permenpan":       "PermenPAN-RB",
    "permenperin":     "Permenperin",
    "permenkebud":     "Permenkebud",
    "permenkkp":       "PermenKKP",
    "permendikdasmen": "Permendikdasmen",
    "permenkoinfra":   "Permenkoinfra",
    "permenkoeko":     "Permenkoeko",
    "permenag":        "Permenag",
    "permenmubpn":     "Permen ATR/BPN",
    "permenpera":      "Permenpera",
    "permensos":       "Permensos",
    "kepmen":          "Kepmen",
    "perda":           "Perda",
    "pergub":          "Pergub",
    "perwako":         "Perwako",
    "perwali":         "Perwali",
    "perwalkot":       "Perwalkot",
    "perbup":          "Perbup",
}

SLUG_RE = re.compile(
    r"^([a-z]+)"
    r"(?:-([a-z][a-z0-9-]*?))?"
    r"-no-([\w.+-]+?)"
    r"-tahun-(\d{4})/?$",
    re.IGNORECASE,
)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 jdih-bulk/0.1"
)


# ─────────────────────────────────────────────────────────
async def fetch(client: httpx.AsyncClient, url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            r = await client.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            if 500 <= r.status_code < 600:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
        except (httpx.RequestError, httpx.HTTPError):
            await asyncio.sleep(2 ** attempt)
    return None


def parse_page(html: str, default_law_type: str, default_category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for w in soup.select("div.wrapper"):
        link = w.select_one('a[href^="/id/"][title="lihat detail"]') or w.select_one('a[href^="/id/"]')
        if not link:
            continue
        href = (link.get("href") or "").strip()
        if not href.startswith("/id/"):
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        slug = href.rsplit("/", 1)[-1]
        m = SLUG_RE.match(slug)
        if m:
            slug_type = m.group(1).lower()
            num = m.group(3)
            year = int(m.group(4))
            law_number = f"Nomor {num} Tahun {year}"
        else:
            slug_type = default_law_type.lower()
            year = None
            law_number = slug

        # category routing
        if slug_type.startswith(("perda", "pergub", "perwako", "perwalkot", "perwali", "perbup")):
            category = "perda"
        elif slug_type.startswith("kepmen"):
            category = "keputusan"
        else:
            category = default_category

        law_type = SLUG_TYPE_MAP.get(slug_type, default_law_type)

        out.append({
            "category":          category,
            "law_type":          law_type,
            "law_number":        law_number,
            "title_id":          title,
            "source":            "peraturan_go_id",
            "source_url":        f"{BASE}{href}",
            "ministry_code":     "kumham",
            "ministry_name_ko":  "법무인권부",
            "year":              year,
            "promulgation_date": f"{year}-01-01" if year else None,
            "pdf_url_id":        f"{BASE}/files/{slug}.pdf",
            "status":            "berlaku",
            "era":               "modern",
        })
    return out


async def crawl_section(
    client: httpx.AsyncClient,
    slug: str,
    law_type: str,
    category: str,
    out_path: Path,
    chunk: int = 20,
    concurrency: int = 10,
    max_pages: int = 5000,
) -> int:
    sem = asyncio.Semaphore(concurrency)

    async def go(url: str) -> str | None:
        async with sem:
            return await fetch(client, url)

    seen_slugs: set[str] = set()
    total = 0
    page = 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        while page <= max_pages:
            urls = [f"{BASE}/{slug}?page={page + i}" for i in range(chunk)]
            log.info("[%s] fetching pages %d-%d", slug, page, page + chunk - 1)
            results = await asyncio.gather(*[go(u) for u in urls])

            chunk_rows = 0
            for html in results:
                if not html:
                    continue
                for row in parse_page(html, law_type, category):
                    key = row["source_url"]
                    if key in seen_slugs:
                        continue
                    seen_slugs.add(key)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    chunk_rows += 1

            total += chunk_rows
            log.info("[%s] page-chunk yielded %d rows (running total %d)",
                     slug, chunk_rows, total)

            if chunk_rows == 0:
                # whole chunk produced nothing → assume end of list
                break
            page += chunk

    return total


async def amain(targets: Iterable[str], out_dir: Path, chunk: int, concurrency: int, max_pages: int) -> int:
    headers = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9"}
    async with httpx.AsyncClient(
        headers=headers,
        http2=True,
        follow_redirects=True,
        timeout=30,
        limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
    ) as client:
        for slug in targets:
            if slug not in SECTIONS:
                log.error("unknown section: %s (valid: %s)", slug, list(SECTIONS))
                return 1
            law_type, category = SECTIONS[slug]
            out_path = out_dir / f"{slug}.jsonl"
            # truncate any prior run
            if out_path.exists():
                out_path.unlink()
            n = await crawl_section(
                client, slug, law_type, category, out_path,
                chunk=chunk, concurrency=concurrency, max_pages=max_pages,
            )
            log.info("=== %s done: %d rows → %s ===", slug, n, out_path)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", help="hierarchy slugs (uu/pp/perpres/permen/kepmen/perda) or 'all'")
    ap.add_argument("--out-dir", default="data/raw")
    ap.add_argument("--chunk", type=int, default=20, help="pages fetched per round")
    ap.add_argument("--concurrency", type=int, default=10, help="max in-flight requests")
    ap.add_argument("--max-pages", type=int, default=5000)
    args = ap.parse_args()

    targets = list(SECTIONS) if args.targets == ["all"] else args.targets
    return asyncio.run(amain(targets, Path(args.out_dir), args.chunk, args.concurrency, args.max_pages))


if __name__ == "__main__":
    sys.exit(main())
