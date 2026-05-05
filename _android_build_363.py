"""
子 Agent B：Android APK 通过 GitHub Actions 远程构建并上传到测试服务器。
触发 workflow → 轮询 → 下载 release APK → SFTP 上传 → HTTP 验证。
"""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import secrets
import datetime
import urllib.request
import urllib.error
from pathlib import Path

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "android-build.yml"
COMMIT = "7eaa1a23395b9db8c8c4cf69631af7bc33000235"
BRANCH = "master"
PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")

SERVER_HOST = "newbb.test.bangbangvip.com"
SERVER_USER = "ubuntu"
SERVER_PASS = "Newbang888"
SERVER_APK_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def now_hms() -> str:
    return datetime.datetime.now().strftime("%H%M%S")


def now_hmd() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def run_cmd(args, check=True, capture=True, timeout=120, cwd=None, env=None) -> subprocess.CompletedProcess:
    print(f"[run] {' '.join(args)}")
    return subprocess.run(
        args,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
        encoding="utf-8",
        errors="replace",
    )


def retry(callable_fn, max_attempts=3, base_delay=10, label=""):
    delay = base_delay
    last_err = None
    for n in range(1, max_attempts + 1):
        try:
            return callable_fn()
        except Exception as e:  # noqa
            last_err = e
            print(f"[retry:{label}] 第 {n}/{max_attempts} 次失败: {e}")
            if n < max_attempts:
                print(f"[retry:{label}] {delay}s 后重试...")
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"retry exhausted ({label}): {last_err}")


def gh(args, timeout=120) -> str:
    full = ["gh"] + args
    res = run_cmd(full, check=False, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"gh failed rc={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}")
    return res.stdout


def trigger_workflow(version: str) -> None:
    def _do():
        gh([
            "workflow", "run", WORKFLOW,
            "-R", REPO,
            "--ref", BRANCH,
            "-f", f"version={version}",
        ])
    retry(_do, label="workflow_run")


