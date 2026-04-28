"""Repair promulgation_date values across the laws DB.

Two phases:

Phase 1 — local quick wins (run anywhere, no network):
  * Drop epoch placeholders ("1970-01-01") to NULL.
  * Replace 21XX years (2104..2107) with 20XX where the law's `year`
    column confirms the typo offset.
  * Null out impossible future dates (>= 2027) where they conflict
    with the law's `year`.

Phase 2 — re-fetch from peraturan.go.id (must run from a network that
can reach the Indonesian gov sites — GitHub Actions, not Korea).
  * Pulls every row whose pd-year still mismatches `year` or is NULL.
  * Re-fetches the source_url in parallel (ThreadPoolExecutor, 16 workers).
  * Re-extracts promulgation_date from the detail page.
  * Writes corrections to data/fixed_promulgation_dates.jsonl as a
    side-channel for downstream merge into the JSONL source-of-truth.

Usage:
  python -X utf8 -m scripts.fix_promulgation_dates --phase 1
  python -X utf8 -m scripts.fix_promulgation_dates --phase 2 --workers 16 --shard 0/4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crawler.db import DB_PATH  # noqa: E402

OUT_PATH = ROOT / "data" / "fixed_promulgation_dates.jsonl"
EPOCH = "1970-01-01"


# ---------- phase 1 ----------

def phase1() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    epoch_cnt = cur.execute(
        "UPDATE laws SET promulgation_date = NULL WHERE promulgation_date = ?",
        (EPOCH,),
    ).rowcount
    print(f"epoch→NULL: {epoch_cnt}")

    # 21XX → 20XX where year matches the 20XX form
    rows = cur.execute(
        """
        SELECT id, year, promulgation_date
        FROM laws
        WHERE substr(promulgation_date,1,2) = '21'
        """
    ).fetchall()
    fixed = 0
    for r in rows:
        new_date = "20" + r["promulgation_date"][2:]
        if r["year"] is None or int(new_date[:4]) == r["year"]:
            cur.execute(
                "UPDATE laws SET promulgation_date = ? WHERE id = ?",
                (new_date, r["id"]),
            )
            fixed += 1
    print(f"21XX→20XX: {fixed}")

    # Future-year mismatches: clear the obviously bogus pd
    bogus = cur.execute(
        """
        UPDATE laws SET promulgation_date = NULL
        WHERE promulgation_date IS NOT NULL
          AND year IS NOT NULL
          AND CAST(substr(promulgation_date,1,4) AS INTEGER) >= 2027
          AND CAST(substr(promulgation_date,1,4) AS INTEGER) <> year
        """
    ).rowcount
    print(f"future-year cleared: {bogus}")

    # Year-2036 anomaly tied to 1950s-era laws (pd off by exactly 80 yrs)
    s_2036 = cur.execute(
        "SELECT id, year, promulgation_date FROM laws WHERE substr(promulgation_date,1,4) = '2036'"
    ).fetchall()
    nulled = 0
    for r in s_2036:
        if r["year"] is None or r["year"] < 2000:
            cur.execute(
                "UPDATE laws SET promulgation_date = NULL WHERE id = ?", (r["id"],)
            )
            nulled += 1
    print(f"2036 anomaly cleared: {nulled}")

    conn.commit()
    conn.close()


# ---------- phase 2 ----------

DATE_LABEL_RX = re.compile(
    r"(?:tanggal\s*)?(?:penetapan|pengundangan|ditetapkan|diundangkan)\b[\s\S]{0,120}?(\d{1,2}\s+\w+\s+\d{4})",
    re.IGNORECASE,
)
INDO_MONTH = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "mei.": "05",
    "jun": "06", "jul": "07", "agu": "08", "sep": "09", "okt": "10",
    "nov": "11", "des": "12",
}


def parse_indo_date(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if not m:
        return None
    day, month, year = m.group(1), m.group(2).lower(), m.group(3)
    mm = INDO_MONTH.get(month)
    if not mm:
        return None
    return f"{year}-{mm}-{day.zfill(2)}"


def fetch_one(client: httpx.Client, row: sqlite3.Row) -> dict | None:
    url = row["source_url"]
    if not url or "peraturan.go.id" not in url:
        return None
    try:
        r = client.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        m = DATE_LABEL_RX.search(text)
        if not m:
            return None
        date = parse_indo_date(m.group(1))
        if not date:
            return None
        return {"id": row["id"], "promulgation_date": date, "source_url": url}
    except Exception:
        return None


def _is_suspect(row: dict, today_year: int = 2026) -> bool:
    pd = row.get("promulgation_date")
    yr = row.get("year")
    if not pd:
        return True
    if pd == EPOCH:
        return True
    try:
        pd_year = int(pd[:4])
    except Exception:
        return True
    if pd_year > today_year + 1:
        return True
    if yr and pd_year != yr:
        return True
    return False


def _load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def phase2(workers: int, shard: tuple[int, int] | None) -> None:
    """Operate on data/laws/peraturan_go_id.jsonl (source of truth) and
    emit a key=source_url patch to data/fixed_promulgation_dates.jsonl.
    Merge phase rewrites the JSONL in place."""
    src_path = ROOT / "data" / "laws" / "peraturan_go_id.jsonl"
    rows = _load_jsonl(src_path)
    suspect = [r for r in rows if _is_suspect(r)]

    if shard:
        i, n = shard
        suspect = [r for idx, r in enumerate(suspect) if idx % n == i]

    print(f"phase2 candidates: {len(suspect)}/{len(rows)} "
          f"(workers={workers}, shard={shard})", flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_fp = OUT_PATH.open("a", encoding="utf-8")

    class _Row:
        def __init__(self, d):
            self._d = d

        def __getitem__(self, k):
            return self._d.get(k)

    headers = {"User-Agent": "jdih-fixer/1.0 (+github-actions)"}
    started = time.time()
    fixed = 0
    with httpx.Client(headers=headers, http2=True) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_one, client, _Row(r)): r["source_url"]
                       for r in suspect}
            for i, fut in enumerate(as_completed(futures), 1):
                res = fut.result()
                if res:
                    fixed += 1
                    out_fp.write(json.dumps(res, ensure_ascii=False) + "\n")
                    out_fp.flush()
                if i % 100 == 0:
                    print(f"  {i}/{len(suspect)} processed, {fixed} fixed, "
                          f"{time.time()-started:.0f}s elapsed", flush=True)
    out_fp.close()
    print(f"done: {fixed}/{len(suspect)} fixed → {OUT_PATH}")


# ---------- merge phase 2 results back into DB ----------

def merge() -> None:
    """Apply patch (keyed by source_url) back to JSONL source-of-truth."""
    if not OUT_PATH.exists():
        print("no fixed_promulgation_dates.jsonl to merge")
        return
    patch: dict[str, str] = {}
    with OUT_PATH.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            patch[rec["source_url"]] = rec["promulgation_date"]
    if not patch:
        print("empty patch")
        return

    src_path = ROOT / "data" / "laws" / "peraturan_go_id.jsonl"
    rows = _load_jsonl(src_path)
    n = 0
    for r in rows:
        new = patch.get(r.get("source_url"))
        if new and r.get("promulgation_date") != new:
            r["promulgation_date"] = new
            n += 1
    tmp = src_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(src_path)
    print(f"merged: {n} rows updated in {src_path.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["1", "2", "merge"], required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--shard", default=None,
                    help="i/n — only process row indexes where idx%%n == i")
    args = ap.parse_args()

    if args.phase == "1":
        phase1()
    elif args.phase == "2":
        shard = None
        if args.shard:
            a, b = args.shard.split("/")
            shard = (int(a), int(b))
        phase2(args.workers, shard)
    else:
        merge()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
