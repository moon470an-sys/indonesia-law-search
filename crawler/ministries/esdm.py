"""에너지광물자원부 (Kementerian ESDM) JDIH scraper.

Site: https://jdih.esdm.go.id
List page: /dokumen/peraturan?page=N&per-page=K

DOM (확인됨 2026-04-25):
  div.card-body.no-padding-tb
    > div.d-flex … > p > a[href*="/dokumen/index2"]   # 법령 종류 (KEPUTUSAN MENTERI ESDM 등)
    > div.d-flex … > ul > li > a                       # 연도
    > p > a.text-primary[href*="/dokumen/view?id=N"]   # 제목 + 상세 ID
    > div … > a[href*="/dokumen/download"]             # PDF 직링크
"""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator
from urllib.parse import urljoin

from ..base_scraper import BaseScraper, LawRecord

log = logging.getLogger(__name__)

NUMBER_RE = re.compile(r"Nomor\s+(\S+(?:\s+\S+)*?)\s+(?:Tahun|tentang|Tentang)", re.IGNORECASE)
TOTAL_RE = re.compile(r"dari\s+(\d+)\s+Data", re.IGNORECASE)


class EsdmScraper(BaseScraper):
    ministry_code = "esdm"
    ministry_name_ko = "에너지광물자원부"
    base_url = "https://jdih.esdm.go.id"
    list_path = "/dokumen/peraturan"
    # Site forces 5 results/page regardless of per-page query string.
    per_page = 5

    def __init__(
        self,
        headless: bool = True,
        max_pages: int = 600,
        known_source_urls: set[str] | None = None,
        stop_after_known: int = 5,
    ):
        # Default ceiling = 600 pages × 5 = 3,000 records, which comfortably
        # covers the current site total (~2,493). The scrape loop tightens
        # this down to the actual needed_pages parsed from the summary text.
        super().__init__(headless=headless, max_pages=max_pages)
        # Incremental mode: when known_source_urls is provided, stop after we
        # see `stop_after_known` consecutive records that are already in DB.
        # Listing is newest-first, so a contiguous run of known URLs means we
        # have caught up.
        self.known_source_urls = known_source_urls or set()
        self.stop_after_known = stop_after_known

    async def scrape(self) -> AsyncIterator[LawRecord]:
        page = await self.new_page()

        # Determine actual total from the first page summary text and cap pages.
        # max_pages on the instance is treated as a *user-supplied ceiling*; the
        # effective page count is min(ceil(total / per_page), max_pages).
        page_limit = self.max_pages
        seen_total = False
        consecutive_known = 0

        for page_no in range(1, self.max_pages + 1):
            if page_no > page_limit:
                # Total parsed from first-page summary already capped iterations.
                # Without this, range() keeps going up to max_pages (600) since
                # the in-loop reassignment of page_limit does not change range's
                # bounds, which were evaluated once at loop entry.
                break
            url = f"{self.base_url}{self.list_path}?page={page_no}"
            await self.goto(page, url)
            await page.wait_for_load_state("networkidle")

            if not seen_total:
                summary = await page.evaluate(
                    "() => { const e = document.querySelector('.summary'); return e ? e.textContent.trim() : ''; }"
                )
                m = TOTAL_RE.search(summary or "")
                if m:
                    total = int(m.group(1))
                    needed_pages = (total + self.per_page - 1) // self.per_page
                    page_limit = min(self.max_pages, needed_pages)
                    log.info("[esdm] total=%d → crawling %d pages (cap=%d)",
                             total, page_limit, self.max_pages)
                seen_total = True

            cards = await page.query_selector_all(".card-body.no-padding-tb")
            if not cards:
                log.warning("[esdm] no cards on page %d (%s)", page_no, url)
                break
            log.info("[esdm] page %d/%d: %d cards", page_no, page_limit, len(cards))

            yielded = 0
            for card in cards:
                # 제목 + 상세 링크
                title_link = await card.query_selector('a.text-primary[href*="/dokumen/view"]')
                if not title_link:
                    continue
                title_id = (await title_link.inner_text()).strip()
                href = (await title_link.get_attribute("href")) or ""
                source_url = urljoin(self.base_url, href)
                if not (title_id and source_url):
                    continue

                # 법령 종류 (예: "KEPUTUSAN MENTERI ESDM")
                type_link = await card.query_selector('a[href*="/dokumen/index2"]')
                law_type = (await type_link.inner_text()).strip() if type_link else None

                # PDF 직링크
                pdf_link = await card.query_selector('a[href*="/dokumen/download"]')
                pdf_url = None
                if pdf_link:
                    pdf_href = (await pdf_link.get_attribute("href")) or ""
                    pdf_url = urljoin(self.base_url, pdf_href) if pdf_href else None

                # 연도 (제정일 대용 — 상세 페이지에서 정확한 날짜 가져올 수 있으나 일단 연도만)
                year_el = await card.query_selector("ul li a")
                year_txt = (await year_el.inner_text()).strip() if year_el else ""
                year_int = int(year_txt) if year_txt.isdigit() and len(year_txt) == 4 else None
                promulgation_date = f"{year_int}-01-01" if year_int else None

                # 법령 번호 추출 (제목에서 "Nomor X tentang Y" 패턴)
                law_number = self._extract_number(title_id)
                if not law_number:
                    m = re.search(r"id=(\d+)", source_url)
                    law_number = f"esdm-detail-{m.group(1)}" if m else title_id[:64]

                if source_url in self.known_source_urls:
                    consecutive_known += 1
                else:
                    consecutive_known = 0

                yield LawRecord(
                    category="keputusan",            # ESDM Kepmen은 행정규칙 메뉴
                    law_type=law_type or "Kepmen",
                    law_number=law_number,
                    title_id=title_id,
                    source="jdih_esdm",
                    source_url=source_url,
                    ministry_code=self.ministry_code,
                    ministry_name_ko=self.ministry_name_ko,
                    year=year_int,
                    promulgation_date=promulgation_date,
                    pdf_url_id=pdf_url,
                )
                yielded += 1

                if (self.known_source_urls
                        and consecutive_known >= self.stop_after_known):
                    log.info(
                        "[esdm] stopping early: %d consecutive known URLs (incremental mode)",
                        consecutive_known,
                    )
                    return

            if yielded == 0:
                break

    @staticmethod
    def _extract_number(title: str) -> str | None:
        m = NUMBER_RE.search(title)
        if m:
            return m.group(1).strip().rstrip(",")
        return None
