"""peraturan.go.id (DITJEN PP, Kemenkumham) scraper.

NOTE: 실제 selector는 GitHub Actions(미국 IP) 첫 실행 결과를 보고 보정한다.
한국 IP 회선에서는 TLS/ALPN 단계에서 차단되어 로컬 검증 불가.

법령 위계 매핑:
  /uu        → law_type='UU'        category='peraturan'
  /pp        → law_type='PP'        category='peraturan'
  /perpres   → law_type='Perpres'   category='peraturan'
  /permen    → law_type='Permen'    category='peraturan'
  /kepmen    → law_type='Kepmen'    category='keputusan'
  /perda     → law_type='Perda'     category='perda'
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, ClassVar
from urllib.parse import urljoin

from ..base_scraper import BaseScraper, LawRecord

log = logging.getLogger(__name__)

NUMBER_RE = re.compile(r"(?:Nomor|No\.?)\s*([\w./-]+)\s+Tahun\s+(\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class _Section:
    path: str
    law_type: str
    category: str  # 'peraturan' | 'keputusan' | 'perda'


SECTIONS: tuple[_Section, ...] = (
    _Section("/uu",      "UU",      "peraturan"),
    _Section("/pp",      "PP",      "peraturan"),
    _Section("/perpres", "Perpres", "peraturan"),
    _Section("/permen",  "Permen",  "peraturan"),
    _Section("/kepmen",  "Kepmen",  "keputusan"),
    _Section("/perda",   "Perda",   "perda"),
)


class PeraturanGoIdScraper(BaseScraper):
    """Crawl peraturan.go.id across all 1차 categories."""

    ministry_code = "kumham"                 # data publisher (DITJEN PP, Kemenkumham)
    ministry_name_ko = "법무인권부"
    base_url = "https://peraturan.go.id"

    # 첫 실행 시 한 위계당 가져올 페이지 수 (rate-limit 고려)
    pages_per_section: ClassVar[int] = 2

    async def scrape(self) -> AsyncIterator[LawRecord]:
        for section in SECTIONS:
            log.info("[peraturan.go.id] section %s (%s)", section.path, section.law_type)
            page = await self.new_page()
            for page_no in range(1, self.pages_per_section + 1):
                url = f"{self.base_url}{section.path}?page={page_no}"
                try:
                    await self.goto(page, url)
                    await page.wait_for_load_state("networkidle", timeout=20_000)
                except Exception as e:
                    log.warning("  goto fail %s: %s", url, e)
                    break

                # peraturan.go.id 의 실제 DOM 셀렉터는 첫 실행 시 보정.
                # 추정: 결과 카드/행 안에 상세 페이지 링크 + PDF 링크가 있다.
                items = await page.query_selector_all(
                    'a[href*="/details/"], a[href*="/peraturan/"], a[href*="/uu/"], '
                    'a[href*="/pp/"], a[href*="/perpres/"], a[href*="/permen/"], '
                    'a[href*="/kepmen/"], a[href*="/perda/"]'
                )
                if not items:
                    log.warning("  no items on %s", url)
                    break

                seen: set[str] = set()
                for el in items:
                    href = (await el.get_attribute("href")) or ""
                    if not href or href in seen:
                        continue
                    # 분류 페이지 자체 링크는 스킵
                    if href.rstrip("/").endswith(section.path):
                        continue
                    seen.add(href)

                    title_id = (await el.inner_text()).strip()
                    if not title_id or len(title_id) < 5:
                        continue

                    detail_url = urljoin(self.base_url, href)
                    law_number, year = self._parse_number_year(title_id)
                    if not law_number:
                        m = re.search(r"/([^/]+)$", href)
                        law_number = m.group(1) if m else title_id[:64]

                    yield LawRecord(
                        category=section.category,
                        law_type=section.law_type,
                        law_number=law_number,
                        title_id=title_id,
                        source="peraturan_go_id",
                        source_url=detail_url,
                        ministry_code=self.ministry_code,
                        ministry_name_ko=self.ministry_name_ko,
                        year=year,
                        promulgation_date=f"{year}-01-01" if year else None,
                    )

    @staticmethod
    def _parse_number_year(title: str) -> tuple[str | None, int | None]:
        m = NUMBER_RE.search(title)
        if not m:
            return None, None
        return f"{m.group(1)} Tahun {m.group(2)}", int(m.group(2))
