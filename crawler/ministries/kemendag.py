"""무역부 (Kementerian Perdagangan) JDIH scraper.

Site: https://jdih.kemendag.go.id
"""
from __future__ import annotations

from typing import AsyncIterator

from ..base_scraper import BaseScraper, LawRecord


class KemendagScraper(BaseScraper):
    ministry_code = "kemendag"
    ministry_name_ko = "무역부"
    base_url = "https://jdih.kemendag.go.id"
    list_path = "/peraturan"

    async def scrape(self) -> AsyncIterator[LawRecord]:
        page = await self.new_page()
        await self.goto(page, f"{self.base_url}{self.list_path}")
        # TODO: selector 확정.
        rows = await page.query_selector_all("table tbody tr")
        for tr in rows:
            tds = await tr.query_selector_all("td")
            if len(tds) < 3:
                continue
            link = await tds[1].query_selector("a")
            if not link:
                continue
            title_id = (await link.inner_text()).strip()
            source_url = (await link.get_attribute("href")) or ""
            if source_url.startswith("/"):
                source_url = f"{self.base_url}{source_url}"
            law_number = (await tds[0].inner_text()).strip() or title_id[:64]
            yield LawRecord(
                ministry_code=self.ministry_code,
                ministry_name_ko=self.ministry_name_ko,
                law_number=law_number,
                title_id=title_id,
                source_url=source_url,
            )
