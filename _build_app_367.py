"""Bug 367 Android + iOS 并行打包脚本（基于历史 _android_build_363.log / _ios_build_363.log 模式）。

流程：
1. 触发 GitHub Actions 工作流
2. 轮询 run 状态
3. 下载产物（APK/IPA）
4. SFTP 上传到部署服务器（仅 APK，IPA 留在 Release）
5. HTTP 验证可访问
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SERVER_HOST = "newbb.test.bangbangvip.com"
SERVER_USER = "ubuntu"
SERVER_PASS = "Newbang888"
APK_REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"
APK_BASE_URL = f"https://{SERVER_HOST}/autodev/{DEPLOY_ID}/apk"


def run(cmd, capture=True, timeout=300):
    print(f"[run] {cmd}", flush=True)
    proc = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    if proc.stdout:
        print(proc.stdout, flush=True)
    if proc.stderr:
        print(f"[stderr] {proc.stderr}", flush=True)
    return proc


def trigger_workflow(workflow, version):
    proc = run(f"gh workflow run {workflow} -R {REPO} --ref master -f version={version}")
    if proc.returncode != 0:
        raise RuntimeError(f"trigger {workflow} failed")


def find_run_id(workflow, version, max_wait=60):
    """find latest run for given version tag (best-effort by displayTitle/createdAt)."""
    for _ in range(max_wait // 3):
        proc = run(
            f"gh run list -R {REPO} --workflow {workflow} --limit 5 --json databaseId,displayTitle,headBranch,status,conclusion,createdAt,event"
        )
        try:
            data = json.loads(proc.stdout)
        except Exception:
            data = []
        if data:
            return data[0]["databaseId"]
        time.sleep(3)
    raise RuntimeError(f"cannot find run for {workflow}")


def poll_run(run_id, max_minutes=30):
    deadline = time.time() + max_minutes * 60
    while time.time() < deadline:
        proc = run(
            f"gh run view {run_id} -R {REPO} --json status,conclusion,databaseId,displayTitle"
        )
        data = json.loads(proc.stdout) if proc.stdout else {}
        st = data.get("status")
        cc = data.get("conclusion")
        print(f"[poll] run={run_id} status={st} conclusion={cc}", flush=True)
        if st == "completed":
            return cc
        time.sleep(20)
    raise TimeoutError(f"run {run_id} not completed in {max_minutes}min")


def download_release(tag, pattern, outdir):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    proc = run(f"gh release download {tag} -R {REPO} --pattern {pattern} --dir {outdir} --clobber")
    if proc.returncode != 0:
        raise RuntimeError(f"download release {tag} failed")
    return list(Path(outdir).glob(pattern.replace("*", "*")))


def sftp_upload(local_path, remote_path):
    import paramiko

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, timeout=30)
    try:
        sftp = cli.open_sftp()
        try:
            cli.exec_command(f"mkdir -p {os.path.dirname(remote_path)}")
            sftp.put(local_path, remote_path)
            print(f"[sftp] uploaded {local_path} -> {remote_path}", flush=True)
        finally:
            sftp.close()
    finally:
        cli.close()


def http_verify(url):
    import urllib.request

    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[http] {url} -> {resp.status}", flush=True)
            return resp.status == 200
    except Exception as e:
        print(f"[http] {url} -> {e}", flush=True)
        return False


def build_android(result):
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        version = f"android-bug367-v{ts}"
        print(f"\n=== ANDROID build version={version} ===", flush=True)
        trigger_workflow("android-build.yml", version)
        run_id = find_run_id("android-build.yml", version)
        cc = poll_run(run_id, max_minutes=30)
        if cc != "success":
            result["android"] = {"ok": False, "error": f"build conclusion={cc}", "run_id": run_id}
            return
        outdir = f"_apk_download_367"
        files = download_release(version, "*.apk", outdir)
        if not files:
            result["android"] = {"ok": False, "error": "no apk", "run_id": run_id}
            return
        apk = files[0]
        ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"bini_health_android_bug367_{ts2}.apk"
        renamed = apk.parent / new_name
        apk.rename(renamed)
        remote_path = f"{APK_REMOTE_DIR}/{new_name}"
        sftp_upload(str(renamed), remote_path)
        url = f"{APK_BASE_URL}/{new_name}"
        ok = http_verify(url)
        result["android"] = {
            "ok": ok,
            "version": version,
            "run_id": run_id,
            "filename": new_name,
            "size": renamed.stat().st_size,
            "url": url,
        }
    except Exception as e:
        result["android"] = {"ok": False, "error": str(e)}


def build_ios(result):
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        version = f"ios-bug367-v{ts}"
        print(f"\n=== IOS build version={version} ===", flush=True)
        trigger_workflow("ios-build.yml", version)
        run_id = find_run_id("ios-build.yml", version)
        cc = poll_run(run_id, max_minutes=45)
        if cc != "success":
            result["ios"] = {"ok": False, "error": f"build conclusion={cc}", "run_id": run_id}
            return
        release_page = f"https://github.com/{REPO}/releases/tag/{version}"
        ipa_url = f"https://github.com/{REPO}/releases/download/{version}/bini_health_ios.ipa"
        result["ios"] = {
            "ok": True,
            "version": version,
            "run_id": run_id,
            "release_page": release_page,
            "ipa_url": ipa_url,
        }
    except Exception as e:
        result["ios"] = {"ok": False, "error": str(e)}


def main():
    result = {}
    threads = [
        threading.Thread(target=build_android, args=(result,), name="android"),
        threading.Thread(target=build_ios, args=(result,), name="ios"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("\n\n=================================", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print("=================================", flush=True)


if __name__ == "__main__":
    main()
