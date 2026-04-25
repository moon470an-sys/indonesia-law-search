from .peraturan_go_id import PeraturanGoIdScraper
from .dephub import DephubScraper
from .esdm import EsdmScraper
from .bkpm import BkpmScraper
from .kemenkeu import KemenkeuScraper
from .kemendag import KemendagScraper

# 1차 출처 우선, JDIH는 보완 출처
ALL_SCRAPERS = [
    PeraturanGoIdScraper,
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
