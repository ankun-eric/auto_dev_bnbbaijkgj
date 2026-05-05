#!/usr/bin/env python3
"""[PRD-01 全平台固定时段切片] Android APK 远程构建 + 上传脚本

流程：
  1. 推送本地三端 utils 文件 + 后端文件到 GitHub（git add/commit/push，含重试）
  2. 触发 GitHub Actions android-build.yml workflow
  3. 轮询构建状态（30s 一次，最多 30 分钟）
  4. 下载 APK release 资产
  5. 重命名为 bini_health_prd01_timeslot_*.apk
  6. paramiko SFTP 上传到服务器 /home/ubuntu/<PROJECT_ID>/static/apk/
  7. curl 验证 HTTP 200
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

LOCAL_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_APK_DIR = f"/home/ubuntu/{PROJECT_ID}/static/apk"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

GH_REPO = "ankun-eric/auto_dev_bnbbaijkgj"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
WORKFLOW = "android-build.yml"

POLL_INTERVAL = 30
MAX_POLL_SECONDS = 30 * 60


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_cmd(args, *, cwd=None, env=None, check=True, timeout=300, capture=True):
    log(f"$ {' '.join(args) if isinstance(args, list) else args}")
    res = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        timeout=timeout,
        capture_output=capture,
        text=True,
        shell=isinstance(args, str),
    )
    if capture:
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(f"STDERR: {res.stderr}")
    log(f"  exit={res.returncode}")
    if check and res.returncode != 0:
        raise RuntimeError(f"cmd failed: {args}")
    return res


def retry_run(args, *, cwd=None, env=None, max_attempts=3, timeout=300):
    last = None
    for i in range(1, max_attempts + 1):
        log(f"--- attempt {i}/{max_attempts} ---")
        try:
            res = run_cmd(args, cwd=cwd, env=env, check=False, timeout=timeout)
            if res.returncode == 0:
                return res
            last = res
        except Exception as e:
            log(f"  exception: {e}")
            last = e
        time.sleep(5 * i)
    return last


def build_env():
    e = os.environ.copy()
    e["GH_TOKEN"] = GH_TOKEN
    e["GITHUB_TOKEN"] = GH_TOKEN
    return e


def stage_and_push() -> bool:
    """git add 关键文件 + commit + push（带重试）。返回是否成功推送。"""
    files = [
        "flutter_app/lib/utils/time_slots.dart",
        "h5-web/src/lib/timeSlots.ts",
        "miniprogram/utils/timeSlots.js",
        "backend/app/api/common.py",
        "backend/app/utils/time_slots.py",
        "backend/app/api/merchant_dashboard.py",
        "backend/app/api/unified_orders.py",
        "backend/app/main.py",
        "backend/app/models/models.py",
        "backend/app/services/schema_sync.py",
        "backend/scripts/backfill_unified_orders_time_slot.py",
        "backend/tests/test_time_slots_unified_v1.py",
        ".github/workflows/android-build.yml",
        "deploy/_build_apk_prd01_20260505.py",
    ]
    cwd = str(LOCAL_ROOT)
    env = build_env()
    for f in files:
        p = LOCAL_ROOT / f
        if p.exists():
            run_cmd(["git", "add", "--", f], cwd=cwd, check=False)
        else:
            log(f"  skip missing file: {f}")

    diff = run_cmd(["git", "diff", "--cached", "--name-only"], cwd=cwd, check=False)
    if not diff.stdout.strip():
        log("no staged changes — skipping commit")
    else:
        run_cmd(
            [
                "git",
                "commit",
                "-m",
                "[prd-01] 全平台固定时段切片体系：三端 utils + 后端 API/模型/迁移/测试",
            ],
            cwd=cwd,
            check=False,
        )

    res = retry_run(["git", "push", "origin", "HEAD:master"], cwd=cwd, env=env, max_attempts=3, timeout=300)
    if isinstance(res, subprocess.CompletedProcess) and res.returncode == 0:
        return True
    log("WARNING: git push failed after retries — will still try to trigger workflow on remote HEAD")
    return False


def get_current_sha() -> str:
    res = run_cmd(["git", "rev-parse", "HEAD"], cwd=str(LOCAL_ROOT), check=True)
    return res.stdout.strip()


def get_remote_master_sha() -> str:
    env = build_env()
    res = run_cmd(
        ["gh", "api", f"repos/{GH_REPO}/branches/master", "--jq", ".commit.sha"],
        cwd=str(LOCAL_ROOT),
        env=env,
        check=False,
    )
    return res.stdout.strip()


def trigger_workflow(version: str) -> None:
    env = build_env()
    res = retry_run(
        ["gh", "workflow", "run", WORKFLOW, "-R", GH_REPO, "-f", f"version={version}"],
        cwd=str(LOCAL_ROOT),
        env=env,
        max_attempts=3,
        timeout=120,
    )
    if not (isinstance(res, subprocess.CompletedProcess) and res.returncode == 0):
        raise RuntimeError("Failed to trigger workflow after retries")


def find_run_id(version: str) -> str | None:
    """从最近 workflow runs 中找到我们触发的那个 run id。"""
    env = build_env()
    res = run_cmd(
        [
            "gh",
            "run",
            "list",
            "-R",
            GH_REPO,
            "--workflow",
            WORKFLOW,
            "--limit",
            "10",
            "--json",
            "databaseId,displayTitle,event,headBranch,status,conclusion,createdAt",
        ],
        cwd=str(LOCAL_ROOT),
        env=env,
        check=False,
    )
    if res.returncode != 0:
        return None
    try:
        data = json.loads(res.stdout)
    except Exception:
        return None
    runs = sorted(data, key=lambda r: r.get("createdAt", ""), reverse=True)
    if runs:
        return str(runs[0]["databaseId"])
    return None


def poll_run(run_id: str) -> str:
    env = build_env()
    deadline = time.time() + MAX_POLL_SECONDS
    while time.time() < deadline:
        res = run_cmd(
            ["gh", "run", "view", run_id, "-R", GH_REPO, "--json", "status,conclusion"],
            cwd=str(LOCAL_ROOT),
            env=env,
            check=False,
        )
        try:
            d = json.loads(res.stdout)
        except Exception:
            d = {}
        status = d.get("status", "?")
        concl = d.get("conclusion", "?")
        log(f"  run {run_id}: status={status}, conclusion={concl}")
        if status == "completed":
            return concl or "?"
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"workflow run {run_id} timed out after {MAX_POLL_SECONDS}s")


def download_apk(version: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    env = build_env()
    res = retry_run(
        [
            "gh",
            "release",
            "download",
            version,
            "-R",
            GH_REPO,
            "--pattern",
            "*.apk",
            "--dir",
            str(dest_dir),
            "--clobber",
        ],
        cwd=str(LOCAL_ROOT),
        env=env,
        max_attempts=3,
        timeout=600,
    )
    if not (isinstance(res, subprocess.CompletedProcess) and res.returncode == 0):
        log("gh release download failed — try ghproxy mirror fallback")
        # 通过 gh api 拿到资产 URL，再走 ghproxy
        api = run_cmd(
            ["gh", "api", f"repos/{GH_REPO}/releases/tags/{version}"],
            cwd=str(LOCAL_ROOT),
            env=env,
            check=False,
        )
        if api.returncode == 0:
            try:
                rel = json.loads(api.stdout)
                for asset in rel.get("assets", []):
                    name = asset.get("name", "")
                    url = asset.get("browser_download_url")
                    if name.endswith(".apk") and url:
                        mirror = f"https://ghproxy.com/{url}"
                        log(f"trying mirror: {mirror}")
                        out = dest_dir / name
                        # 用 curl 下载
                        run_cmd(
                            ["curl", "-L", "-k", "-o", str(out), mirror],
                            cwd=str(LOCAL_ROOT),
                            check=False,
                            timeout=600,
                        )
                        if out.exists() and out.stat().st_size > 100_000:
                            return out
            except Exception as e:
                log(f"mirror fallback parse failed: {e}")
        raise RuntimeError("Failed to download APK after retries")

    apks = list(dest_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError("no APK found in download dir")
    return apks[0]


def upload_apk(local_apk: Path, remote_name: str) -> tuple[str, int]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    try:
        _i, o, _e = ssh.exec_command(f'mkdir -p "{REMOTE_APK_DIR}"', timeout=30)
        o.channel.recv_exit_status()

        sftp = ssh.open_sftp()
        remote_path = f"{REMOTE_APK_DIR}/{remote_name}"
        log(f"sftp put {local_apk} -> {remote_path}")
        sftp.put(str(local_apk), remote_path)
        sftp.close()

        _i, o, _e = ssh.exec_command(f'ls -la "{remote_path}" && stat -c %s "{remote_path}"', timeout=30)
        out = o.read().decode("utf-8", errors="replace")
        o.channel.recv_exit_status()
        print(out)
        size = local_apk.stat().st_size
        return remote_path, size
    finally:
        ssh.close()


def verify_http(url: str) -> int:
    res = run_cmd(
        ["curl", "-k", "-sI", "-o", "-", "-w", "HTTP:%{http_code}\n", url],
        cwd=str(LOCAL_ROOT),
        check=False,
        timeout=60,
    )
    code = 0
    for line in (res.stdout or "").splitlines():
        if line.startswith("HTTP:"):
            try:
                code = int(line.split(":", 1)[1].strip())
            except Exception:
                code = 0
    return code


def main() -> int:
    print("=" * 70)
    print("[android-apk] PRD-01 时段切片 Android APK 构建+上传")
    print("=" * 70)

    ts = datetime.now()
    suffix = secrets.token_hex(2)
    version = f"android-prd01-v{ts.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    apk_name = f"bini_health_prd01_timeslot_{ts.strftime('%Y%m%d_%H%M%S')}_{suffix}.apk"
    log(f"version tag: {version}")
    log(f"target apk : {apk_name}")

    # 1) push
    push_ok = stage_and_push()
    log(f"push_ok={push_ok}")
    local_sha = get_current_sha()
    remote_sha = get_remote_master_sha()
    log(f"local HEAD = {local_sha}")
    log(f"remote master = {remote_sha}")

    # 2) trigger
    trigger_workflow(version)
    log("workflow dispatched, waiting 10s for run to register...")
    time.sleep(10)

    run_id = None
    for _ in range(6):
        run_id = find_run_id(version)
        if run_id:
            break
        time.sleep(5)
    if not run_id:
        raise RuntimeError("could not find newly-dispatched run id")
    log(f"run id = {run_id}")

    # 3) poll
    concl = poll_run(run_id)
    if concl != "success":
        raise RuntimeError(f"workflow run {run_id} concluded as {concl}")

    # 4) download
    tmp = LOCAL_ROOT / "deploy" / f"_apk_tmp_{suffix}"
    apk = download_apk(version, tmp)
    log(f"downloaded: {apk} ({apk.stat().st_size:,} bytes)")

    # 5) rename
    final_local = tmp / apk_name
    if apk.resolve() != final_local.resolve():
        apk.rename(final_local)
    log(f"renamed: {final_local}")

    # 6) upload
    remote_path, size = upload_apk(final_local, apk_name)
    log(f"uploaded -> {remote_path} ({size:,} bytes)")

    # 7) verify
    download_url = f"{BASE_URL}/apk/{apk_name}"
    code = verify_http(download_url)
    log(f"HTTP {code} for {download_url}")

    print("\n" + "=" * 70)
    print("Android APK 打包结果：")
    print(f"- 版本标签: {version}")
    print(f"- APK 文件名: {apk_name}")
    print(f"- 下载 URL: {download_url}")
    print(f"- HTTP 状态: {code}")
    print(f"- 文件大小: {size / (1024 * 1024):.2f} MB")
    print("=" * 70)

    if code != 200:
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\nFAILED: {exc}")
        sys.exit(1)
