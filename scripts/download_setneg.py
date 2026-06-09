"""Download setneg(jdih_kemensetneg) 원문 PDF into the RAG category folders.

setneg 의 PDF 는 `/api/hukumproduk/pdf?l=uploads&f=<file>&fl=<idperaturan>` 로
reCAPTCHA 없이 직접 받을 수 있다(스크레이퍼가 그 URL 을 pdf_url_id 에 채워둠).
download_originals 와 같은 classify()/safe_filename() 으로 hierarchy 폴더에 저장해
RAG 의 discover_pdfs() 가 동일하게 인덱싱하도록 한다.

이 다운로더는 source='jdih_kemensetneg' 행만 대상으로 하므로 전체 DB 를 훑는
download_originals 와 달리 가볍고, setneg 전용 Referer/재시도를 쓴다.

실행:
    python -m scripts.download_setneg            # 전체 (skip existing)
    python -m scripts.download_setneg --limit 5  # 스모크 테스트
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from crawler import db
from scripts.download_originals import classify, safe_filename, HIERARCHY_DIRS, ROOT_OUT

REFERER = "https://jdih.setneg.go.id/"
_tl = threading.local()


def _client() -> httpx.Client:
    if not hasattr(_tl, "c"):
        _tl.c = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=20.0),
            verify=False,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Referer": REFERER,
            },
        )
    return _tl.c


def download_one(law: dict, dest: Path, tries: int = 6) -> dict:
    out = dest / f"{law['fname']}.pdf"
    if out.exists() and out.stat().st_size > 0:
        with out.open("rb") as f:
            if f.read(4) == b"%PDF":
                return {"id": law["id"], "status": "skipped"}
    url = law["pdf_url_id"]
    c = _client()
    last = ""
    for attempt in range(tries):
        try:
            r = c.get(url)
            if r.status_code != 200:
                last = f"http_{r.status_code}"
            elif r.content[:4] != b"%PDF":
                last = f"not_pdf:{r.content[:4]!r}"
                break  # served something else — not transient
            else:
                tmp = out.with_suffix(".pdf.part")
                tmp.write_bytes(r.content)
                tmp.replace(out)
                return {"id": law["id"], "status": "ok", "size": len(r.content)}
        except Exception as e:
            last = f"{type(e).__name__}"
        time.sleep(1.0 + attempt * 0.8)
    return {"id": law["id"], "status": "fail", "error": last, "url": url}


def fetch_rows() -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT id, law_type, law_number, title_id, category, pdf_url_id "
            "FROM laws WHERE source='jdih_kemensetneg' "
            "  AND pdf_url_id IS NOT NULL AND pdf_url_id <> '' ORDER BY id"
        ).fetchall()
    out = []
    seen: dict[str, int] = {}
    for r in rows:
        d = dict(r)
        d["hierarchy"] = classify(d["law_type"], d["category"], d["title_id"])
        fname = safe_filename(
            law_type=d["law_type"] or "",
            law_number=d["law_number"] or "",
            title=d["title_id"] or "",
        )
        k = (d["hierarchy"], fname.lower())
        seen[k] = seen.get(k, 0) + 1
        if seen[k] > 1:
            fname = f"{fname}__id{d['id']}"
        d["fname"] = fname
        out.append(d)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    rows = fetch_rows()
    if args.limit:
        rows = rows[: args.limit]
    by_h: dict[str, list[dict]] = {}
    for d in rows:
        by_h.setdefault(d["hierarchy"], []).append(d)
    print(f"setneg PDFs to fetch: {len(rows)}  ({ {h: len(v) for h, v in by_h.items()} })")

    counts = {"ok": 0, "skipped": 0, "fail": 0}
    fails: list[dict] = []
    t0 = time.time()
    for h, laws in by_h.items():
        dest = ROOT_OUT / HIERARCHY_DIRS[h]
        dest.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(download_one, law, dest): law for law in laws}
            for fut in as_completed(futs):
                res = fut.result()
                counts[res["status"]] = counts.get(res["status"], 0) + 1
                if res["status"] == "fail":
                    fails.append(res)
        print(f"  [{h}] → {dest.name}: done ({len(laws)} laws)")
    print(f"\n=== SUMMARY ({time.time()-t0:.0f}s) ===")
    print(counts)
    for f in fails[:20]:
        print("  FAIL", f.get("id"), f.get("error"), str(f.get("url"))[:90])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
