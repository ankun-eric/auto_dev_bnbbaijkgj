"""
Android APK 远程构建 + 下载 + 上传部署脚本 (UI polish 版本)
流程:
  1. 生成版本标签
  2. gh workflow run android-build.yml -f version=<tag>
  3. 循环轮询构建状态
  4. gh release download 拉 APK
  5. 重命名 -> app_{YYYYMMDD}_{HHMMSS}_{hex}.apk
  6. SFTP 上传到服务器静态目录
  7. HTTPS 可达性校验
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client  # noqa: E402

# ---- 常量 -------------------------------------------------------------------
PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
DEPLOY_DIR = PROJECT_ROOT / "deploy"
APK_TMP = DEPLOY_DIR / "_apk_tmp"
WORKFLOW_FILE = "android-build.yml"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
# gateway nginx 将 /autodev/<id>/static/downloads/ 指向 /home/ubuntu/<id>/static/downloads/
REMOTE_STATIC_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"
URL_SUBPATH = "static/downloads"

POLL_INTERVAL = 30          # seconds
POLL_MAX_MINUTES = 30
MAX_BUILD_RETRY = 2         # 构建失败最多重试次数


def log(msg: str) -> None:
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def retry(cmd_list, max_retries: int = 3, delay: int = 10,
          timeout: int = 300, cwd: str | None = None):
    """国内网络重试包装,指数退避。"""
    last = None
    cur = delay
    for i in range(max_retries):
        try:
            r = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            log(f"  retry {i+1}/{max_retries} timeout: {e}; sleep {cur}s")
            time.sleep(cur)
            cur *= 2
            last = e
            continue
        if r.returncode == 0:
            return r
        last = r
        log(f"  retry {i+1}/{max_retries} rc={r.returncode}: {(r.stderr or r.stdout or '').strip()[:200]}")
        time.sleep(cur)
        cur *= 2
    if isinstance(last, subprocess.CompletedProcess):
        raise RuntimeError(f"failed after {max_retries}: {last.stderr or last.stdout}")
    raise RuntimeError(f"failed after {max_retries}: {last}")


def make_version_tag() -> tuple[str, str, str, str]:
    """生成 version tag, 以及 (yyyymmdd, hhmmss, hex4)。"""
    now = _dt.datetime.now()
    ymd = now.strftime("%Y%m%d")
    hms = now.strftime("%H%M%S")
    hx = secrets.token_hex(2)
    tag = f"android-v{ymd}-{hms}-{hx}"
    return tag, ymd, hms, hx


def trigger_workflow(tag: str) -> None:
    log(f"触发 workflow: {WORKFLOW_FILE}  version={tag}")
    retry(
        ["gh", "workflow", "run", WORKFLOW_FILE, "-f", f"version={tag}"],
        max_retries=3, delay=10, timeout=90,
        cwd=str(PROJECT_ROOT),
    )
    log("  workflow run 已提交")


def wait_new_run(since_ts: float, tag: str) -> str:
    """等待出现新的 run id。"""
    for attempt in range(20):
        r = retry(
            ["gh", "run", "list", "--workflow", WORKFLOW_FILE,
             "--limit", "5", "--json", "databaseId,status,createdAt,displayTitle,headBranch,event"],
            max_retries=3, delay=5, timeout=60, cwd=str(PROJECT_ROOT),
        )
        try:
            runs = json.loads(r.stdout)
        except Exception:
            runs = []
        for run in runs:
            created = run.get("createdAt", "")
            try:
                t = _dt.datetime.strptime(
                    created, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=_dt.timezone.utc).timestamp()
            except Exception:
                t = 0
            if t >= since_ts - 5 and run.get("event") == "workflow_dispatch":
                rid = str(run["databaseId"])
                log(f"  检测到新 run: id={rid} created={created}")
                return rid
        time.sleep(5)
    raise RuntimeError("等待新 run 超时")


def poll_run(run_id: str) -> tuple[str, str]:
    """轮询 run,返回 (status, conclusion)。"""
    deadline = time.time() + POLL_MAX_MINUTES * 60
    last_status = ""
    while time.time() < deadline:
        r = retry(
            ["gh", "run", "view", run_id, "--json", "status,conclusion"],
            max_retries=3, delay=5, timeout=60, cwd=str(PROJECT_ROOT),
        )
        try:
            info = json.loads(r.stdout)
        except Exception:
            info = {}
        status = info.get("status", "")
        conclusion = info.get("conclusion") or ""
        if status != last_status:
            log(f"  run {run_id} status={status} conclusion={conclusion}")
            last_status = status
        if status == "completed":
            return status, conclusion
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"轮询超时 (> {POLL_MAX_MINUTES} min)")


def fetch_fail_log(run_id: str) -> str:
    try:
        r = subprocess.run(
            ["gh", "run", "view", run_id, "--log-failed"],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT), encoding="utf-8", errors="replace",
        )
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as e:
        return f"<fetch log failed: {e}>"


def download_apk(tag: str) -> Path:
    """gh release download -> _apk_tmp, 返回 APK 绝对路径。"""
    if APK_TMP.exists():
        shutil.rmtree(APK_TMP, ignore_errors=True)
    APK_TMP.mkdir(parents=True, exist_ok=True)

    r = retry(
        ["gh", "release", "list", "--limit", "10",
         "--json", "tagName,name,createdAt"],
        max_retries=3, delay=5, timeout=60, cwd=str(PROJECT_ROOT),
    )
    try:
        releases = json.loads(r.stdout)
    except Exception:
        releases = []
    tags = [it.get("tagName") for it in releases]
    log(f"  最近 releases: {tags[:5]}")
    if tag not in tags:
        raise RuntimeError(f"release 未找到 tag={tag}")

    retry(
        ["gh", "release", "download", tag,
         "--pattern", "*.apk", "--dir", str(APK_TMP)],
        max_retries=4, delay=15, timeout=600, cwd=str(PROJECT_ROOT),
    )
    apks = list(APK_TMP.glob("*.apk"))
    if not apks:
        raise RuntimeError("release 下载完成但未发现 apk")
    return apks[0]


def upload_and_verify(local_apk: Path, new_name: str) -> tuple[str, int]:
    """SFTP 上传并 HTTPS 验证,返回 (url, size)。"""
    remote_path = f"{REMOTE_STATIC_DIR}/{new_name}"
    log(f"SSH 连接并准备目录: {REMOTE_STATIC_DIR}")
    ssh = create_client()
    try:
        ssh.exec_command(f"mkdir -p {REMOTE_STATIC_DIR}")
        time.sleep(2)
        sftp = ssh.open_sftp()
        try:
            try:
                sftp.stat(REMOTE_STATIC_DIR)
            except IOError:
                # 递归创建
                parts = REMOTE_STATIC_DIR.strip("/").split("/")
                cur = ""
                for p in parts:
                    cur += "/" + p
                    try:
                        sftp.stat(cur)
                    except IOError:
                        try:
                            sftp.mkdir(cur)
                        except Exception:
                            pass
            log(f"上传 -> {remote_path}")
            sftp.put(str(local_apk), remote_path)
            st = sftp.stat(remote_path)
            log(f"  远端文件大小: {st.st_size} bytes")
        finally:
            sftp.close()
    finally:
        ssh.close()

    url = f"{BASE_URL}/{URL_SUBPATH}/{new_name}"
    log(f"HTTPS 校验: {url}")
    size = 0
    last_err = None
    for i in range(5):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                cl = int(resp.headers.get("Content-Length", "0"))
                log(f"  HEAD try{i+1}: status={code} content-length={cl}")
                if code == 200 and cl > 1024 * 1024:
                    size = cl
                    break
        except Exception as e:
            last_err = e
            log(f"  HEAD try{i+1} error: {e}")
        time.sleep(6)
    if size == 0:
        raise RuntimeError(f"HTTPS 校验失败: {last_err}")
    return url, size


def run_one(max_retry: int = MAX_BUILD_RETRY) -> dict:
    start = time.time()
    attempt = 0
    failure_notes: list[str] = []

    while attempt <= max_retry:
        attempt += 1
        tag, ymd, hms, hx = make_version_tag()
        log(f"=== Attempt {attempt}/{max_retry+1}  tag={tag} ===")
        trigger_ts = time.time()
        trigger_workflow(tag)
        time.sleep(8)
        run_id = wait_new_run(trigger_ts, tag)
        status, conclusion = poll_run(run_id)
        release_url = (
            f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{tag}"
        )
        if conclusion != "success":
            fail_log = fetch_fail_log(run_id)
            note = (
                f"attempt {attempt} run={run_id} conclusion={conclusion}\n"
                f"--- fail log (tail) ---\n{fail_log[-3000:]}"
            )
            failure_notes.append(note)
            log(f"构建失败: conclusion={conclusion}")
            if attempt > max_retry:
                return {
                    "success": False,
                    "reason": "build failed",
                    "attempts": attempt,
                    "failure_notes": failure_notes,
                    "last_run_id": run_id,
                    "last_tag": tag,
                    "release_page": release_url,
                    "elapsed_sec": int(time.time() - start),
                }
            log("准备重试构建...")
            continue

        log(f"构建成功 run={run_id}")
        apk_local = download_apk(tag)
        new_name = f"app_{ymd}_{hms}_{hx}.apk"
        renamed = APK_TMP / new_name
        shutil.move(str(apk_local), str(renamed))
        log(f"  本地重命名: {renamed.name}  size={renamed.stat().st_size}")
        url, size = upload_and_verify(renamed, new_name)
        elapsed = int(time.time() - start)
        return {
            "success": True,
            "apk_name": new_name,
            "download_url": url,
            "file_size": size,
            "file_size_mb": round(size / 1024 / 1024, 2),
            "release_page": release_url,
            "tag": tag,
            "run_id": run_id,
            "elapsed_sec": elapsed,
            "attempts": attempt,
        }

    return {"success": False, "reason": "unknown"}


def main() -> int:
    log("=== Android APK 打包流程开始 ===")
    result = run_one()
    print("\n================ RESULT ================")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("========================================\n")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
