"""peraturan.bpk.go.id (BPK 국가 법령 DB) 크롤 — 로컬 실행.

배경: peraturan.go.id 는 인도네시아 외 모든 IP(데이터센터 포함)를 차단해 우회 불가.
대안으로 BPK 의 공식 법령 DB(peraturan.bpk.go.id)를 쓴다. BPK 는 Cloudflare 뒤에
있어 일반 httpx 는 403 이지만 cloudscraper 로 통과되며, 한국에서 직접 접근된다
(프록시/RunPod 불필요).

검색: /Search?keywords=&jenis=<JENIS>&tahun=<YEAR>[&p=<page>]  (최신순)
카드: div.card 안 <a href="/Details/<id>/<slug>">제목</a>
      메타라인 "Undang-undang (UU) Nomor N Tahun Y • Berlaku/Dicabut ..."
→ 신규 등록은 물론 폐기(Dicabut) 상태까지 수집한다.

결과는 laws.db 에 source="peraturan_bpk" 로 upsert (dedup: source+source_url),
data/laws/peraturan_bpk.jsonl 재덤프.

실행 (크롤러 파이썬 C:\\Python314 — cloudscraper/bs4 설치돼 있음):
    python -m scripts.crawl_bpk --probe                 # 접속/파싱 검증
    python -m scripts.crawl_bpk                          # 일일: 올해분 신규
    python -m scripts.crawl_bpk --years 2026 2025        # 최근 2년
    python -m scripts.crawl_bpk --max-pages 50 --years 2024 2023 ...   # 백필
    python -m scripts.crawl_bpk --no-import              # 크롤만, DB 미반영
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cloudscraper
from bs4 import BeautifulSoup

SRC = "peraturan_bpk"
MINISTRY_CODE = "kumham"
MINISTRY_NAME_KO = "법무인권부"
BASE = "https://peraturan.bpk.go.id"

# (BPK jenis 코드, 우리 law_type, category)
JENIS = [
    ("UU",      "UU",      "peraturan"),
    ("PERPPU",  "Perppu",  "peraturan"),
    ("PP",      "PP",      "peraturan"),
    ("PERPRES", "Perpres", "peraturan"),
    ("KEPPRES", "Keppres", "keputusan"),
    ("INPRES",  "Inpres",  "keputusan"),
    ("PM",      "Permen",  "peraturan"),
    ("KEPMEN",  "Kepmen",  "keputusan"),
    ("PERDA",   "Perda",   "perda"),
]

# <type>-no-<num>-tahun-<year>  (perda 는 지역 토큰이 끼기도 함)
SLUG_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:-(?P<region>[a-z-]+?))?"
    r"-no-(?P<num>[\w.+]+?)"
    r"-tahun-(?P<year>\d{4})$",
    re.IGNORECASE,
)
META_RE = re.compile(r"Nomor\s+(?P<num>\S+)\s+Tahun\s+(?P<year>\d{4})\s*[•·]\s*(?P<status>[^\n]{0,40})",
                     re.IGNORECASE)

# 슬러그 타입 → 우리 law_type. (검색 결과에 다른 타입 카드가 섞여 나오므로 슬러그로 판정)
SLUG_TYPE_MAP = {
    "uu": "UU", "uud": "UUD", "perpu": "Perppu", "perppu": "Perppu",
    "pp": "PP", "perpres": "Perpres", "keppres": "Keppres", "inpres": "Inpres",
    "permen": "Permen", "pmk": "Permenkeu", "perda": "Perda",
    "pergub": "Pergub", "perwali": "Perwali", "perwako": "Perwako",
    "perbup": "Perbup", "kepmen": "Kepmen", "keppres": "Keppres",
}


def _resolve(slug_type: str, fallback_type: str, fallback_cat: str) -> tuple[str, str]:
    """슬러그 타입 → (law_type, category). 모르면 jenis 폴백."""
    st = slug_type.lower()
    law_type = SLUG_TYPE_MAP.get(st)
    if law_type is None:
        # permenkeu/permenkes 처럼 permen* 접두는 Permen 으로
        if st.startswith("permen") or st.startswith("pm"):
            law_type = "Permen"
        elif st.startswith("kepmen") or st.startswith("kep"):
            law_type = "Kepmen"
        elif st.startswith(("perda", "pergub", "perwali", "perwako", "perbup")):
            law_type = "Perda"
        else:
            law_type = fallback_type
    if st.startswith(("perda", "pergub", "perwali", "perwako", "perbup")):
        cat = "perda"
    elif st.startswith(("keppres", "inpres", "kepmen", "kep")):
        cat = "keputusan"
    else:
        cat = fallback_cat
    return law_type, cat


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False})


def parse_status(text: str) -> str:
    """카드 자체 상태: 메타라인 '• Berlaku/Dicabut...' 에서 추출."""
    m = META_RE.search(text)
    if m:
        s = m.group("status").lower()
        if "cabut" in s or "tidak berlaku" in s:
            return "dicabut"
        if "berlaku" in s:
            return "berlaku"
    # 폴백
    return "berlaku"


def parse_cards(html: str, law_type: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    seen: set[str] = set()
    for card in soup.select("div.card"):
        a = card.select_one('a[href^="/Details/"]')
        if not a:
            continue
        href = (a.get("href") or "").strip()
        if not href.startswith("/Details/") or href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True)
        if not title:
            continue
        slug = href.rsplit("/", 1)[-1]
        m = SLUG_RE.match(slug)
        card_text = re.sub(r"\s+", " ", card.get_text(" ", strip=True))
        if m:
            slug_type = m.group("type").lower()
            num = m.group("num")
            year = int(m.group("year"))
            region = m.group("region")
        else:
            slug_type = slug.split("-", 1)[0].lower()
            mm = META_RE.search(card_text)
            num = mm.group("num") if mm else slug
            year = int(mm.group("year")) if mm else None
            region = None
        # 타입/카테고리는 슬러그 기준으로 판정 (검색 결과에 타 타입이 섞임)
        rec_type, rec_cat = _resolve(slug_type, law_type, category)
        status = parse_status(card_text)
        out.append({
            "category": rec_cat,
            "law_type": rec_type,
            "law_number": f"Nomor {num} Tahun {year}" if year else f"Nomor {num}",
            "title_id": title,
            "source": SRC,
            "source_url": f"{BASE}{href}",
            "ministry_code": MINISTRY_CODE,
            "ministry_name_ko": MINISTRY_NAME_KO,
            # region_code 는 regions(code) FK 대상이라 슬러그의 지역토큰(kab-kudus 등)을
            # 그대로 넣으면 FK 위반. 기존 데이터처럼 None 으로 둔다(지역정보는 slug/url 에 남음).
            "region_code": None,
            "year": year,
            "enactment_date": None,
            "promulgation_date": f"{year}-01-01" if year else None,
            "effective_date": None,
            "repealed_date": None,
            "status": status,
            "era": "modern",
            "title_en": None,
            "pdf_url_id": None,   # 상세 enrich 단계에서 /Download 링크 채움(옵션)
            "pdf_url_en": None,
        })
    return out


def fetch(s, url: str, retries: int = 3) -> str | None:
    last = None
    for i in range(retries):
        try:
            r = s.get(url, timeout=40)
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (i + 1))
    log(f"  ! fetch 실패 {url}: {last}")
    return None


def crawl(years: list[int], max_pages: int) -> list[dict]:
    """연도별 최신순 피드를 페이지네이션. BPK 의 jenis 파라미터는 무시되므로
    타입은 슬러그로 판정하고 연도(tahun)+페이지(p)로 전 타입을 수집한다."""
    s = scraper()
    records: list[dict] = []
    seen: set[str] = set()
    for year in years:
        ycount = 0
        empty_streak = 0
        for page in range(1, max_pages + 1):
            url = f"{BASE}/Search?keywords=&tahun={year}&p={page}"
            html = fetch(s, url)
            if html is None:
                break
            recs = parse_cards(html, "Lainnya", "peraturan")
            if not recs:
                break
            new_on_page = 0
            for r in recs:
                if r["source_url"] in seen:
                    continue
                seen.add(r["source_url"])
                records.append(r)
                ycount += 1
                new_on_page += 1
            # 연속으로 새 항목이 없으면(끝 도달) 조기 종료
            empty_streak = empty_streak + 1 if new_on_page == 0 else 0
            if empty_streak >= 2:
                break
            time.sleep(0.6)
        log(f"  {year}: {ycount} records")
    return records


SUMMARY_PATH = ROOT / "data" / "pending" / "bpk.summary.json"
DICABUT = ("dicabut", "dicabut_sebagian")


def do_import(records: list[dict]) -> dict:
    """records 를 upsert. 진짜 신규 법령과 '새로 폐기로 바뀐' 법령을 추적해
    bpk.summary.json 에 기록(이메일용)."""
    from crawler import db, dump_jsonl
    db.init_db()
    new_laws: list[dict] = []
    newly_dicabut: list[dict] = []
    with db.connect() as c:
        before = c.execute("SELECT COUNT(*) FROM laws WHERE source=?", (SRC,)).fetchone()[0]
        for r in records:
            ex = c.execute(
                "SELECT status FROM laws WHERE source=? AND source_url=?",
                (SRC, r["source_url"]),
            ).fetchone()
            db.upsert_law(c, r)
            brief = {"law_type": r["law_type"], "law_number": r["law_number"],
                     "title_id": r["title_id"], "year": r["year"],
                     "source_url": r["source_url"], "status": r["status"]}
            if ex is None:
                new_laws.append(brief)
            elif r["status"] in DICABUT and (ex[0] not in DICABUT):
                newly_dicabut.append(brief)
        after = c.execute("SELECT COUNT(*) FROM laws WHERE source=?", (SRC,)).fetchone()[0]
        dicabut_now = c.execute(
            f"SELECT COUNT(*) FROM laws WHERE source=? AND status IN {DICABUT}", (SRC,)
        ).fetchone()[0]
    dump_jsonl.main([SRC])

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": SRC,
        "new_count": len(new_laws),
        "repealed_count": len(newly_dicabut),
        "new_laws": new_laws[:50],
        "repealed_laws": newly_dicabut[:50],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"seen": len(records), "new": after - before, "before": before, "after": after,
            "new_laws": len(new_laws), "newly_dicabut": len(newly_dicabut),
            "dicabut_now": dicabut_now}


def main() -> int:
    ap = argparse.ArgumentParser()
    cur = datetime.now().year
    ap.add_argument("--years", type=int, nargs="*", default=[cur],
                    help=f"크롤 연도 (기본 올해 {cur})")
    ap.add_argument("--max-pages", type=int, default=8, help="연도별 최대 페이지(최신순). 백필은 크게")
    ap.add_argument("--no-import", action="store_true")
    ap.add_argument("--probe", action="store_true", help="UU 1페이지만 접속/파싱 확인")
    args = ap.parse_args()

    if args.probe:
        s = scraper()
        url = f"{BASE}/Search?keywords=&jenis=UU&tahun={cur}"
        log(f"probe {url}")
        html = fetch(s, url)
        if not html:
            log("PROBE FAIL: 접속 불가")
            return 1
        recs = parse_cards(html, "UU", "peraturan")
        log(f"PROBE OK: records={len(recs)}")
        for r in recs[:5]:
            log(f"  - [{r['status']}] {r['law_type']} {r['law_number']} | {r['title_id'][:50]} | {r['source_url']}")
        return 0 if recs else 2

    log(f"=== BPK 크롤 (years={args.years}, max_pages={args.max_pages}) ===")
    t0 = time.time()
    records = crawl(args.years, args.max_pages)
    log(f"크롤 완료: 총 {len(records)} records ({time.time()-t0:.0f}s)")

    if args.no_import:
        out = ROOT / "data" / "pending" / "bpk_crawl.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log(f"--no-import: {out} 에 {len(records)}건 기록")
        return 0

    imp = do_import(records)
    log(f"laws.db 반영: 신규 법령 {imp['new_laws']}건, 새 폐기 {imp['newly_dicabut']}건 "
        f"(peraturan_bpk {imp['before']}→{imp['after']}, 폐기 누적 {imp['dicabut_now']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
