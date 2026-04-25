"""교통부 (Kementerian Perhubungan) JDIH scraper.

Site: https://jdih.dephub.go.id

NOTE: 실제 selector는 사이트 구조에 따라 조정 필요.
이 파일은 스켈레톤이며 첫 실행 시 페이지 구조를 점검 후 selector를 채운다.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from ..base_scraper import BaseScraper, LawRecord

log = logging.getLogger(__name__)


class DephubScraper(BaseScraper):
    ministry_code = "dephub"
    ministry_name_ko = "교통부"
    base_url = "https://jdih.dephub.go.id"
    list_path = "/produk-hukum"

    async def scrape(self) -> AsyncIterator[LawRecord]:
        page = await self.new_page()
        await self.goto(page, f"{self.base_url}{self.list_path}")

        # TODO: 실제 selector 확정 필요. 아래는 placeholder.
        # 일반적인 JDIH 사이트는 .table > tbody > tr 구조.
        for page_no in range(1, self.max_pages + 1):
            rows = await page.query_selector_all("table tbody tr")
            if not rows:
                log.warning("[dephub] no rows on page %d", page_no)
                break

            for tr in rows:
                cells = await tr.query_selector_all("td")
                if len(cells) < 4:
                    continue
                law_number = (await cells[1].inner_text()).strip()
                title_id = (await cells[2].inner_text()).strip()
                link_el = await cells[2].query_selector("a")
                source_url = (await link_el.get_attribute("href")) if link_el else ""
                if source_url and source_url.startswith("/"):
                    source_url = f"{self.base_url}{source_url}"
                if not (law_number and title_id and source_url):
                    continue
                yield LawRecord(
                    category="keputusan",
                    law_type="Permen",
                    law_number=law_number,
                    title_id=title_id,
                    source="jdih_dephub",
                    source_url=source_url,
                    ministry_code=self.ministry_code,
                    ministry_name_ko=self.ministry_name_ko,
                )

            next_btn = await page.query_selector("a.next, li.next > a")
            if not next_btn:
                break
            await next_btn.click()
            await page.wait_for_load_state("domcontentloaded")
