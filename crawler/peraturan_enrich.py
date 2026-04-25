"""peraturan.go.id detail-page enricher.

For each law row already in the DB (filtered by hierarchy), fetches its
detail page and extracts:

  • enactment_date    (Tanggal Penetapan)
  • promulgation_date (Tanggal Pengundangan)
  • status            (Berlaku / Diubah / Dicabut)
  • relasi[]          (related law slug URLs)

Writes one JSONL line per law to data/enrich/<hierarchy>.jsonl. A separate
import step (crawler.import_enrich) merges these fields into the DB.

Concurrency-friendly httpx async, per-section deadline, --probe-only mode for
selector discovery.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("peraturan_enrich")


BASE = "https://peraturan.go.id"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 jdih-enrich/0.1"
)

# Indonesian month names → 2-digit
MONTHS = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei":     "05", "juni":      "06", "juli":  "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
}

DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
SLUG_PREFIX_RE = re.compile(r"^([a-z]+)", re.IGNORECASE)

# slug prefix → hierarchy classification (matches scripts/assign_ministries.py logic)
HIERARCHY_PREFIXES: dict[str, set[str]] = {
    "uu":      {"uu", "perppu"},
    "pp":      {"pp"},
    "perpres": {"perpres"},
    "permen":  {
        "permen", "permenkeu", "permenhub", "permendag", "permenhut", "permentan",
        "permenkes", "permenag", "permenkum", "permenkumham", "permensos",
        "permenkop", "permenpera", "permenpkp", "permenpu", "permenkkp",
        "permenpar", "permenkominfo", "permenkomdigi", "permenperin",
        "permendikdasmen", "permenkebud", "permenpan", "permenpanrb",
        "permenkoinfra", "permenpppa", "permenppn", "permenmubpn",
        "permendagri", "permendikbud", "permendikbudristek", "permendiknas",
        "permendiktisaintek", "permenristekdikti", "permenristek", "permenhan",
        "permenaker", "permenakertrans", "permendesa", "permendespdt",
        "permenlu", "permenlh", "permenklhbph", "permenpora", "permenparekraf",
        "permenbudpar", "permensetneg", "permenimipas", "permenham",
        "permenko",
    },
    "kepmen":  {"kepmen"},
    "perda":   {"perda", "pergub", "perwako", "perwalkot", "perwali", "perbup"},
}


def parse_date_id(text: str) -> str | None:
    """Return ISO yyyy-mm-dd or None."""
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    mon = MONTHS.get(m.group(2).lower())
    year = m.group(3)
    if not mon:
        return None
    return f"{year}-{mon}-{day:02d}"


def select_hierarchy_rows(db_path: Path, hierarchy: str, limit: int) -> list[tuple[int, str]]:
    """Return (id, source_url) rows belonging to the given hierarchy bucket."""
    prefixes = HIERARCHY_PREFIXES.get(hierarchy)
    if not prefixes:
        log.error("unknown hierarchy: %s", hierarchy)
        return []
    placeholders = ",".join(["?"] * len(prefixes))
    # We extract slug prefix in SQL — use a subquery with INSTR for portability.
    # Simpler: fetch all peraturan_go_id rows then filter in Python.
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT id, source_url FROM laws WHERE source = 'peraturan_go_id'"
    ).fetchall()
    con.close()

    out: list[tuple[int, str]] = []
    for row_id, url in rows:
        # /id/<prefix>-... pattern
        path_part = url.split("peraturan.go.id", 1)[-1]
        m = re.match(r"^/id/([a-z]+)", path_part, re.IGNORECASE)
        if not m:
            continue
        if m.group(1).lower() in prefixes:
            out.append((row_id, url))
    if limit > 0:
        out = out[:limit]
    return out


async def fetch(client: httpx.AsyncClient, url: str, retries: int = 2) -> str | None:
    for attempt in range(retries):
        try:
            r = await client.get(url, timeout=15)
            if r.status_code == 200:
                return r.text
            if 500 <= r.status_code < 600:
                await asyncio.sleep(1 + attempt)
                continue
            return None
        except (httpx.RequestError, httpx.HTTPError):
            await asyncio.sleep(1 + attempt)
    return None


def parse_detail(html: str) -> dict:
    """Extract enrichment fields from a peraturan.go.id detail page."""
    soup = BeautifulSoup(html, "lxml")
    out: dict = {}

    # 1) Tanggal Penetapan / Pengundangan — usually in ul.info_booking or
    #    table.detail or a dl block. We try multiple structures.
    text_blob = soup.get_text("\n", strip=True)

    # ul.info_booking li → "<strong>Tanggal Penetapan</strong>19 September 2026"
    for li in soup.select("ul.info_booking li"):
        label = li.find("strong")
        if not label:
            continue
        key = label.get_text(strip=True).lower()
        val = li.get_text(" ", strip=True)
        # remove the label portion
        val = val.replace(label.get_text(strip=True), "", 1).strip()
        if "penetapan" in key:
            out["enactment_date"] = parse_date_id(val) or out.get("enactment_date")
        elif "pengundangan" in key:
            out["promulgation_date"] = parse_date_id(val) or out.get("promulgation_date")

    # Fallback: regex over plain text for "Tanggal Penetapan ... 19 September 2025"
    if "enactment_date" not in out:
        m = re.search(r"Tanggal\s+Penetapan[^\d]*(\d{1,2}\s+\w+\s+\d{4})", text_blob, re.IGNORECASE)
        if m:
            out["enactment_date"] = parse_date_id(m.group(1))
    if "promulgation_date" not in out:
        m = re.search(r"Tanggal\s+Pengundangan[^\d]*(\d{1,2}\s+\w+\s+\d{4})", text_blob, re.IGNORECASE)
        if m:
            out["promulgation_date"] = parse_date_id(m.group(1))

    # 2) Status — look for a badge / explicit "Status" row
    m = re.search(r"Status[^A-Za-z]*([A-Za-z]+)", text_blob)
    if m:
        word = m.group(1).lower()
        if word.startswith("berlaku"):
            out["status"] = "berlaku"
        elif word.startswith("diubah"):
            out["status"] = "diubah"
        elif word.startswith("dicabut"):
            out["status"] = "dicabut"

    # 3) Relasi — collect detail-style anchors that aren't the page itself.
    relasi: list[str] = []
    self_href = None
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        self_href = canonical["href"].rstrip("/")

    for a in soup.select('a[href^="/id/"]'):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full = BASE + href
        if self_href and full.rstrip("/") == self_href:
            continue
        if full not in relasi:
            relasi.append(full)
    if relasi:
        out["relasi"] = relasi[:50]

    return out


async def enrich_hierarchy(
    db_path: Path,
    hierarchy: str,
    out_path: Path,
    *,
    concurrency: int,
    deadline_seconds: int,
    limit: int,
) -> int:
    rows = select_hierarchy_rows(db_path, hierarchy, limit)
    log.info("[%s] %d rows to enrich", hierarchy, len(rows))
    if not rows:
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    sem = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9"}
    written = 0
    start = time.monotonic()
    progress_every = max(50, len(rows) // 40)

    async with httpx.AsyncClient(
        headers=headers, http2=True, follow_redirects=True, timeout=15,
        limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
    ) as client:
        async def go(rid: int, url: str) -> dict | None:
            async with sem:
                html = await fetch(client, url)
                if html is None:
                    return None
                fields = parse_detail(html)
                if not fields:
                    return None
                return {"id": rid, **fields}

        with out_path.open("w", encoding="utf-8") as f:
            tasks = [asyncio.create_task(go(rid, url)) for rid, url in rows]
            for done_ix, fut in enumerate(asyncio.as_completed(tasks), 1):
                if time.monotonic() - start > deadline_seconds:
                    log.warning("[%s] deadline reached at %d/%d", hierarchy, done_ix, len(rows))
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break
                try:
                    res = await fut
                except asyncio.CancelledError:
                    continue
                if res:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                    written += 1
                if done_ix % progress_every == 0:
                    log.info("[%s] %d/%d done (%d enriched)", hierarchy, done_ix, len(rows), written)

    log.info("[%s] enriched %d of %d rows → %s", hierarchy, written, len(rows), out_path)
    return written


async def amain(targets: Iterable[str], db_path: Path, out_dir: Path,
                concurrency: int, deadline: int, limit: int) -> int:
    for h in targets:
        await enrich_hierarchy(
            db_path, h, out_dir / f"{h}.jsonl",
            concurrency=concurrency, deadline_seconds=deadline, limit=limit,
        )
    return 0


def probe_main(args) -> int:
    """Fetch a few detail URLs and dump parsed fields + a snippet of HTML for selector tuning."""
    rows = select_hierarchy_rows(Path(args.db), args.hierarchy, args.probe)
    print(f"=== probing {len(rows)} {args.hierarchy} rows ===")
    headers = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9"}

    async def go() -> None:
        async with httpx.AsyncClient(headers=headers, http2=True, follow_redirects=True, timeout=15) as c:
            for rid, url in rows:
                print(f"\n--- id={rid} {url} ---")
                html = await fetch(c, url)
                if html is None:
                    print("  fetch failed")
                    continue
                fields = parse_detail(html)
                print(f"  parsed: {json.dumps(fields, ensure_ascii=False)}")
                soup = BeautifulSoup(html, "lxml")
                for sel in ("ul.info_booking", "table.detail", "dl.detail-list",
                            "div.law-meta", "div.detail", "section.detail"):
                    nodes = soup.select(sel)
                    if nodes:
                        print(f"  selector hit: {sel} (n={len(nodes)})")
                        print(f"    snippet: {nodes[0].get_text(' ', strip=True)[:300]}")

    asyncio.run(go())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=[],
                    help="hierarchy slugs (uu/pp/perpres/permen/kepmen/perda)")
    ap.add_argument("--db", default="data/laws.db")
    ap.add_argument("--out-dir", default="data/enrich")
    ap.add_argument("--concurrency", type=int, default=15)
    ap.add_argument("--deadline-seconds", type=int, default=1500)
    ap.add_argument("--limit", type=int, default=0, help="max rows per hierarchy (0 = all)")
    ap.add_argument("--probe", type=int, default=0,
                    help="probe mode — fetch this many rows of the first target and dump")
    ap.add_argument("--hierarchy", default="uu", help="probe target hierarchy")
    args = ap.parse_args()

    if args.probe > 0:
        return probe_main(args)

    if not args.targets:
        ap.error("provide at least one hierarchy or use --probe")

    return asyncio.run(amain(
        args.targets, Path(args.db), Path(args.out_dir),
        args.concurrency, args.deadline_seconds, args.limit,
    ))


if __name__ == "__main__":
    sys.exit(main())
