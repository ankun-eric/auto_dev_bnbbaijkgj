# -*- coding: utf-8 -*-
"""[PRD-TIZHI-OPTIM-V1] 通过 GitHub Actions 远程构建 Flutter Android APK，
下载 release 后 SFTP 上传到部署服务器 /apk，HEAD 验证。复用 bug432fix 管线。"""
import os
import sys
import time
import json
import secrets
import datetime
import subprocess
import urllib.request
import urllib.error
import ssl
import tempfile

import paramiko

REPO_DIR = r"C:\auto_output\bnbbaijkgj"
GH_REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "android-build.yml"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

POLL_INTERVAL = 30
POLL_TIMEOUT = 35 * 60

LOG_PATH = os.path.join(REPO_DIR, "_build_apk_tizhi_optim_v1.log")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

_log_fp = None


def log(msg):
    global _log_fp
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if _log_fp is None:
        _log_fp = open(LOG_PATH, "a", encoding="utf-8")
    _log_fp.write(line + "\n")
    _log_fp.flush()


def run(cmd, check=True, timeout=180):
    log(f"$ {cmd}")
    proc = subprocess.run(
        cmd, shell=True, cwd=REPO_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if out.strip():
        for ln in out.strip().splitlines()[-20:]:
            log(f"  | {ln}")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed (rc={proc.returncode}): {cmd}\n{out}")
    return proc.returncode, out


def make_version_tag():
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"android-tizhioptim-v{now}-{secrets.token_hex(2)}"


def trigger_workflow(version):
    last = None
    for attempt in range(3):
        try:
            run(f"gh workflow run {WORKFLOW_FILE} -R {GH_REPO} -f version={version} --ref master")
            log(f"[trigger] dispatched, version={version}")
            return
        except Exception as e:
            last = e
            wait = 10 * (2 ** attempt)
            log(f"[trigger] attempt {attempt+1} failed: {e}; sleep {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"trigger_workflow failed: {last}")


def _last_json(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].lstrip()
        if s.startswith("[") or s.startswith("{"):
            return "\n".join(lines[i:])
    return text


def get_latest_run_id():
    rc, out = run(
        f"gh run list -R {GH_REPO} --workflow={WORKFLOW_FILE} --limit 5 "
        f"--json databaseId,status,conclusion,createdAt,event,headBranch",
        timeout=60,
    )
    runs = json.loads(_last_json(out))
    runs.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    for r in runs:
        if r.get("event") == "workflow_dispatch":
            return r["databaseId"]
    return runs[0]["databaseId"] if runs else None


def get_run_url(run_id):
    try:
        rc, out = run(f"gh run view {run_id} -R {GH_REPO} --json url", timeout=30, check=False)
        return json.loads(_last_json(out)).get("url", "")
    except Exception:
        return ""


def poll_run(run_id):
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        try:
            rc, out = run(
                f"gh run view {run_id} -R {GH_REPO} --json status,conclusion,url",
                timeout=60, check=False,
            )
            data = json.loads(_last_json(out))
            log(f"[poll] {run_id} status={data.get('status')} conclusion={data.get('conclusion')}")
            if data.get("status") == "completed":
                return data.get("conclusion"), data.get("url", "")
        except Exception as e:
            log(f"[poll] err: {e}")
        time.sleep(POLL_INTERVAL)
    return None, None


def fetch_failure_log(run_id):
    try:
        rc, out = run(f"gh run view {run_id} -R {GH_REPO} --log-failed", timeout=180, check=False)
        return out
    except Exception as e:
        return f"(failed: {e})"


def download_apk(version, dest_dir):
    deadline = time.time() + 300
    while time.time() < deadline:
        rc, out = run(
            f"gh release download {version} -R {GH_REPO} --pattern \"*.apk\" --dir \"{dest_dir}\" --clobber",
            timeout=600, check=False,
        )
        if rc == 0:
            break
        log("[download] release not ready, retry in 15s")
        time.sleep(15)
    files = [f for f in os.listdir(dest_dir) if f.lower().endswith(".apk")]
    if not files:
        raise RuntimeError("no APK")
    src = os.path.join(dest_dir, files[0])
    log(f"[download] got {src} ({os.path.getsize(src)} bytes)")
    return src


def make_remote_filename():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"app_tizhioptim_{ts}_{secrets.token_hex(2)}.apk"


def sftp_upload(local_path, remote_name):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        i, o, e = client.exec_command(f"mkdir -p {REMOTE_DIR}")
        o.channel.recv_exit_status()
        sftp = client.open_sftp()
        try:
            remote_path = f"{REMOTE_DIR}/{remote_name}"
            sftp.put(local_path, remote_path)
            attr = sftp.stat(remote_path)
            log(f"[upload] {remote_path} size={attr.st_size}")
            return attr.st_size
        finally:
            sftp.close()
    finally:
        client.close()


def verify_download(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            code = resp.getcode()
            length = resp.headers.get("Content-Length")
            log(f"[verify] HEAD {url} -> {code} length={length}")
            return code, length
    except urllib.error.HTTPError as e:
        log(f"[verify] HTTPError {e.code}")
        return e.code, None
    except Exception as e:
        log(f"[verify] err: {e}")
        return -1, None


def main():
    started = time.time()
    log("=" * 60)
    log("[tizhi-optim] starting Android APK remote build pipeline")
    version = make_version_tag()
    log(f"[tizhi-optim] version: {version}")
    trigger_workflow(version)

    time.sleep(30)
    run_id = None
    for _ in range(6):
        run_id = get_latest_run_id()
        if run_id:
            break
        time.sleep(5)
    if not run_id:
        raise RuntimeError("no run_id")
    run_url = get_run_url(run_id)
    log(f"[tizhi-optim] run id={run_id} url={run_url}")

    conclusion, run_url2 = poll_run(run_id)
    run_url = run_url2 or run_url
    if conclusion is None:
        raise RuntimeError(f"workflow timed out, run url: {run_url}")
    if conclusion != "success":
        tail = fetch_failure_log(run_id)
        log("[tizhi-optim] FAILURE LOG tail:")
        for ln in tail.splitlines()[-60:]:
            log(f"  >> {ln}")
        raise RuntimeError(f"workflow conclusion={conclusion}, url={run_url}")

    log(f"[tizhi-optim] workflow OK; downloading release {version}")
    tmp_dir = tempfile.mkdtemp(prefix="apk_tizhioptim_")
    src_apk = download_apk(version, tmp_dir)
    apk_size = os.path.getsize(src_apk)

    remote_name = make_remote_filename()
    sftp_upload(src_apk, remote_name)

    download_url = f"{BASE_URL}/apk/{remote_name}"
    code, length = verify_download(download_url)
    if code != 200:
        raise RuntimeError(f"HEAD verify failed code={code} url={download_url}")

    elapsed = int(time.time() - started)
    print("=" * 60)
    print(f"APK_VERSION_TAG={version}")
    print(f"APK_FILENAME={remote_name}")
    print(f"APK_SIZE={apk_size}")
    print(f"APK_HTTP_STATUS={code}")
    print(f"APK_DOWNLOAD_URL={download_url}")
    print(f"GH_RUN_URL={run_url}")
    print(f"ELAPSED_SECONDS={elapsed}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[tizhi-optim] FAILED: {e}")
        sys.exit(2)
