"""Daily incremental update + email summary, run on the local Windows host
via Task Scheduler at 09:00 KST.

Pipeline (each step is non-fatal so a partial failure still emails):
  1. git pull --rebase                                    — sync DB latest
  2. python -m crawler.update_all                         — crawl + chunk pending
  3. (optional) python -m crawler.build_db                — rebuild laws.db
  4. git add data/laws data/pending/today.summary.json
     git commit -m "chore(daily): KST YYYY-MM-DD"
     git push                                             — publish snapshot
  5. Send email summary to JDIH_EMAIL_TO

The email contains the per-source delta, total new pending rows, any
exceptions, and a reminder if rows still need translation. Translation
itself stays manual (see CLAUDE.md — no external translation API).

Required environment variables (set once via Task Scheduler "Edit Action
> Environment" or in the user's permanent env):
  JDIH_EMAIL_FROM      — sender address (e.g. moon470an@gmail.com)
  JDIH_EMAIL_TO        — recipient (default yoonseok.moon@sticorp.co.kr)
  JDIH_SMTP_HOST       — e.g. smtp.gmail.com
  JDIH_SMTP_PORT       — 587 for STARTTLS, 465 for SSL
  JDIH_SMTP_USER       — SMTP login (often same as FROM)
  JDIH_SMTP_PASSWORD   — app password / SMTP token

If SMTP env is missing the script logs the would-be email body to
data/pending/last_daily_log.txt and exits 0 (so the task scheduler
shows a green run for monitoring).

Usage:
  python -m scripts.daily_update [--no-git] [--no-email] [--keys esdm bnn]
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import subprocess
import sys
import traceback
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "data" / "pending" / "today.summary.json"
LOG_PATH = ROOT / "data" / "pending" / "last_daily_log.txt"
KST = timezone(timedelta(hours=9))


def run(cmd: list[str], *, cwd: Path = ROOT, check: bool = True) -> tuple[int, str]:
    """Run a subprocess, capture combined stdout/stderr, return (code, output)."""
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} exit {proc.returncode}\n{out[-2000:]}")
    return proc.returncode, out


def git_pull() -> str:
    code, out = run(["git", "pull", "--rebase", "origin", "main"], check=False)
    return f"git pull (exit {code})\n{out.strip()}"


def crawler_update(keys: list[str]) -> str:
    cmd = [sys.executable, "-m", "crawler.update_all"] + keys
    code, out = run(cmd, check=False)
    return f"crawler.update_all (exit {code})\n{out[-3000:].strip()}"


def build_db() -> str:
    code, out = run([sys.executable, "-m", "crawler.build_db"], check=False)
    return f"crawler.build_db (exit {code})\n{out[-1500:].strip()}"


def git_commit_push(date_label: str) -> str:
    parts = []
    code, out = run(
        ["git", "add", "data/laws", "data/pending/today.summary.json", "data/pending/chunks"],
        check=False,
    )
    parts.append(f"git add (exit {code})\n{out.strip()}")
    code, out = run(["git", "diff", "--cached", "--quiet"], check=False)
    if code == 0:
        parts.append("nothing staged — nothing to commit")
        return "\n\n".join(parts)
    code, out = run(
        ["git", "commit", "-m", f"chore(daily-local): KST {date_label}"], check=False,
    )
    parts.append(f"git commit (exit {code})\n{out.strip()}")
    code, out = run(["git", "push", "origin", "main"], check=False)
    parts.append(f"git push (exit {code})\n{out.strip()}")
    return "\n\n".join(parts)


def read_summary() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None
    try:
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def fetch_new_laws(limit: int = 30) -> list[dict]:
    """Pull the rows newly added in the just-finished crawl from the DB.

    "Newly added" = highest ids; the crawler only inserts new rows with
    AUTOINCREMENT ids, so the last batch always sits at the tail.
    """
    try:
        import sqlite3
        from crawler.db import DB_PATH
        if not DB_PATH.exists():
            return []
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, source, law_type, law_number, year, title_id, title_ko,
                   summary_ko, ministry_name_ko, promulgation_date, source_url
            FROM laws
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


SITE_URL = "https://moon470an-sys.github.io/indonesia-law-search"


def format_law_block(law: dict) -> str:
    """One readable Korean block per law. Falls back to Indonesian title
    when the Korean translation hasn't been produced yet (translation is
    manual via Claude Code chat per CLAUDE.md)."""
    nomor = (law.get("law_number") or "").strip()
    year = law.get("year") or ""
    type_label = (law.get("law_type") or "").strip()
    ministry = (law.get("ministry_name_ko") or "").strip()
    promulgation = (law.get("promulgation_date") or "").strip()
    title_ko = (law.get("title_ko") or "").strip()
    title_id = (law.get("title_id") or "").strip()
    summary_ko = (law.get("summary_ko") or "").strip()

    headline_parts = [type_label] if type_label else []
    if nomor:
        headline_parts.append(f"제{nomor}호")
    if year:
        headline_parts.append(f"({year})")
    headline = " ".join(headline_parts) or "(법령 정보)"

    detail_link = f"{SITE_URL}/laws/{law['id']}/"

    lines = [f"### {headline}"]
    if ministry:
        lines.append(f"  - 소관: {ministry}")
    if promulgation:
        lines.append(f"  - 공포일: {promulgation}")
    if title_ko:
        lines.append(f"  - 제목: {title_ko}")
    elif title_id:
        lines.append(f"  - 제목(인니어): {title_id[:200]}")
        lines.append("  - (한국어 번역 대기 중 — `/translate-pending` 실행 후 반영)")
    if summary_ko:
        lines.append(f"  - 요약: {summary_ko}")
    lines.append(f"  - 상세: {detail_link}")
    return "\n".join(lines)


def format_summary(summary: dict | None, step_logs: list[str]) -> tuple[str, str]:
    """Returns (subject, body). Email focuses on the actual newly-enacted
    laws rather than crawl pipeline statistics."""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    today_label = datetime.now(KST).strftime("%Y-%m-%d")
    total_new = (summary or {}).get("total_new", 0) or 0

    if summary is None:
        subject = f"[인도네시아 법령] {today_label} — 업데이트 정보 없음"
        body = (
            f"## 인도네시아 법령 일일 업데이트\n"
            f"실행 시각: {now}\n\n"
            f"오늘 새로 추가된 법령이 없거나 크롤 요약 파일이 생성되지 않았습니다.\n\n"
            f"사이트: {SITE_URL}/search\n\n"
            f"---\n### 실행 로그\n" + "\n\n".join(step_logs)
        )
        return subject, body

    if total_new == 0:
        subject = f"[인도네시아 법령] {today_label} — 신규 제정 법령 없음"
        body = (
            f"## 인도네시아 법령 일일 업데이트\n"
            f"실행 시각: {now}\n\n"
            f"오늘 새로 추가된 법령이 없습니다. 등록된 부처 사이트(peraturan.go.id, "
            f"jdih.esdm 등)를 점검했지만 신규 항목이 발견되지 않았습니다.\n\n"
            f"기존 법령 검색: {SITE_URL}/search\n"
        )
        return subject, body

    new_laws = fetch_new_laws(limit=min(30, total_new))
    if not new_laws:
        subject = f"[인도네시아 법령] {today_label} — 신규 {total_new}건 (DB 조회 실패)"
        body = (
            f"## 인도네시아 법령 일일 업데이트\n"
            f"실행 시각: {now}\n"
            f"신규 추가: {total_new} 건\n\n"
            f"DB 조회에 실패해 개별 법령 정보를 표시하지 못했습니다. "
            f"사이트({SITE_URL}/search)에서 직접 확인해주세요.\n\n"
            f"---\n### 실행 로그\n" + "\n\n".join(step_logs)
        )
        return subject, body

    # Headline highlight = first item's type + number
    first = new_laws[0]
    first_label = (first.get("law_type") or "").strip()
    first_no = (first.get("law_number") or "").strip()
    headline = f"{first_label} 제{first_no}호" if first_label and first_no else f"{total_new}건"
    if total_new > 1:
        subject = f"[인도네시아 법령] {today_label} — 신규 {total_new}건 ({headline} 외)"
    else:
        subject = f"[인도네시아 법령] {today_label} — 신규 {headline}"

    blocks = [format_law_block(law) for law in new_laws]
    untranslated = sum(1 for law in new_laws if not (law.get("title_ko") or "").strip())

    body_parts = [
        f"## 인도네시아 법령 일일 업데이트",
        f"실행 시각: {now}",
        f"신규 제정·수집된 법령: {total_new} 건"
        + (f" (이메일에는 최근 {len(new_laws)}건 표시)" if total_new > len(new_laws) else ""),
        "",
    ]
    if untranslated > 0:
        body_parts.append(
            f"※ 이 중 {untranslated}건은 인니어 원제만 수집된 상태입니다. "
            f"Claude Code 채팅에서 `/translate-pending` 실행 시 한국어 제목·요약이 적용되어 "
            f"사이트에 반영됩니다."
        )
        body_parts.append("")
    body_parts.append("---")
    body_parts.append("")
    body_parts.extend(blocks)
    body_parts.append("")
    body_parts.append("---")
    body_parts.append(f"전체 검색 페이지: {SITE_URL}/search")
    return subject, "\n".join(body_parts)


def send_email(subject: str, body: str) -> str:
    host = os.environ.get("JDIH_SMTP_HOST")
    port = int(os.environ.get("JDIH_SMTP_PORT", "587"))
    user = os.environ.get("JDIH_SMTP_USER")
    password = os.environ.get("JDIH_SMTP_PASSWORD")
    sender = os.environ.get("JDIH_EMAIL_FROM", user or "")
    recipient = os.environ.get("JDIH_EMAIL_TO", "yoonseok.moon@sticorp.co.kr")
    if not (host and user and password and sender):
        return (
            "SMTP env vars missing (JDIH_SMTP_HOST/USER/PASSWORD/EMAIL_FROM) — "
            f"would have emailed:\nTo: {recipient}\nSubject: {subject}\n\n{body[:1500]}"
        )
    # Manual MIME assembly: every header value is base64-encoded for safety
    # and the body is base64-encoded UTF-8. This avoids smtplib's habit of
    # re-encoding headers as ASCII when send_message() walks the message.
    import base64
    enc_subject = "=?utf-8?b?" + base64.b64encode(subject.encode("utf-8")).decode("ascii") + "?="
    enc_body = base64.b64encode(body.encode("utf-8")).decode("ascii")
    raw = (
        f"From: {sender}\r\n"
        f"To: {recipient}\r\n"
        f"Subject: {enc_subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Transfer-Encoding: base64\r\n"
        f"\r\n"
        f"{enc_body}\r\n"
    ).encode("ascii")
    ctx = ssl.create_default_context()
    # Force an ASCII local hostname for EHLO. Python defaults to socket.gethostname()
    # which on this Windows host returns Korean ("문윤석"), and smtplib tries to
    # ASCII-encode it on the wire — UnicodeEncodeError otherwise.
    local_hostname = "jdih-daily.local"
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30,
                              local_hostname=local_hostname) as s:
            s.login(user, password)
            s.sendmail(sender, [recipient], raw)
    else:
        with smtplib.SMTP(host, port, timeout=30, local_hostname=local_hostname) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(user, password)
            s.sendmail(sender, [recipient], raw)
    return f"sent to {recipient} via {host}:{port}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true", help="skip git pull/push")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--keys", nargs="*", default=[], help="ministry keys (default: all)")
    args = ap.parse_args()

    step_logs: list[str] = []
    today_kst = datetime.now(KST).strftime("%Y-%m-%d")
    try:
        if not args.no_git:
            step_logs.append(git_pull())
        step_logs.append(crawler_update(args.keys))
        step_logs.append(build_db())
        if not args.no_git:
            step_logs.append(git_commit_push(today_kst))
    except Exception as e:
        step_logs.append("UNEXPECTED EXCEPTION:\n" + "".join(traceback.format_exc())[-2000:])

    summary = read_summary()
    subject, body = format_summary(summary, step_logs)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(f"# {subject}\n\n{body}\n", encoding="utf-8")

    if args.no_email:
        print(f"[no-email] subject={subject}")
        print(body[:1500])
    else:
        try:
            result = send_email(subject, body)
            print(f"[email] {result}")
        except Exception as e:
            print(f"[email] FAILED: {e}", file=sys.stderr)
            (LOG_PATH.parent / "last_daily_email_error.txt").write_text(
                f"{e}\n\n{traceback.format_exc()}", encoding="utf-8",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
