from .dephub import DephubScraper
from .esdm import EsdmScraper
from .bkpm import BkpmScraper
from .kemenkeu import KemenkeuScraper
from .kemendag import KemendagScraper

ALL_SCRAPERS = [
    DephubScraper,
    EsdmScraper,
    BkpmScraper,
    KemenkeuScraper,
    KemendagScraper,
]

__all__ = [
    "DephubScraper",
    "EsdmScraper",
    "BkpmScraper",
    "KemenkeuScraper",
    "KemendagScraper",
    "ALL_SCRAPERS",
]
