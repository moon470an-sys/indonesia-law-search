"""peraturan.go.id 우회 크롤 — RunPod 경유 (한국 IP 차단 우회).

peraturan.go.id 는 한국 IP를 네트워크 레벨에서 차단(TCP connect timeout)하므로,
비한국 egress인 RunPod 파드에서 크롤을 실행하고 결과만 회수한다.

흐름:
  1) RunPod 파드 spawn (저렴한 GPU fallback)
  2) SSH 접속 → httpx/bs4 설치 → crawler/peraturan_fetch.py 업로드
  3) (probe) 연결성/렌더링 확인  또는  (full) 크롤 → /workspace/peraturan.jsonl
  4) 결과 JSONL 다운로드
  5) db.upsert_law 로 laws.db 반영 (신규만 카운트) → data/laws/peraturan_go_id.jsonl 재덤프
  6) 파드 terminate (성공/실패 무관, --keep-on-error 시 유지)

실행 (크롤러 파이썬 C:\\Python314 — runpod/paramiko/scp/httpx/bs4 설치돼 있음):
    python -m scripts.runpod_crawl_peraturan --probe-only          # 검증용 (크롤 안 함)
    python -m scripts.runpod_crawl_peraturan                       # 일일 증분 (섹션별 5페이지)
    python -m scripts.runpod_crawl_peraturan --pages-per-section 200   # 백필(과거분 보강)
    python -m scripts.runpod_crawl_peraturan --no-import           # 다운로드만 (import 안 함)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
# RUNPOD_API_KEY 가 crawler/.env 에 없으면 RAG_app/.env 에서 폴백 로드 (시크릿 중복 저장 회피)
if not os.environ.get("RUNPOD_API_KEY"):
    _ragenv = Path(r"D:\인도네시아 법령 원문\RAG_app\.env")
    if _ragenv.exists():
        load_dotenv(_ragenv)

import runpod
import paramiko
from scp import SCPClient

GPU_FALLBACK = [
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX A5000",
    "NVIDIA L4",
    "NVIDIA A40",
]
IMAGE_NAME = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"
POD_NAME = "indonesia-peraturan-crawl"
SSH_USERNAME = "root"
SSH_KEY_PATH = Path.home() / ".ssh" / "id_ed25519"
REMOTE_WORKDIR = "/workspace"
FETCH_SCRIPT_LOCAL = ROOT / "crawler" / "peraturan_fetch.py"
REMOTE_FETCH = f"{REMOTE_WORKDIR}/peraturan_fetch.py"
REMOTE_OUT = f"{REMOTE_WORKDIR}/peraturan.jsonl"
LOCAL_OUT = ROOT / "data" / "pending" / "peraturan.jsonl"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_for_pod_ready(pod_id: str, timeout: int = 600) -> dict:
    log(f"  pod {pod_id} ready 대기 (timeout {timeout}s)")
    t0 = time.time()
    while time.time() - t0 < timeout:
        pod = runpod.get_pod(pod_id)
        runtime = pod.get("runtime") or {}
        ports = runtime.get("ports") or []
        ssh_ports = [p for p in ports if p.get("privatePort") == 22 and p.get("ip") and p.get("publicPort")]
        if pod.get("desiredStatus") == "RUNNING" and ssh_ports:
            s = ssh_ports[0]
            log(f"  ready! ssh={s['ip']}:{s['publicPort']}")
            return {"ssh_ip": s["ip"], "ssh_port": s["publicPort"]}
        log(f"  ... desired={pod.get('desiredStatus')}, ports={len(ports)} ({int(time.time()-t0)}s)")
        time.sleep(10)
    raise TimeoutError(f"pod {pod_id} not ready in {timeout}s")


def ssh_connect(ip: str, port: int, retries: int = 12) -> paramiko.SSHClient:
    log(f"  SSH connect → {ip}:{port}")
    pkey = paramiko.Ed25519Key.from_private_key_file(str(SSH_KEY_PATH))
    last = None
    for i in range(retries):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=ip, port=port, username=SSH_USERNAME, pkey=pkey,
                        timeout=10, banner_timeout=15, auth_timeout=15)
            log("  SSH OK")
            return cli
        except Exception as exc:  # noqa: BLE001
            last = exc
            log(f"  SSH attempt {i+1}/{retries}: {type(exc).__name__}")
            time.sleep(10)
    raise RuntimeError(f"SSH 실패: {last}")


def run_cmd(ssh: paramiko.SSHClient, cmd: str, label: str = "") -> tuple[int, str]:
    if label:
        log(f"  $ {label}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out_lines = []
    for line in iter(stdout.readline, ""):
        line = line.rstrip()
        if line:
            print(f"    {line}", flush=True)
            out_lines.append(line)
    rc = stdout.channel.recv_exit_status()
    return rc, "\n".join(out_lines)


def spawn_pod(gpu_type: str | None, container_disk_gb: int, cloud_type: str):
    candidates = ([gpu_type] if gpu_type else []) + [g for g in GPU_FALLBACK if g != gpu_type]
    last = None
    for gid in candidates:
        log(f"  시도: {gid}")
        try:
            pod = runpod.create_pod(
                name=POD_NAME, image_name=IMAGE_NAME, gpu_type_id=gid,
                cloud_type=cloud_type, gpu_count=1, volume_in_gb=0,
                container_disk_in_gb=container_disk_gb, ports="22/tcp",
                start_ssh=True, support_public_ip=True,
            )
            log(f"  성공: {gid}")
            return pod
        except Exception as exc:  # noqa: BLE001
            last = exc
            log(f"  실패: {type(exc).__name__}: {exc}")
            time.sleep(2)
    raise RuntimeError(f"모든 GPU 후보 spawn 실패: {last}")


def import_jsonl(jsonl_path: Path) -> dict:
    """다운로드한 JSONL을 laws.db에 upsert. (source, source_url) 기준 신규만 추가."""
    from crawler import db, dump_jsonl
    db.init_db()
    SRC = "peraturan_go_id"
    with db.connect() as c:
        before = c.execute("SELECT COUNT(*) FROM laws WHERE source=?", (SRC,)).fetchone()[0]
    seen = 0
    by_type: dict[str, int] = {}
    with db.connect() as c:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                db.upsert_law(c, row)
                seen += 1
                by_type[row.get("law_type", "?")] = by_type.get(row.get("law_type", "?"), 0) + 1
    with db.connect() as c:
        after = c.execute("SELECT COUNT(*) FROM laws WHERE source=?", (SRC,)).fetchone()[0]
    # JSONL 재덤프 (git source of truth)
    dump_jsonl.main([SRC])
    return {"seen": seen, "new": after - before, "before": before, "after": after, "by_type": by_type}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-only", action="store_true", help="연결성/렌더링만 확인하고 종료")
    ap.add_argument("--pages-per-section", type=int, default=5)
    ap.add_argument("--no-import", action="store_true", help="다운로드만, laws.db 반영 안 함")
    ap.add_argument("--gpu-type", default=None)
    ap.add_argument("--cloud-type", default="ALL", choices=["COMMUNITY", "SECURE", "ALL"])
    ap.add_argument("--container-disk-gb", type=int, default=20)
    ap.add_argument("--keep-on-error", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("RUNPOD_API_KEY"):
        log("FATAL: RUNPOD_API_KEY 없음 (crawler/.env 또는 RAG_app/.env 확인)")
        return 1
    runpod.api_key = os.environ["RUNPOD_API_KEY"]
    if not SSH_KEY_PATH.exists():
        log(f"FATAL: SSH key 없음: {SSH_KEY_PATH}")
        return 1
    if not FETCH_SCRIPT_LOCAL.exists():
        log(f"FATAL: {FETCH_SCRIPT_LOCAL} 없음")
        return 1

    log("=== peraturan.go.id RunPod 우회 크롤 ===")
    log(f"  mode={'probe' if args.probe_only else 'full'}, pages/section={args.pages_per_section}")

    log("[1/6] Pod spawn")
    pod = spawn_pod(args.gpu_type, args.container_disk_gb, args.cloud_type)
    pod_id = pod["id"]
    log(f"  pod id={pod_id}")

    ssh = None
    success = False
    result: dict = {}
    try:
        log("[2/6] ready 대기")
        info = wait_for_pod_ready(pod_id)
        time.sleep(25)  # sshd warm-up
        log("[3/6] SSH 연결")
        ssh = ssh_connect(info["ssh_ip"], info["ssh_port"])

        log("[4/6] 의존성 설치 + 스크립트 업로드")
        rc, _ = run_cmd(ssh, "pip install --quiet httpx beautifulsoup4", "pip install httpx bs4")
        if rc != 0:
            raise RuntimeError(f"pip install 실패 rc={rc}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(str(FETCH_SCRIPT_LOCAL), REMOTE_FETCH)
        log("  업로드 OK")

        if args.probe_only:
            log("[5/6] probe 실행")
            rc, out = run_cmd(ssh, f"cd {REMOTE_WORKDIR} && python peraturan_fetch.py --probe", "probe")
            success = (rc == 0)
            result = {"probe_rc": rc}
            log(f"  probe rc={rc}")
        else:
            log(f"[5/6] 크롤 실행 (pages/section={args.pages_per_section})")
            rc, out = run_cmd(
                ssh,
                f"cd {REMOTE_WORKDIR} && python peraturan_fetch.py "
                f"--out {REMOTE_OUT} --pages-per-section {args.pages_per_section}",
                "crawl",
            )
            if rc != 0:
                raise RuntimeError(f"크롤 실패 rc={rc}")
            log("[6/6] 결과 다운로드")
            LOCAL_OUT.parent.mkdir(parents=True, exist_ok=True)
            with SCPClient(ssh.get_transport(), socket_timeout=120.0) as scp:
                scp.get(REMOTE_OUT, str(LOCAL_OUT))
            n_lines = sum(1 for _ in open(LOCAL_OUT, encoding="utf-8"))
            log(f"  다운로드 OK: {LOCAL_OUT} ({n_lines} records)")
            result["downloaded"] = n_lines
            success = True
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        success = False
    finally:
        if ssh:
            try:
                ssh.close()
            except Exception:
                pass
        if success or not args.keep_on_error:
            log(f"  pod terminate: {pod_id}")
            try:
                runpod.terminate_pod(pod_id)
                log("  terminated.")
            except Exception as exc:  # noqa: BLE001
                log(f"  WARN: terminate 실패: {exc} → 콘솔에서 수동 종료: {pod_id}")
        else:
            log(f"  pod 유지(debug). 수동 종료 필요: {pod_id}")

    # import (full 모드, 성공 시, --no-import 아닐 때)
    if success and not args.probe_only and not args.no_import:
        log("=== laws.db 반영 (db.upsert_law) ===")
        try:
            imp = import_jsonl(LOCAL_OUT)
            log(f"  seen={imp['seen']}, 신규={imp['new']} "
                f"(peraturan_go_id {imp['before']}→{imp['after']})")
            log(f"  타입별: {imp['by_type']}")
            result["import"] = imp
        except Exception:
            log("import 실패:\n" + traceback.format_exc()[-1500:])
            success = False

    log("=== 결과 ===")
    log(json.dumps(result, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
