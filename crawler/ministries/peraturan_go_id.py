"""peraturan.go.id (DITJEN PP, Kemenkumham) scraper.

Confirmed structure (probe 2026-04-25):

  Listing pages:
    https://peraturan.go.id/{type}                  (type ∈ uu|pp|perpres|permen|perda)
    https://peraturan.go.id/{type}?page=N           (pagination)

  Row container:    div.wrapper
  Detail link:      <a href="/id/{slug}" title="lihat detail">{title}</a>
  Slug pattern:     {type}-no-{num}-tahun-{year}
                    perda-{region}-no-{num}-tahun-{year}     (지방법규)
  PDF:              https://peraturan.go.id/files/{slug}.pdf

Inside the wrapper there is also:
    <a class="float-right" href="/pemerintah-pusat">UU</a>      ← 위계 label
    <a class="wish_bt"     href="/id/#">2026</a>                ← year
    <p>Undang-Undang Nomor 1 Tahun 2026</p>                     ← meta line
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, ClassVar
from urllib.parse import urljoin

from ..base_scraper import BaseScraper, LawRecord

log = logging.getLogger(__name__)

SLUG_RE = re.compile(
    r"^/id/"
    r"(?P<type>[a-z]+)"               # uu / pp / perpres / permen / perda / perwako / pergub …
    r"(?:-(?P<region>[a-z-]+?))?"     # optional 지역명 (perda-kabupaten-kendal …)
    r"-no-(?P<num>[\w.+-]+?)"
    r"-tahun-(?P<year>\d{4})/?$",
    re.IGNORECASE,
)


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
    _Section("/perda",   "Perda",   "perda"),
)


class PeraturanGoIdScraper(BaseScraper):
    ministry_code = "kumham"          # data publisher (DITJEN PP)
    ministry_name_ko = "법무인권부"
    base_url = "https://peraturan.go.id"

    pages_per_section: ClassVar[int] = 2   # ~20 records per section per run

    async def scrape(self) -> AsyncIterator[LawRecord]:
        for section in SECTIONS:
            log.info("[peraturan.go.id] %s (%s)", section.path, section.law_type)
            page = await self.new_page()
            try:
                seen_slugs: set[str] = set()
                for page_no in range(1, self.pages_per_section + 1):
                    url = f"{self.base_url}{section.path}?page={page_no}"
                    try:
                        await self.goto(page, url)
                        await page.wait_for_load_state("networkidle", timeout=20_000)
                    except Exception as e:
                        log.warning("  goto %s: %s", url, e)
                        break

                    wrappers = await page.query_selector_all("div.wrapper")
                    if not wrappers:
                        log.warning("  no div.wrapper on %s", url)
                        break
                    log.info("  page %d: %d wrappers", page_no, len(wrappers))

                    yielded_this_page = 0
                    for w in wrappers:
                        title_link = await w.query_selector('a[href^="/id/"][title="lihat detail"]')
                        if not title_link:
                            # fallback: any a[href^="/id/"]
                            title_link = await w.query_selector('a[href^="/id/"]')
                        if not title_link:
                            continue

                        href = (await title_link.get_attribute("href")) or ""
                        if not href.startswith("/id/"):
                            continue
                        if href in seen_slugs:
                            continue
                        seen_slugs.add(href)

                        title_id = (await title_link.inner_text()).strip()
                        if not title_id:
                            continue

                        m = SLUG_RE.match(href)
                        if m:
                            slug_type = m.group("type").lower()
                            num = m.group("num")
                            year = int(m.group("year"))
                            region = m.group("region")
                            law_number = f"Nomor {num} Tahun {year}"
                        else:
                            # fallback — use the slug itself
                            slug_type = section.law_type.lower()
                            year = None
                            region = None
                            law_number = href.rsplit("/", 1)[-1]

                        # detail page + PDF
                        detail_url = urljoin(self.base_url, href)
                        slug = href.rsplit("/", 1)[-1]
                        pdf_url = f"{self.base_url}/files/{slug}.pdf"

                        # 위계 결정 — section의 law_type을 우선
                        law_type = self._normalize_law_type(slug_type, section.law_type)

                        # category
                        # Perda 패밀리(perda/pergub/perwali/perwako/pergub-prov 등)는 'perda'
                        category = (
                            "perda"
                            if slug_type.startswith(("perda", "pergub", "perwako", "perwali", "perbup", "perdal"))
                            else section.category
                        )

                        yield LawRecord(
                            category=category,
                            law_type=law_type,
                            law_number=law_number,
                            title_id=title_id,
                            source="peraturan_go_id",
                            source_url=detail_url,
                            ministry_code=self.ministry_code,
                            ministry_name_ko=self.ministry_name_ko,
                            year=year,
                            promulgation_date=f"{year}-01-01" if year else None,
                            pdf_url_id=pdf_url,
                        )
                        yielded_this_page += 1

                    if yielded_this_page == 0:
                        break
            finally:
                await page.close()

    @staticmethod
    def _normalize_law_type(slug_type: str, fallback: str) -> str:
        mapping = {
            "uu":              "UU",
            "pp":              "PP",
            "perpres":         "Perpres",
            "permen":          "Permen",
            "permendag":       "Permendag",
            "permenkeu":       "Permenkeu",
            "permenhub":       "Permenhub",
            "permenesdm":      "Permen ESDM",
            "permenkum":       "Permenkumham",
            "permendikdasmen": "Permendikdasmen",
            "permenpan":       "PermenPAN-RB",
            "permenkominfo":   "Permenkominfo",
            "permenperin":    "Permenperin",
            "perda":           "Perda",
            "perwako":         "Perwako",
            "perwali":         "Perwali",
            "pergub":          "Pergub",
            "perbup":          "Perbup",
        }
        return mapping.get(slug_type, fallback)
