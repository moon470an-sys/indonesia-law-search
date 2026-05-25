from .peraturan_go_id import PeraturanGoIdScraper
from .dephub import DephubScraper
from .esdm import EsdmScraper
from .bkpm import BkpmScraper
from .kemenkeu import KemenkeuScraper
from .kemendag import KemendagScraper

# 1차 출처 우선, JDIH는 보완 출처
# PeraturanGoIdScraper 는 peraturan.go.id 가 해외 IP를 전부 차단해 매 페이지 RetryError(5분 낭비)
# → 일일 크롤에서 제외. 국가 법령은 scripts/crawl_bpk.py(peraturan.bpk.go.id, cloudscraper)로 수집한다.
# (클래스/KEY_MAP("peraturan")은 유지 — 차단 해제 시 수동 `update_all peraturan` 으로 복귀 가능)
ALL_SCRAPERS = [
    DephubScraper,
    EsdmScraper,
    BkpmScraper,
    KemenkeuScraper,
    KemendagScraper,
]

__all__ = [
    "PeraturanGoIdScraper",
    "DephubScraper",
    "EsdmScraper",
    "BkpmScraper",
    "KemenkeuScraper",
    "KemendagScraper",
    "ALL_SCRAPERS",
]
