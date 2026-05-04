"""Auto-translate today's pending chunks via Claude Code, then commit + push.

Runs as a follow-up to scripts/daily_update.py (the 09:00 KST crawl).

Pipeline:
  1. Read data/pending/today.summary.json. If chunk_files empty → exit 0.
  2. Run `claude -p "/translate-pending" --dangerously-skip-permissions`
     in the project root. The slash command writes translations/<chunk>.json
     for each pending chunk.
  3. Verify each chunk_file has a matching translations/<basename>.json.
     If any are missing, fail loudly and email the user.
  4. python -m crawler.import_all_translations
  5. python -m crawler.build_db
  6. git add translations data/laws data/pending
     git commit -m "chore(daily-translate): KST YYYY-MM-DD"
     git push
  7. Append result to data/pending/last_translate_log.txt and email summary.

Usage:
  python -m scripts.daily_translate              # full run, with git + email
  python -m scripts.daily_translate --no-git
  python -m scripts.daily_translate --no-email
  python -m scripts.daily_translate --dry-run    # show what would happen
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "data" / "pending" / "today.summary.json"
LOG_PATH = ROOT / "data" / "pending" / "last_translate_log.txt"
TRANSLATIONS_DIR = ROOT / "translations"
KST = timezone(timedelta(hours=9))

# Resolve Claude Code CLI. Task Scheduler runs without the user's PATH, so
# point at the absolute path we know exists on this host. Fallback to PATH.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or str(
    Path.home() / ".local" / "bin" / "claude.exe"
)
if not Path(CLAUDE_BIN).exists():
    CLAUDE_BIN = "claude"


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int | None = None,
        check: bool = True) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} exit {proc.returncode}\n{out[-2000:]}")
    return proc.returncode, out


def read_summary() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None
    try:
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def chunk_paths(summary: dict) -> list[Path]:
    """Resolve chunk_files entries to absolute Paths, filtering out missing."""
    out: list[Path] = []
    for s in summary.get("chunk_files") or []:
        # Stored with backslashes on Windows; normalize.
        p = ROOT / Path(str(s).replace("\\", "/"))
        if p.exists() and p.stat().st_size > 0:
            out.append(p)
    return out


def expected_translation_path(chunk: Path) -> Path:
    return TRANSLATIONS_DIR / chunk.name


def already_translated(chunks: list[Path]) -> tuple[list[Path], list[Path]]:
    """Split chunks into (need_translation, already_done) by checking
    translations/<basename>.json existence + non-empty + length match."""
    need: list[Path] = []
    done: list[Path] = []
    for chunk in chunks:
        out = expected_translation_path(chunk)
        if not out.exists() or out.stat().st_size == 0:
            need.append(chunk)
            continue
        try:
            in_data = json.loads(chunk.read_text(encoding="utf-8"))
            out_data = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            need.append(chunk)
            continue
        if not isinstance(out_data, list) or len(out_data) < len(in_data):
            need.append(chunk)
        else:
            done.append(chunk)
    return need, done


def run_claude_translate(timeout_minutes: int = 60) -> str:
    """Invoke Claude Code in headless mode to run /translate-pending."""
    cmd = [
        CLAUDE_BIN,
        "-p", "/translate-pending",
        "--dangerously-skip-permissions",
        "--output-format", "text",
    ]
    code, out = run(cmd, timeout=timeout_minutes * 60, check=False)
    return f"claude (exit {code})\n{out[-4000:].strip()}"


def import_translations() -> str:
    code, out = run(
        [sys.executable, "-X", "utf8", "-m", "crawler.import_all_translations"],
        check=False,
    )
    return f"crawler.import_all_translations (exit {code})\n{out[-1500:].strip()}"


def build_db() -> str:
    code, out = run(
        [sys.executable, "-X", "utf8", "-m", "crawler.build_db"],
        check=False,
    )
    return f"crawler.build_db (exit {code})\n{out[-1500:].strip()}"


def git_commit_push(date_label: str) -> str:
    parts = []
    code, out = run(
        ["git", "add", "translations", "data/laws", "data/pending"],
        check=False,
    )
    parts.append(f"git add (exit {code})\n{out.strip()}")
    code, _ = run(["git", "diff", "--cached", "--quiet"], check=False)
    if code == 0:
        parts.append("nothing staged — nothing to commit")
        return "\n\n".join(parts)
    code, out = run(
        ["git", "commit", "-m", f"chore(daily-translate): KST {date_label}"],
        check=False,
    )
    parts.append(f"git commit (exit {code})\n{out.strip()}")
    code, out = run(["git", "push", "origin", "main"], check=False)
    parts.append(f"git push (exit {code})\n{out.strip()}")
    return "\n\n".join(parts)


def email_summary(subject: str, body: str) -> str:
    """Reuse daily_update.send_email so SMTP setup stays in one place."""
    try:
        from scripts.daily_update import send_email
        return send_email(subject, body)
    except Exception as e:
        return f"email send failed: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would run; don't invoke claude/git")
    ap.add_argument("--timeout-minutes", type=int, default=60,
                    help="hard cap for the Claude session (default 60)")
    args = ap.parse_args()

    today_kst = datetime.now(KST).strftime("%Y-%m-%d")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    step_logs: list[str] = [f"start: {now}"]
    status = "ok"

    summary = read_summary()
    if not summary:
        body = f"data/pending/today.summary.json not found. nothing to translate."
        LOG_PATH.write_text(f"# [translate] {today_kst} — no summary\n\n{body}\n",
                            encoding="utf-8")
        return 0

    chunks = chunk_paths(summary)
    if not chunks:
        body = f"chunk_files is empty in summary. nothing to translate."
        LOG_PATH.write_text(f"# [translate] {today_kst} — no chunks\n\n{body}\n",
                            encoding="utf-8")
        return 0

    need, done = already_translated(chunks)
    step_logs.append(f"chunks total={len(chunks)} need={len(need)} done={len(done)}")

    if args.dry_run:
        for p in need:
            step_logs.append(f"  would translate: {p.relative_to(ROOT)}")
        LOG_PATH.write_text(f"# [translate] {today_kst} — dry run\n\n"
                            + "\n".join(step_logs) + "\n",
                            encoding="utf-8")
        print("\n".join(step_logs))
        return 0

    TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if need:
            step_logs.append(run_claude_translate(args.timeout_minutes))
            # re-check after Claude run
            still_missing, _ = already_translated(need)
            if still_missing:
                status = "partial"
                step_logs.append(
                    "WARN: still missing translations for: "
                    + ", ".join(p.name for p in still_missing)
                )

        step_logs.append(import_translations())
        step_logs.append(build_db())
        if not args.no_git:
            step_logs.append(git_commit_push(today_kst))
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        step_logs.append(f"TIMEOUT: {e}")
    except Exception:
        status = "error"
        step_logs.append("UNEXPECTED EXCEPTION:\n"
                         + "".join(traceback.format_exc())[-2000:])

    subject = f"[인도네시아 법령 번역] {today_kst} — {status} ({len(need)} chunks)"
    body = "\n\n".join(step_logs)
    LOG_PATH.write_text(f"# {subject}\n\n{body}\n", encoding="utf-8")

    if args.no_email:
        print(f"[no-email] {subject}")
        print(body[:1500])
    else:
        result = email_summary(subject, body)
        print(f"[email] {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