def find_run_id(version: str, timeout_s: int = 120) -> str:
    """触发后等待 run 出现，返回 run id"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = gh([
                "run", "list",
                "-R", REPO,
                "--workflow", WORKFLOW,
                "--limit", "10",
                "--json", "databaseId,displayTitle,headBranch,status,conclusion,createdAt,event",
            ])
            runs = json.loads(out)
            for r in runs:
                if r.get("event") == "workflow_dispatch":
                    return str(r["databaseId"])
        except Exception as e:
            print(f"[find_run_id] {e}")
        time.sleep(5)
    raise RuntimeError("未在 120s 内找到 workflow_dispatch 触发的 run")


def poll_run(run_id: str, max_minutes: int = 30) -> str:
    """返回 conclusion: success/failure/cancelled/timed_out"""
    deadline = time.time() + max_minutes * 60
    while time.time() < deadline:
        try:
            out = gh([
                "run", "view", run_id,
                "-R", REPO,
                "--json", "status,conclusion,databaseId,displayTitle",
            ])
            data = json.loads(out)
            status = data.get("status")
            concl = data.get("conclusion")
            print(f"[poll] run={run_id} status={status} conclusion={concl}")
            if status == "completed":
                return concl or "unknown"
        except Exception as e:
            print(f"[poll] {e}")
        time.sleep(30)
    raise RuntimeError(f"run {run_id} 30 分钟未完成")


def fetch_failed_log(run_id: str) -> str:
    try:
        res = run_cmd(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"], check=False, timeout=120)
        return (res.stdout or "")[-4000:] + "\n[stderr]\n" + (res.stderr or "")[-1000:]
    except Exception as e:
        return f"<fetch failed log error: {e}>"


def download_release_apk(version: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    def _do():
        gh([
            "release", "download", version,
            "-R", REPO,
            "--pattern", "*.apk",
            "--dir", str(dest_dir),
            "--clobber",
        ], timeout=600)
    retry(_do, label="release_download", base_delay=15)
    apks = list(dest_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError(f"release {version} 下载后未在 {dest_dir} 找到 .apk")
    apks.sort(key=lambda p: p.stat().st_size, reverse=True)
    return apks[0]


def sftp_upload(local: Path, remote_path: str) -> None:
    import paramiko
    print(f"[sftp] upload {local} -> {SERVER_USER}@{SERVER_HOST}:{remote_path}")
    transport = paramiko.Transport((SERVER_HOST, 22))
    transport.connect(username=SERVER_USER, password=SERVER_PASS)
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            remote_dir = remote_path.rsplit("/", 1)[0]
            try:
                sftp.stat(remote_dir)
            except IOError:
                parts = remote_dir.strip("/").split("/")
                cur = ""
                for p in parts:
                    cur += "/" + p
                    try:
                        sftp.stat(cur)
                    except IOError:
                        sftp.mkdir(cur)
            sftp.put(str(local), remote_path)
            try:
                sftp.chmod(remote_path, 0o644)
            except Exception:
                pass
            size = sftp.stat(remote_path).st_size
            print(f"[sftp] uploaded size={size}")
        finally:
            sftp.close()
    finally:
        transport.close()


def http_check(url: str, attempts: int = 5) -> int:
    last = None
    delay = 5
    for n in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                print(f"[http] {url} -> {code}")
                if code == 200:
                    return code
                last = code
        except urllib.error.HTTPError as e:
            print(f"[http] HTTPError {e.code} attempt {n}")
            last = e.code
        except Exception as e:
            print(f"[http] err attempt {n}: {e}")
            last = -1
        if n < attempts:
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(f"http_check failed url={url} last={last}")


def main():
    hms = now_hms()
    rand_hex = secrets.token_hex(2)
    version = f"android-login-layout-v20260506-{hms}-{rand_hex}"
    print(f"[main] version tag = {version}")
    print(f"[main] commit = {COMMIT}")

    print("[main] === step 1: trigger workflow ===")
    trigger_workflow(version)

    print("[main] === step 2: find run id ===")
    time.sleep(8)
    run_id = find_run_id(version)
    print(f"[main] run_id = {run_id}")

    print("[main] === step 3: poll run ===")
    concl = poll_run(run_id, max_minutes=30)
    print(f"[main] first run conclusion = {concl}")

    if concl != "success":
        log = fetch_failed_log(run_id)
        print("[main] FAILED LOG (tail):\n" + log)
        # 简单重试：再触发一次同 version+_retry
        retry_version = version + "-r1"
        print(f"[main] retrying with {retry_version}")
        trigger_workflow(retry_version)
        time.sleep(8)
        run_id2 = find_run_id(retry_version)
        concl2 = poll_run(run_id2, max_minutes=30)
        if concl2 != "success":
            log2 = fetch_failed_log(run_id2)
            print("[main] SECOND FAILED LOG (tail):\n" + log2)
            raise SystemExit(
                "ERROR: GitHub Actions 构建连续两次失败。\n"
                f"第一次 run_id={run_id} conclusion={concl}\n"
                f"第二次 run_id={run_id2} conclusion={concl2}\n"
                f"--- 第二次失败日志（尾部） ---\n{log2}"
            )
        version = retry_version

    print("[main] === step 4: download release APK ===")
    download_dir = PROJECT_ROOT / "_apk_download_363"
    apk_local = download_release_apk(version, download_dir)
    print(f"[main] downloaded {apk_local} size={apk_local.stat().st_size}")

    print("[main] === step 5: rename ===")
    final_name = f"bini_health_android_login_layout_{now_hmd()}_{rand_hex}.apk"
    final_local = download_dir / final_name
    if final_local.exists():
        final_local.unlink()
    apk_local.rename(final_local)
    print(f"[main] renamed -> {final_local}")

    print("[main] === step 6: sftp upload ===")
    remote_path = SERVER_APK_DIR + final_name
    def _up():
        sftp_upload(final_local, remote_path)
    retry(_up, max_attempts=3, base_delay=10, label="sftp")

    print("[main] === step 7: http verify ===")
    download_url = f"{BASE_URL}/apk/{final_name}"
    http_check(download_url, attempts=6)

    print("\n=================================")
    print(f"APK_FILENAME={final_name}")
    print(f"APK_DOWNLOAD_URL={download_url}")
    print("=================================\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"\nFATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
