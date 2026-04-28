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
from email.message import EmailMessage
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


def format_summary(summary: dict | None, step_logs: list[str]) -> tuple[str, str]:
    """Returns (subject, body)."""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    if summary:
        total_new = summary.get("total_new", 0)
        ministries = summary.get("ministries", {}) or {}
        rows = []
        for name, info in ministries.items():
            err = info.get("error")
            if err:
                rows.append(f"  - {name}: ERROR — {err[:120]}")
            else:
                rows.append(
                    f"  - {name} ({info.get('ministry_code', '?')}): "
                    f"new={info.get('new_in_db', 0)}, chunks={len(info.get('chunk_files', []))}"
                )
        bucket_lines = "\n".join(rows) if rows else "  (no ministries reported)"
        subject = f"[JDIH 일일 크롤] {now} — +{total_new} 건"
        body = (
            f"## 인도네시아 법령 일일 업데이트\n"
            f"실행 시각: {now}\n"
            f"신규 미번역: {total_new} 건\n\n"
            f"### 부처별 결과\n{bucket_lines}\n\n"
            f"### 다음 단계\n"
            f"신규 행이 있다면 Claude Code 채팅에서 `/translate-pending` 으로 번역하세요.\n\n"
            f"---\n### 실행 로그\n" + "\n\n".join(step_logs)
        )
    else:
        subject = f"[JDIH 일일 크롤] {now} — 요약 파일 없음"
        body = (
            f"## 인도네시아 법령 일일 업데이트 (요약 누락)\n"
            f"실행 시각: {now}\n"
            f"data/pending/today.summary.json 이 생성되지 않았습니다.\n\n"
            f"---\n### 실행 로그\n" + "\n\n".join(step_logs)
        )
    return subject, body


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
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
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
