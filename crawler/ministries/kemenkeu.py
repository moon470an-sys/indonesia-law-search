"""재무부 (Kementerian Keuangan) JDIH scraper.

Site: https://jdih.kemenkeu.go.id
"""
from __future__ import annotations

from typing import AsyncIterator

from ..base_scraper import BaseScraper, LawRecord


class KemenkeuScraper(BaseScraper):
    ministry_code = "kemenkeu"
    ministry_name_ko = "재무부"
    base_url = "https://jdih.kemenkeu.go.id"
    list_path = "/in/dokumen"

    async def scrape(self) -> AsyncIterator[LawRecord]:
        page = await self.new_page()
        await self.goto(page, f"{self.base_url}{self.list_path}")
        # TODO: selector 확정.
        items = await page.query_selector_all(".document-item, article.law")
        for it in items:
            link = await it.query_selector("a")
            if not link:
                continue
            title_id = (await link.inner_text()).strip()
            source_url = (await link.get_attribute("href")) or ""
            if source_url.startswith("/"):
                source_url = f"{self.base_url}{source_url}"
            num_el = await it.query_selector(".doc-number, .nomor")
            law_number = (await num_el.inner_text()).strip() if num_el else title_id[:64]
            yield LawRecord(
                category="keputusan",
                law_type="Permen",
                law_number=law_number,
                title_id=title_id,
                source="jdih_kemenkeu",
                source_url=source_url,
                ministry_code=self.ministry_code,
                ministry_name_ko=self.ministry_name_ko,
            )
