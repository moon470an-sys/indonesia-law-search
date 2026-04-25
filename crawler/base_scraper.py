"""Base class for ministry JDIH scrapers."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import AsyncIterator

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


@dataclass
class LawRecord:
    # — 1차 메뉴 매핑
    category: str                         # 'peraturan'|'keputusan'|'lampiran'|'perda'|'putusan'|'kepkl'|'perjanjian'|'lainnya'
    law_type: str                         # 'UU' | 'PP' | 'Perpres' | 'Permen' | 'Kepmen' | 'Perda' | 'KEPUTUSAN MENTERI ESDM' …
    law_number: str                       # 예: '12 Tahun 2023'
    title_id: str                         # 인니어 원제목
    source: str                           # 'peraturan_go_id' | 'jdih_esdm' | …
    source_url: str

    # — 부처/지역
    ministry_code: str | None = None
    ministry_name_ko: str | None = None
    region_code: str | None = None

    # — 일자
    year: int | None = None
    enactment_date: str | None = None
    promulgation_date: str | None = None
    effective_date: str | None = None
    repealed_date: str | None = None

    # — 상태
    status: str = "berlaku"
    era: str = "modern"

    # — 외국어/원문
    title_en: str | None = None
    pdf_url_id: str | None = None
    pdf_url_en: str | None = None

    def as_row(self) -> dict:
        return asdict(self)


class BaseScraper:
    ministry_code: str = ""
    ministry_name_ko: str = ""
    base_url: str = ""

    def __init__(self, headless: bool = True, max_pages: int = 5):
        self.headless = headless
        self.max_pages = max_pages

    async def __aenter__(self) -> "BaseScraper":
        self._pw = await async_playwright().start()
        self._browser: Browser = await self._pw.chromium.launch(headless=self.headless)
        self._context: BrowserContext = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-crawler/0.1"
            ),
            locale="id-ID",
        )
        return self

    async def __aexit__(self, *exc) -> None:
        await self._context.close()
        await self._browser.close()
        await self._pw.stop()

    async def new_page(self) -> Page:
        page = await self._context.new_page()
        page.set_default_timeout(30_000)
        return page

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    async def goto(self, page: Page, url: str) -> None:
        await page.goto(url, wait_until="domcontentloaded")

    async def scrape(self) -> AsyncIterator[LawRecord]:
        """Override in subclasses. Should yield LawRecord per discovered law."""
        if False:
            yield  # pragma: no cover
        raise NotImplementedError

    async def run(self) -> list[dict]:
        rows: list[dict] = []
        async for record in self.scrape():
            rows.append(record.as_row())
        log.info("[%s] scraped %d records", self.ministry_code, len(rows))
        return rows
