"""국가비서실 (Kementerian Sekretariat Negara) JDIH scraper.

Site: https://jdih.setneg.go.id  (Next.js SPA + JSON API)

setneg 의 JDIH 는 국가 1차 법령(UU/Perppu/PP/Perpres) 이 가장 빨리 게시되는
공식 출처다. 페이지는 클라이언트 렌더링이라 DOM 스크래핑 대신 백엔드 API 를
직접 호출한다 (Playwright 불필요 → BaseScraper 의 chromium 기동을 우회).

API (2026-06 확인):
  POST /api/hukumproduk/produkhukum
    body: {"tentang":"", "p_lihan":"semua", "jns":[<코드>...], "thn":[<연도>...],
           "status":"", "terx":"All", "length":<페이지크기>, "start":<오프셋>}
    resp: {"data":[{idperaturan,no_peraturan,tahun,tentang,jns,nama_jenis,
                    file_jj,files,tgl_di,diundangkan,status_hukum}...],
           "jml":<전체건수>, ...}
  목록은 타입(jns)별로 최신순(newest-first) 이지만, 여러 타입을 한 번에
  넣으면 타입별로 묶여 날짜 전역 정렬이 깨진다. → 타입별로 따로 페이징한다.

상세 페이지(source_url): /detailperaturan?jns=<jns>&no=<no>&thn=<thn>
PDF 직링크는 reCAPTCHA/뷰어 뒤에 있어 안정적으로 못 얻음 → pdf_url_id 는 비움.

source 값은 ministries 시드의 'kemensetneg'(국가비서실)에 맞춰 'jdih_kemensetneg'.
(db.py CHECK 제약 / source_value_for 규약과 일치해야 한다.)
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator
from urllib.parse import urlencode

import httpx

from ..base_scraper import BaseScraper, LawRecord

log = logging.getLogger(__name__)


class SetnegScraper(BaseScraper):
    ministry_code = "kemensetneg"
    ministry_name_ko = "국가비서실"
    base_url = "https://jdih.setneg.go.id"
    api_url = f"{base_url}/api/hukumproduk/produkhukum"

    per_page = 50

    # (jns API 코드, law_type 표시 라벨, category)
    #   UU/Perppu/PP/Perpres/Permensesneg → 법령(peraturan)
    #   Keppres/Inpres                    → 행정규칙·결정(keputusan)
    JENIS: list[tuple[str, str, str]] = [
        ("UU",           "UU",           "peraturan"),
        ("PERPU",        "Perppu",       "peraturan"),
        ("PP",           "PP",           "peraturan"),
        ("PERPRES",      "Perpres",      "peraturan"),
        ("PERMENSESNEG", "Permensesneg", "peraturan"),
        ("KEPPRES",      "Keppres",      "keputusan"),
        ("INPRES",       "Inpres",       "keputusan"),
    ]

    # status_hukum(API) → laws.status CHECK 허용값
    STATUS_MAP = {
        "berlaku":           "berlaku",
        "berlaku sebagian":  "dicabut_sebagian",
        "sebagian":          "dicabut_sebagian",
        "dicabut":           "dicabut",
        "dicabut sebagian":  "dicabut_sebagian",
        "tidak berlaku":     "dicabut",
        "diubah":            "diubah",
        "mengubah":          "berlaku",
        "belum berlaku":     "belum_berlaku",
    }

    def __init__(
        self,
        headless: bool = True,
        max_pages: int = 200,
        known_source_urls: set[str] | None = None,
        stop_after_known: int = 5,
        min_year: int | None = None,
        jenis: list[str] | None = None,
    ):
        # max_pages here = 타입별 최대 페이지 ceiling (안전장치).
        super().__init__(headless=headless, max_pages=max_pages)
        # Incremental: known_source_urls 가 주어지면 한 타입에서
        # stop_after_known 개 연속으로 이미 아는 URL 을 만나면 그 타입 종료.
        self.known_source_urls = known_source_urls or set()
        self.stop_after_known = stop_after_known
        # 시드 바운딩: 이 연도 미만이 나오면 그 타입 페이징 종료(최신순이므로).
        self.min_year = min_year
        # 수집할 jns 코드 부분집합(없으면 JENIS 전체).
        self._jenis_filter = set(jenis) if jenis else None

    # ── Playwright 대신 httpx 비동기 클라이언트 사용 ──────────────────
    async def __aenter__(self) -> "SetnegScraper":
        # 정부 사이트지만 간헐적으로 연결을 강제 종료(WinError 10054)해서
        # 호출마다 재시도한다. http2 미사용(h2 미설치 환경 대비).
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 jdih-crawler/0.1"
                ),
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/produk-hukum/instrumen/peraturan",
                "Accept": "application/json, text/plain, */*",
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def _post(self, payload: dict, tries: int = 6) -> dict:
        last: Exception | None = None
        for attempt in range(tries):
            try:
                r = await self._client.post(self.api_url, json=payload)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001 — 네트워크/디코딩 무엇이든 재시도
                last = e
                await asyncio.sleep(1.0 + attempt * 0.8)
        raise RuntimeError(f"setneg API failed after {tries} tries: {last}")

    def _detail_url(self, jns: str, no: str, thn: str) -> str:
        return f"{self.base_url}/detailperaturan?" + urlencode(
            {"jns": jns, "no": no, "thn": thn}
        )

    @staticmethod
    def _date(value: str | None) -> str | None:
        # API 날짜는 ISO "2026-05-20T00:00:00.000Z" → 'YYYY-MM-DD' 만 취함.
        if not value or not isinstance(value, str):
            return None
        return value[:10] or None

    async def scrape(self) -> AsyncIterator[LawRecord]:
        for jns, law_type, category in self.JENIS:
            if self._jenis_filter and jns not in self._jenis_filter:
                continue
            async for rec in self._scrape_jenis(jns, law_type, category):
                yield rec

    async def _scrape_jenis(
        self, jns: str, law_type: str, category: str
    ) -> AsyncIterator[LawRecord]:
        consecutive_known = 0
        for page_no in range(self.max_pages):
            start = page_no * self.per_page
            payload = {
                "tentang": "",
                "p_lihan": "semua",
                "jns": [jns],
                "thn": [],
                "status": "",
                "terx": "All",
                "length": self.per_page,
                "start": start,
            }
            body = await self._post(payload)
            data = body.get("data") or []
            if not data:
                break
            if page_no == 0:
                log.info("[setneg] %s: total=%s", jns, body.get("jml"))

            stop = False
            for item in data:
                no = str(item.get("no_peraturan") or "").strip()
                thn = str(item.get("tahun") or "").strip()
                tentang = (item.get("tentang") or "").strip()
                if not (no and thn and tentang):
                    continue

                year = int(thn) if thn.isdigit() else None
                # 최신순이므로 min_year 미만이 나오면 이 타입 종료.
                if self.min_year and year and year < self.min_year:
                    stop = True
                    break

                source_url = self._detail_url(jns, no, thn)
                nama_jenis = (item.get("nama_jenis") or law_type).strip()
                # 제목: "<Jenis> Nomor <no> Tahun <thn> tentang <tentang>"
                title_id = f"{nama_jenis} Nomor {no} Tahun {thn} tentang {tentang}"
                status = self.STATUS_MAP.get(
                    (item.get("status_hukum") or "").strip().lower(),
                    "tidak_diketahui",
                )

                if source_url in self.known_source_urls:
                    consecutive_known += 1
                else:
                    consecutive_known = 0

                yield LawRecord(
                    category=category,
                    law_type=law_type,
                    law_number=f"{no} Tahun {thn}",
                    title_id=title_id,
                    source="jdih_kemensetneg",
                    source_url=source_url,
                    ministry_code=self.ministry_code,
                    ministry_name_ko=self.ministry_name_ko,
                    year=year,
                    enactment_date=self._date(item.get("tgl_di")),
                    promulgation_date=self._date(item.get("diundangkan")),
                    status=status,
                )

                if (
                    self.known_source_urls
                    and consecutive_known >= self.stop_after_known
                ):
                    log.info(
                        "[setneg] %s: stopping early (%d consecutive known)",
                        jns, consecutive_known,
                    )
                    stop = True
                    break

            if stop:
                break
            # 마지막 페이지(데이터가 per_page 미만)면 종료.
            if len(data) < self.per_page:
                break
