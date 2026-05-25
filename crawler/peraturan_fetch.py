"""Standalone peraturan.go.id fetcher — runs on a NON-Korea egress (RunPod relay).

peraturan.go.id blocks Korean IPs at the network layer (TCP connect timeout),
so this script is meant to run on a relay box (RunPod pod) whose egress is not
Korean. It does NOT need Playwright — peraturan.go.id listing pages are
server-rendered, so plain httpx + BeautifulSoup is enough (lighter, faster).

It mirrors crawler/ministries/peraturan_go_id.py's parsing but is fully
self-contained (only httpx + beautifulsoup4), so it can be uploaded and run on
a bare pod. Output is JSON Lines, one record per law, with fields matching
crawler.base_scraper.LawRecord.as_row() so the importer can db.upsert_law()
directly.

On the pod:
    pip install httpx beautifulsoup4
    python peraturan_fetch.py --out /workspace/peraturan.jsonl --pages-per-section 5
    python peraturan_fetch.py --probe          # 연결성/렌더링만 확인 (1페이지)

Sections: /uu /pp /perpres /permen /perda  (type ∈ uu|pp|perpres|permen|perda)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://peraturan.go.id"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

SLUG_RE = re.compile(
    r"^/id/"
    r"(?P<type>[a-z]+)"
    r"(?:-(?P<region>[a-z-]+?))?"
    r"-no-(?P<num>[\w.+-]+?)"
    r"-tahun-(?P<year>\d{4})/?$",
    re.IGNORECASE,
)

# (path, law_type, category)
SECTIONS = (
    ("/uu",      "UU",      "peraturan"),
    ("/pp",      "PP",      "peraturan"),
    ("/perpres", "Perpres", "peraturan"),
    ("/permen",  "Permen",  "peraturan"),
    ("/perda",   "Perda",   "perda"),
)

LAW_TYPE_MAP = {
    "uu": "UU", "pp": "PP", "perpres": "Perpres", "permen": "Permen",
    "permendag": "Permendag", "permenkeu": "Permenkeu", "permenhub": "Permenhub",
    "permenesdm": "Permen ESDM", "permenkum": "Permenkumham",
    "permendikdasmen": "Permendikdasmen", "permenpan": "PermenPAN-RB",
    "permenkominfo": "Permenkominfo", "permenperin": "Permenperin",
    "perda": "Perda", "perwako": "Perwako", "perwali": "Perwali",
    "pergub": "Pergub", "perbup": "Perbup",
}

MINISTRY_CODE = "kumham"
MINISTRY_NAME_KO = "법무인권부"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch(client: httpx.Client, url: str, retries: int = 3) -> str | None:
    last = None
    for i in range(retries):
        try:
            r = client.get(url, timeout=30, follow_redirects=True)
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1.5 * (i + 1))
    log(f"  ! fetch 실패 {url}: {last}")
    return None


def parse_page(html: str, law_type: str, category: str) -> list[dict]:
    """div.wrapper 내 a[href^=/id/] → LawRecord 호환 dict 리스트."""
    soup = BeautifulSoup(html, "html.parser")
    wrappers = soup.select("div.wrapper")
    out: list[dict] = []
    seen: set[str] = set()
    for w in wrappers:
        a = w.select_one('a[href^="/id/"][title="lihat detail"]') or w.select_one('a[href^="/id/"]')
        if not a:
            continue
        href = (a.get("href") or "").strip()
        if not href.startswith("/id/") or href in seen:
            continue
        seen.add(href)
        title_id = a.get_text(strip=True)
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
            slug_type = law_type.lower()
            year = None
            region = None
            law_number = href.rsplit("/", 1)[-1]

        detail_url = urljoin(BASE_URL, href)
        slug = href.rsplit("/", 1)[-1]
        pdf_url = f"{BASE_URL}/files/{slug}.pdf"
        resolved_type = LAW_TYPE_MAP.get(slug_type, law_type)
        cat = ("perda" if slug_type.startswith(
                   ("perda", "pergub", "perwako", "perwali", "perbup", "perdal"))
               else category)

        out.append({
            "category": cat,
            "law_type": resolved_type,
            "law_number": law_number,
            "title_id": title_id,
            "source": "peraturan_go_id",
            "source_url": detail_url,
            "ministry_code": MINISTRY_CODE,
            "ministry_name_ko": MINISTRY_NAME_KO,
            "region_code": region,
            "year": year,
            "enactment_date": None,
            "promulgation_date": f"{year}-01-01" if year else None,
            "effective_date": None,
            "repealed_date": None,
            "status": "berlaku",
            "era": "modern",
            "title_en": None,
            "pdf_url_id": pdf_url,
            "pdf_url_en": None,
        })
    return out


def probe(client: httpx.Client) -> int:
    """연결성 + 서버렌더 여부 확인 — uu 1페이지만."""
    url = f"{BASE_URL}/uu?page=1"
    log(f"probe {url}")
    t = time.time()
    html = fetch(client, url)
    if html is None:
        log("PROBE FAIL: 연결 불가")
        return 1
    soup = BeautifulSoup(html, "html.parser")
    wrappers = soup.select("div.wrapper")
    recs = parse_page(html, "UU", "peraturan")
    log(f"PROBE OK ({time.time()-t:.1f}s): html={len(html)}b, div.wrapper={len(wrappers)}, 파싱 records={len(recs)}")
    for r in recs[:3]:
        log(f"  - [{r['law_type']}] {r['law_number']} | {r['title_id'][:60]} | {r['source_url']}")
    return 0 if recs else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="peraturan.jsonl")
    ap.add_argument("--pages-per-section", type=int, default=5,
                    help="섹션별 크롤 페이지 수 (신규는 앞쪽). 백필은 크게.")
    ap.add_argument("--probe", action="store_true", help="연결성/렌더링만 확인")
    ap.add_argument("--proxy", default=None, help="로컬에서 프록시 경유 시 (socks5://host:port 등)")
    args = ap.parse_args()

    client_kwargs = {"headers": {"User-Agent": UA}}
    if args.proxy:
        client_kwargs["proxy"] = args.proxy

    with httpx.Client(**client_kwargs) as client:
        if args.probe:
            return probe(client)

        total = 0
        with open(args.out, "w", encoding="utf-8") as fo:
            for path, law_type, category in SECTIONS:
                sec_count = 0
                seen_urls: set[str] = set()
                for page_no in range(1, args.pages_per_section + 1):
                    url = f"{BASE_URL}{path}?page={page_no}"
                    html = fetch(client, url)
                    if html is None:
                        break
                    recs = parse_page(html, law_type, category)
                    if not recs:
                        break
                    new_on_page = 0
                    for r in recs:
                        if r["source_url"] in seen_urls:
                            continue
                        seen_urls.add(r["source_url"])
                        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                        total += 1
                        sec_count += 1
                        new_on_page += 1
                    if new_on_page == 0:
                        break
                    time.sleep(0.5)
                log(f"  {path}: {sec_count} records")
        log(f"완료: 총 {total} records → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
