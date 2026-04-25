"""Export untranslated laws to a Markdown file for Claude Code translation.

Usage:
    python -m crawler.export_pending                # all ministries
    python -m crawler.export_pending --ministry esdm
    python -m crawler.export_pending --limit 50

Output: data/pending/YYYY-MM-DD_<ministry|all>.md
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from . import db

PENDING_DIR = Path(__file__).resolve().parent.parent / "data" / "pending"

INSTRUCTIONS = """\
> Claude Code 번역 지시:
> 아래 표의 각 행을 한국어로 번역하여 다음 형식의 JSON 배열로 응답하라.
> 결과는 `translations/<이 파일과 같은 이름>.json` 으로 저장하면 된다.
>
> ```json
> [
>   {
>     "id": <id>,
>     "title_ko": "...",
>     "summary_ko": "...",
>     "categories": ["..."],
>     "keywords": ["..."]
>   }
> ]
> ```
>
> - title_ko: 법령 제목의 자연스러운 한국어 번역
> - summary_ko: 1~2문장의 핵심 요약 (없으면 빈 문자열)
> - categories: 분야 태그 (예: "에너지", "광물자원", "투자", "통관")
> - keywords: 검색 키워드 (3~7개)
> - 법령 종류 약어(UU/PP/Permen/Kepmen 등)는 한국어 표기 + 원어 약어 병기
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ministry", help="ministry_code filter (e.g. esdm)")
    ap.add_argument("--limit", type=int, default=200, help="max rows per file")
    args = ap.parse_args()

    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    with db.connect() as conn:
        rows = db.pending_translations(conn, args.ministry)

    if not rows:
        print("No pending translations.")
        return 0

    rows = rows[: args.limit]
    suffix = args.ministry or "all"
    out = PENDING_DIR / f"{date.today().isoformat()}_{suffix}.md"

    lines: list[str] = []
    lines.append(f"# 미번역 법령 — {suffix} ({len(rows)}건)")
    lines.append("")
    lines.append(INSTRUCTIONS)
    lines.append("")
    lines.append("| id | ministry | law_number | title_id | issuance_date | source_url |")
    lines.append("|----|----------|------------|----------|---------------|------------|")
    for r in rows:
        title = (r["title_id"] or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['id']} | {r['ministry_code']} | {r['law_number']} | {title} | "
            f"{r['issuance_date'] or ''} | {r['source_url']} |"
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(rows)} laws)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
