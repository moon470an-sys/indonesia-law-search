"""HTML scrapers for jdih.* subdomains that don't expose a JSON API.

Each adapter declares (list_url_template, item selector, title/url/etc.
extractors). The runner paginates ?page=N until empty or until a known
total is reached, parsing each page with BeautifulSoup.

Sites covered (this batch, ~1,776 laws):
  - kemnaker    노동부          ~515
  - kemenpppa   여성가족부       ~790
  - brin        연구혁신청       ~386
  - pkp         주거단지부       ~85

CLI:
  python -m crawler.html_scrapers kemnaker
  python -m crawler.html_scrapers --all
  python -m crawler.html_scrapers kemnaker --max-pages 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base_scraper import LawRecord

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36 jdih-html-scraper/0.1"
)


# ────────────────────────────────────────────────────────────────────────────
# Per-site parsers
# Each parser takes the BeautifulSoup soup of one list page and yields LawRecords.
# ────────────────────────────────────────────────────────────────────────────

YEAR_RX = re.compile(r"Tahun\s+(\d{4})", re.IGNORECASE)
NUMBER_RX = re.compile(r"Nomor\s+([^\s,]+(?:\s+\S+)*?)\s+(?:Tahun|tentang|Tentang)", re.IGNORECASE)


def _extract_number(title: str) -> str | None:
    m = NUMBER_RX.search(title or "")
    if m:
        return m.group(1).strip().rstrip(",")
    return None


def _extract_year(title: str) -> int | None:
    m = YEAR_RX.search(title or "")
    return int(m.group(1)) if m else None


def parse_kemnaker(soup: BeautifulSoup, page_url: str) -> list[LawRecord]:
    out = []
    for box in soup.select(".result-details"):
        title_a = box.select_one("h5.title a[href]")
        if not title_a:
            continue
        href = title_a.get("href") or ""
        if "/peraturan/detail/" not in href:
            continue
        title = title_a.get_text(" ", strip=True)
        if not title:
            continue
        # status badge
        status_el = box.select_one(".badge")
        status_txt = (status_el.get_text(" ", strip=True) if status_el else "").lower()
        status = "berlaku" if "berlaku" in status_txt else "tidak_diketahui"
        m = re.search(r"/detail/(\d+)/", href)
        det_id = m.group(1) if m else None
        out.append(LawRecord(
            category="peraturan",
            law_type="Permenaker",
            law_number=_extract_number(title) or f"kemnaker-{det_id}",
            title_id=title,
            source="jdih_kemnaker",
            source_url=urljoin(page_url, href),
            ministry_code="kemenaker",
            ministry_name_ko="인력부",
            year=_extract_year(title),
            status=status,
        ))
    return out


def parse_kemenpppa(soup: BeautifulSoup, page_url: str) -> list[LawRecord]:
    out = []
    for a in soup.select('a.text-dark.text-decoration-none[href*="/dokumen-hukum/produk-hukum/"]'):
        href = a.get("href") or ""
        h4 = a.select_one("h4")
        if not h4:
            continue
        title_main = h4.get_text(" ", strip=True)
        # Description sibling: <p class="mb-2 highlightable">…</p>
        desc_p = a.find_next("p", class_=lambda c: c and "highlightable" in c)
        desc = desc_p.get_text(" ", strip=True) if desc_p else ""
        title = (title_main + " " + desc).strip() if desc else title_main
        if not title:
            continue
        out.append(LawRecord(
            category="peraturan",
            law_type="Peraturan Menteri PPPA",
            law_number=_extract_number(title) or "kemenpppa-?",
            title_id=title[:512],
            source="jdih_kemenpppa",
            source_url=urljoin(page_url, href),
            ministry_code="kemenpppa",
            ministry_name_ko="여성·아동권익부",
            year=_extract_year(title),
            status="tidak_diketahui",
        ))
    return out


def parse_brin(soup: BeautifulSoup, page_url: str) -> list[LawRecord]:
    out = []
    for a in soup.select('a[href*="/dokumen-hukum/peraturan/view/"]'):
        href = a.get("href") or ""
        # The card is the closest ancestor with a heading; title is its sibling
        card = a.find_parent("div", recursive=True)
        # Walk up looking for a card with a title (h3/h4) or text
        title = None
        for ancestor in [card] + list(a.parents):
            if not ancestor:
                continue
            h = ancestor.find(["h2", "h3", "h4", "h5"]) if hasattr(ancestor, "find") else None
            if h:
                title = h.get_text(" ", strip=True)
                if title:
                    break
        if not title:
            # Fall back: look for a strong/span with substantial text near the link
            t_el = a.find_previous(["p", "span", "strong"], string=True)
            if t_el:
                title = t_el.get_text(" ", strip=True)
        if not title:
            continue
        m = re.search(r"/view/([a-f0-9\-]+)", href)
        uuid = m.group(1) if m else None
        out.append(LawRecord(
            category="peraturan",
            law_type="Peraturan BRIN",
            law_number=_extract_number(title) or f"brin-{uuid[:8] if uuid else '?'}",
            title_id=title[:512],
            source="jdih_brin",
            source_url=urljoin(page_url, href),
            ministry_code="brin",
            ministry_name_ko="국가연구혁신청",
            year=_extract_year(title),
            status="tidak_diketahui",
        ))
    # Dedupe by source_url within the page
    seen, unique = set(), []
    for r in out:
        if r.source_url in seen:
            continue
        seen.add(r.source_url)
        unique.append(r)
    return unique


def parse_pkp(soup: BeautifulSoup, page_url: str) -> list[LawRecord]:
    out = []
    for actions in soup.select(".doc-actions"):
        # Title: the preceding <p> within the same card
        card = actions.find_parent()
        title_el = None
        if card:
            # Look for the preceding p containing a long descriptive text
            for p in card.find_all("p"):
                t = p.get_text(" ", strip=True)
                if t and len(t) > 20:
                    title_el = p
                    break
        # Alternate path: walk up to find the card's title
        if not title_el:
            container = actions.find_parent("div", recursive=True)
            while container is not None:
                p = container.find("p")
                if p and len(p.get_text(strip=True)) > 20:
                    title_el = p
                    break
                container = container.find_parent("div")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        # Detail link: first <a class="btn-action"> with non-PDF href
        detail_a = None
        for a in actions.select("a.btn-action"):
            href = a.get("href") or ""
            if href and not href.endswith(".pdf"):
                detail_a = a
                break
        if not detail_a:
            continue
        href = detail_a.get("href") or ""
        # PDF
        pdf_a = None
        for a in actions.select("a.btn-action"):
            h2 = a.get("href") or ""
            if h2.endswith(".pdf"):
                pdf_a = a
                break
        out.append(LawRecord(
            category="peraturan",
            law_type="Peraturan Kemen PKP",
            law_number=_extract_number(title) or "pkp-?",
            title_id=title[:512],
            source="jdih_pkp",
            source_url=urljoin(page_url, href),
            ministry_code="kemenpkp",
            ministry_name_ko="주거단지부",
            year=_extract_year(title),
            status="tidak_diketahui",
            pdf_url_id=urljoin(page_url, pdf_a.get("href")) if pdf_a else None,
        ))
    return out


# ────────────────────────────────────────────────────────────────────────────
# Adapter registry
# ────────────────────────────────────────────────────────────────────────────

ADAPTERS: dict[str, dict] = {
    "kemnaker": {
        "list_template": "https://jdih.kemnaker.go.id/peraturan?page={page}",
        "parser": parse_kemnaker,
    },
    "kemenpppa": {
        "list_template": "https://jdih.kemenpppa.go.id/dokumen-hukum/produk-hukum?page={page}",
        "parser": parse_kemenpppa,
    },
    "brin": {
        "list_template": "https://jdih.brin.go.id/dokumen-hukum/peraturan?page={page}",
        "parser": parse_brin,
    },
    "pkp": {
        "list_template": "https://jdih.pkp.go.id/produk-hukum?page={page}",
        "parser": parse_pkp,
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────────────────────

async def fetch(client: httpx.AsyncClient, url: str, retries: int = 3) -> str | None:
    last_err = None
    for attempt in range(retries):
        try:
            r = await client.get(url, timeout=30.0, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = str(e)
            await asyncio.sleep(2 + attempt)
    log.error("[fetch] all retries failed for %s: %s", url, last_err)
    return None


async def scrape_site(site: str, max_pages: int) -> tuple[int, int, Path]:
    adapter = ADAPTERS[site]
    out_path = Path(f"data/raw/jdih_{site}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    yielded = 0
    seen_urls: set[str] = set()
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "id-ID,en;q=0.5"}) as client:
        with out_path.open("w", encoding="utf-8") as f:
            zero_pages = 0
            for page in range(1, max_pages + 1):
                url = adapter["list_template"].format(page=page)
                html = await fetch(client, url)
                if html is None:
                    log.warning("[%s] page %d fetch failed → stop", site, page)
                    break
                soup = BeautifulSoup(html, "lxml")
                records = adapter["parser"](soup, url)
                # Dedupe within site
                new_recs = [r for r in records if r.source_url not in seen_urls]
                for r in new_recs:
                    seen_urls.add(r.source_url)
                    f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
                    yielded += 1
                log.info("[%s] page %d → %d items (%d new, cum=%d)",
                         site, page, len(records), len(new_recs), yielded)
                if not new_recs:
                    zero_pages += 1
                    if zero_pages >= 2:
                        log.info("[%s] 2 consecutive empty pages → done", site)
                        break
                else:
                    zero_pages = 0
    log.info("[%s] DONE yielded=%d → %s", site, yielded, out_path)
    return yielded, 0, out_path


async def main_async(sites: list[str], max_pages: int) -> None:
    results = await asyncio.gather(*(scrape_site(s, max_pages) for s in sites))
    print("\n=== Summary ===")
    for site, (n, _, p) in zip(sites, results):
        print(f"  {site:12} yielded={n:>5} → {p}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-pages", type=int, default=200)
    args = ap.parse_args()
    sites = list(ADAPTERS) if args.all else args.sites
    if not sites:
        ap.error("specify site keys or --all")
    bad = [s for s in sites if s not in ADAPTERS]
    if bad:
        ap.error(f"unknown sites: {bad} (known: {list(ADAPTERS)})")
    asyncio.run(main_async(sites, args.max_pages))


if __name__ == "__main__":
    main()
