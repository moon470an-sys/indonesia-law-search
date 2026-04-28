"""Repair promulgation_date values across the laws DB.

Two phases:

Phase 1 — local quick wins (run anywhere, no network):
  * Drop epoch placeholders ("1970-01-01") to NULL.
  * Replace 21XX years (2104..2107) with 20XX where the law's `year`
    column confirms the typo offset.
  * Null out impossible future dates (>= 2027) where they conflict
    with the law's `year`.

Phase 2 — re-fetch every row's "Tanggal Penetapan" from source.
  * MUST run from a network that can reach the Indonesian gov sites
    (GitHub Actions, not Korea).
  * `--all` processes every row in every data/laws/*.jsonl. Default
    is suspect-only (NULL pd, epoch, or year mismatch).
  * Re-fetches the source_url in parallel (ThreadPoolExecutor) and
    extracts the first "Tanggal Penetapan: <DD MONTH YYYY>" match.
  * Writes corrections to data/fixed_promulgation_dates.jsonl keyed
    by source_url. Phase merge applies the patch back to JSONL.

Usage:
  python -X utf8 -m scripts.fix_promulgation_dates --phase 1
  python -X utf8 -m scripts.fix_promulgation_dates --phase 2 --all \
      --workers 16 --shard 0/16
  python -X utf8 -m scripts.fix_promulgation_dates --phase merge
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

# Indonesian regulation detail pages label the enactment date as
# "Tanggal Penetapan" (or "Ditetapkan: DD MONTH YYYY"); promulgation as
# "Tanggal Pengundangan" / "Diundangkan". We prefer Penetapan since the
# user explicitly asked for that label, falling back to Pengundangan.
PENETAPAN_RX = re.compile(
    r"(?:tanggal\s*)?(?:penetapan|ditetapkan)[^\d]{0,80}?(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    re.IGNORECASE,
)
PENGUNDANGAN_RX = re.compile(
    r"(?:tanggal\s*)?(?:pengundangan|diundangkan)[^\d]{0,80}?(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    re.IGNORECASE,
)
DATE_LABEL_RX = PENETAPAN_RX  # backward compat alias
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


def fetch_one(client: httpx.Client, row) -> dict | None:
    url = row["source_url"]
    if not url:
        return None
    try:
        r = client.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        # Prefer Penetapan; fall back to Pengundangan
        m = PENETAPAN_RX.search(text) or PENGUNDANGAN_RX.search(text)
        if not m:
            return None
        date = parse_indo_date(m.group(1))
        if not date:
            return None
        # Sanity bounds — ignore preposterous dates
        try:
            y = int(date[:4])
        except Exception:
            return None
        if y < 1945 or y > 2027:
            return None
        return {
            "id": row["id"],
            "source_url": url,
            "promulgation_date": date,
        }
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


def phase2(
    workers: int,
    shard: tuple[int, int] | None,
    *,
    fetch_all: bool = False,
) -> None:
    """Walk every data/laws/*.jsonl, optionally restricted to suspect
    rows, and emit a key=source_url patch."""
    src_dir = ROOT / "data" / "laws"
    rows: list[dict] = []
    for f in sorted(src_dir.glob("*.jsonl")):
        rows.extend(_load_jsonl(f))

    if fetch_all:
        candidates = [r for r in rows if r.get("source_url")]
    else:
        candidates = [r for r in rows if r.get("source_url") and _is_suspect(r)]

    if shard:
        i, n = shard
        candidates = [r for idx, r in enumerate(candidates) if idx % n == i]

    print(f"phase2 candidates: {len(candidates)}/{len(rows)} "
          f"(fetch_all={fetch_all}, workers={workers}, shard={shard})",
          flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_fp = OUT_PATH.open("a", encoding="utf-8")

    headers = {"User-Agent": "jdih-fixer/1.0 (+github-actions)"}
    started = time.time()
    fixed = 0
    with httpx.Client(headers=headers, http2=True) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_one, client, r): r["source_url"]
                       for r in candidates}
            for i, fut in enumerate(as_completed(futures), 1):
                res = fut.result()
                if res:
                    fixed += 1
                    out_fp.write(json.dumps(res, ensure_ascii=False) + "\n")
                    out_fp.flush()
                if i % 200 == 0:
                    print(f"  {i}/{len(candidates)} processed, {fixed} fixed, "
                          f"{time.time()-started:.0f}s elapsed", flush=True)
    out_fp.close()
    print(f"done: {fixed}/{len(candidates)} fixed → {OUT_PATH}")


# ---------- merge phase 2 results back into DB ----------

def merge() -> None:
    """Apply patch (keyed by source_url) back to every JSONL file."""
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

    grand = 0
    for src_path in sorted((ROOT / "data" / "laws").glob("*.jsonl")):
        rows = _load_jsonl(src_path)
        n = 0
        for r in rows:
            new = patch.get(r.get("source_url"))
            if new and r.get("promulgation_date") != new:
                r["promulgation_date"] = new
                n += 1
        if n:
            tmp = src_path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fp:
                for r in rows:
                    fp.write(json.dumps(r, ensure_ascii=False) + "\n")
            tmp.replace(src_path)
            print(f"  {src_path.name}: {n} rows updated")
            grand += n
    print(f"merged: {grand} rows updated across all sources")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["1", "2", "merge"], required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--shard", default=None,
                    help="i/n — only process row indexes where idx%%n == i")
    ap.add_argument("--all", action="store_true",
                    help="phase 2: re-fetch every row, not just suspects")
    args = ap.parse_args()

    if args.phase == "1":
        phase1()
    elif args.phase == "2":
        shard = None
        if args.shard:
            a, b = args.shard.split("/")
            shard = (int(a), int(b))
        phase2(args.workers, shard, fetch_all=args.all)
    else:
        merge()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
