#!/usr/bin/env python3
"""
PRD-443 Android APK 打包子 Agent
通过 GitHub Actions 远程构建 Flutter Android APK，下载产物，
上传到部署服务器并验证下载链接可达。
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import paramiko

# ====================== 配置 ======================
PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
WORKFLOW_FILE = "android-build.yml"
LOG_PATH = PROJECT_ROOT / "_pack_prd443_android.log"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
REMOTE_APK_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

POLL_INTERVAL_SEC = 30
POLL_TIMEOUT_SEC = 30 * 60  # 30 minutes


# ====================== 日志 ======================
def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ====================== 工具函数 ======================
def run_cmd(args: list[str], cwd: Path | None = None, check: bool = True,
            capture: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    _log(f"$ {' '.join(args)}" + (f"  (cwd={cwd})" if cwd else ""))
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if capture:
        if proc.stdout:
            for line in proc.stdout.rstrip().splitlines():
                _log(f"  | {line}")
        if proc.stderr:
            for line in proc.stderr.rstrip().splitlines():
                _log(f"  ! {line}")
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit={proc.returncode}): {' '.join(args)}")
    return proc


def run_with_retry(args: list[str], cwd: Path | None = None,
                   retries: int = 3, base_delay: int = 10) -> subprocess.CompletedProcess:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return run_cmd(args, cwd=cwd, check=True, capture=True)
        except Exception as e:
            last_err = e
            if attempt < retries:
                delay = base_delay * (2 ** (attempt - 1))
                _log(f"重试 {attempt}/{retries} 失败：{e}; 等待 {delay}s 后重试")
                time.sleep(delay)
            else:
                _log(f"重试全部失败：{e}")
    assert last_err is not None
    raise last_err


def gen_version_tag() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand_hex = "".join(random.choice("0123456789abcdef") for _ in range(4))
    return f"android-prd443-v{ts}-{rand_hex}"


# ====================== GitHub Actions 触发与轮询 ======================
def trigger_workflow(version_tag: str) -> None:
    _log(f"触发 workflow {WORKFLOW_FILE}, version={version_tag}")
    run_with_retry(
        ["gh", "workflow", "run", WORKFLOW_FILE, "-f", f"version={version_tag}"],
        cwd=PROJECT_ROOT,
        retries=3,
        base_delay=10,
    )


def get_latest_run_id() -> str:
    """触发后等几秒，然后查询最近的 run id。"""
    time.sleep(8)
    for attempt in range(1, 6):
        try:
            proc = run_cmd(
                ["gh", "run", "list", f"--workflow={WORKFLOW_FILE}",
                 "--limit", "1", "--json", "databaseId,status,headBranch,createdAt"],
                cwd=PROJECT_ROOT,
                check=True,
            )
            data = json.loads(proc.stdout)
            if data and isinstance(data, list):
                rid = str(data[0]["databaseId"])
                _log(f"获取到 run id: {rid} (status={data[0].get('status')})")
                return rid
        except Exception as e:
            _log(f"获取 run id 失败 (attempt {attempt}): {e}")
        time.sleep(5)
    raise RuntimeError("无法获取 GitHub Actions run id")


def poll_run(run_id: str) -> str:
    """轮询直到 run 完成；返回 conclusion (success / failure / cancelled)。"""
    deadline = time.time() + POLL_TIMEOUT_SEC
    last_status = ""
    while time.time() < deadline:
        try:
            proc = run_cmd(
                ["gh", "run", "view", run_id, "--json", "status,conclusion,url"],
                cwd=PROJECT_ROOT,
                check=True,
            )
            info = json.loads(proc.stdout)
            status = info.get("status", "")
            conclusion = info.get("conclusion", "") or ""
            if status != last_status:
                _log(f"run {run_id} status={status} conclusion={conclusion} url={info.get('url','')}")
                last_status = status
            if status == "completed":
                _log(f"run {run_id} 完成: conclusion={conclusion}")
                return conclusion
        except Exception as e:
            _log(f"轮询出错 (忽略): {e}")
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"等待 run {run_id} 超过 {POLL_TIMEOUT_SEC}s 仍未完成")


# ====================== 下载 / 重命名 ======================
def download_release_apk(version_tag: str, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    # 清空已有同名 apk 防止冲突
    for f in work_dir.glob("*.apk"):
        try:
            f.unlink()
        except Exception:
            pass

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            run_cmd(
                ["gh", "release", "download", version_tag, "--pattern", "*.apk",
                 "--dir", str(work_dir), "--clobber"],
                cwd=PROJECT_ROOT,
                check=True,
            )
            apks = list(work_dir.glob("*.apk"))
            if apks:
                _log(f"下载到 APK: {apks[0]} ({apks[0].stat().st_size} bytes)")
                return apks[0]
            raise RuntimeError("下载完成但目录中未找到 APK 文件")
        except Exception as e:
            last_err = e
            wait = 10 * attempt
            _log(f"下载 release 失败 (attempt {attempt}/3): {e}; 等 {wait}s 重试")
            time.sleep(wait)
    assert last_err is not None
    raise last_err


def rename_apk(src: Path, version_tag: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand_hex = "".join(random.choice("0123456789abcdef") for _ in range(4))
    new_name = f"app_prd443_{ts}_{rand_hex}.apk"
    dst = src.parent / new_name
    shutil.copy2(src, dst)
    _log(f"重命名 APK: {src.name} -> {dst.name}")
    return dst


# ====================== 上传到部署服务器 ======================
def upload_apk_via_sftp(local_path: Path, remote_filename: str) -> str:
    """直接 SFTP 写入 /home/ubuntu/{DEPLOY_ID}/static/apk/（属主就是 ubuntu）。"""
    final_remote = f"{REMOTE_APK_DIR}/{remote_filename}"
    _log(f"SFTP 上传 {local_path} -> {SSH_HOST}:{final_remote}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS, timeout=60)
    try:
        stdin, stdout, stderr = client.exec_command(
            f"mkdir -p {REMOTE_APK_DIR} && ls -ld {REMOTE_APK_DIR}", timeout=30
        )
        out = stdout.read().decode(errors="replace").strip()
        if out:
            _log(f"  | {out}")

        sftp = client.open_sftp()
        try:
            sftp.put(str(local_path), final_remote)
            st = sftp.stat(final_remote)
            _log(f"  上传完成, 远端大小 = {st.st_size} bytes")
            sftp.chmod(final_remote, 0o644)
        finally:
            sftp.close()
    finally:
        client.close()
    return final_remote


# ====================== HTTP 验证 ======================
def verify_http(url: str) -> tuple[int, int]:
    _log(f"HTTP HEAD/GET 验证: {url}")
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=60) as resp:
                code = resp.getcode()
                clen_hdr = resp.headers.get("Content-Length")
                if clen_hdr:
                    size = int(clen_hdr)
                    _ = resp.read(1024)
                else:
                    body = resp.read()
                    size = len(body)
                _log(f"  HTTP {code}, size={size} bytes")
                return code, size
        except Exception as e:
            last_err = e
            _log(f"  验证失败 (attempt {attempt}/3): {e}")
            time.sleep(5 * attempt)
    assert last_err is not None
    raise last_err


# ====================== 主流程 ======================
def main() -> int:
    try:
        if LOG_PATH.exists():
            LOG_PATH.unlink()
    except Exception:
        pass

    summary: dict = {
        "version_tag": None,
        "run_id": None,
        "release_url": None,
        "apk_filename": None,
        "download_url": None,
        "http_status": None,
        "byte_size": None,
        "error": None,
    }

    try:
        _log("=" * 70)
        _log("PRD-443 Android APK 打包子 Agent 启动")
        _log("=" * 70)

        version_tag = gen_version_tag()
        summary["version_tag"] = version_tag
        _log(f"版本标签: {version_tag}")

        trigger_workflow(version_tag)

        run_id = get_latest_run_id()
        summary["run_id"] = run_id

        conclusion = poll_run(run_id)
        if conclusion != "success":
            raise RuntimeError(f"GitHub Actions 构建未成功: conclusion={conclusion}")

        release_url = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{version_tag}"
        summary["release_url"] = release_url

        work_dir = PROJECT_ROOT / "_prd443_android_dl"
        downloaded = download_release_apk(version_tag, work_dir)

        renamed = rename_apk(downloaded, version_tag)
        summary["apk_filename"] = renamed.name

        upload_apk_via_sftp(renamed, renamed.name)

        download_url = f"{BASE_URL}/apk/{renamed.name}"
        summary["download_url"] = download_url
        time.sleep(3)
        code, size = verify_http(download_url)
        summary["http_status"] = code
        summary["byte_size"] = size
        if code != 200:
            raise RuntimeError(f"下载链接不可达: HTTP {code}")

        _log("=" * 70)
        _log("最终结果:")
        for k, v in summary.items():
            _log(f"  {k}: {v}")
        _log("=" * 70)

        _log("SUMMARY_JSON: " + json.dumps(summary, ensure_ascii=False))
        return 0

    except Exception as e:
        summary["error"] = str(e)
        _log(f"ERROR: {e}")
        _log("SUMMARY_JSON: " + json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
