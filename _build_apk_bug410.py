# -*- coding: utf-8 -*-
"""[BUG-410 阶段4-B] 通过 GitHub Actions 远程构建 Flutter Android APK，
然后下载并 SFTP 上传到部署服务器，最后 HEAD 验证。"""
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

# ====== 配置 ======
REPO_DIR = r"C:\auto_output\bnbbaijkgj"
GH_REPO = "ankun-eric/auto_dev_bnbbaijkgj"
GH_TOKEN = "${GH_TOKEN_PLACEHOLDER}"
WORKFLOW_FILE = "android-build.yml"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

POLL_INTERVAL = 30
POLL_TIMEOUT = 30 * 60

LOG_PATH = os.path.join(REPO_DIR, "_build_apk_bug410.log")

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


def run(cmd, check=True, timeout=120, env_extra=None):
    """运行命令，stdout/stderr 一并捕获。"""
    env = os.environ.copy()
    env["GH_TOKEN"] = GH_TOKEN
    if env_extra:
        env.update(env_extra)
    log(f"$ {cmd}")
    proc = subprocess.run(
        cmd, shell=True, cwd=REPO_DIR, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if out.strip():
        for ln in out.strip().splitlines()[-30:]:
            log(f"  | {ln}")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed (rc={proc.returncode}): {cmd}\n{out}")
    return proc.returncode, out


def make_version_tag():
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    h = secrets.token_hex(2)
    return f"android-bug410-v{now}-{h}"


def trigger_workflow(version):
    last_err = None
    for attempt in range(3):
        try:
            run(f"gh workflow run {WORKFLOW_FILE} -R {GH_REPO} -f version={version} --ref master")
            log(f"[trigger] workflow dispatched, version={version}")
            return
        except Exception as e:
            last_err = e
            wait = 10 * (2 ** attempt)
            log(f"[trigger] attempt {attempt+1} failed: {e}; sleeping {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"trigger_workflow failed after retries: {last_err}")


def get_latest_run_id(version):
    """trigger 后最新 run id 应是为该 version 触发的；用 list + 校验 displayTitle/headBranch。"""
    rc, out = run(
        f"gh run list -R {GH_REPO} --workflow={WORKFLOW_FILE} --limit 5 "
        f"--json databaseId,status,conclusion,createdAt,displayTitle,event,headBranch",
        timeout=60,
    )
    runs = json.loads(out.strip().splitlines()[-1] if False else _last_json(out))
    if not runs:
        return None
    runs.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    for r in runs:
        if r.get("event") == "workflow_dispatch":
            return r["databaseId"]
    return runs[0]["databaseId"]


def _last_json(text):
    """从命令混合输出里提取最后一段 JSON（行首是 [ 或 {）。"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].lstrip()
        if s.startswith("[") or s.startswith("{"):
            return "\n".join(lines[i:])
    return text


def poll_run(run_id):
    """返回 conclusion: success/failure/cancelled/timed_out 或 None(超时)。"""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        try:
            rc, out = run(
                f"gh run view {run_id} -R {GH_REPO} --json status,conclusion,url",
                timeout=60, check=False,
            )
            data = json.loads(_last_json(out))
            status = data.get("status")
            conclusion = data.get("conclusion")
            url = data.get("url", "")
            log(f"[poll] run {run_id} status={status} conclusion={conclusion} url={url}")
            if status == "completed":
                return conclusion, url
        except Exception as e:
            log(f"[poll] error: {e}")
        time.sleep(POLL_INTERVAL)
    return None, None


def get_run_url(run_id):
    try:
        rc, out = run(
            f"gh run view {run_id} -R {GH_REPO} --json url",
            timeout=30, check=False,
        )
        return json.loads(_last_json(out)).get("url", "")
    except Exception:
        return ""


def fetch_failure_log(run_id):
    try:
        rc, out = run(
            f"gh run view {run_id} -R {GH_REPO} --log-failed",
            timeout=180, check=False,
        )
        return out[-4000:]
    except Exception as e:
        return f"(failed to fetch log: {e})"


def download_apk(version, dest_dir):
    """release 资产名称是 bini_health_<version>.apk。"""
    expected = f"bini_health_{version}.apk"
    deadline = time.time() + 300
    while time.time() < deadline:
        rc, out = run(
            f"gh release download {version} -R {GH_REPO} --pattern \"*.apk\" --dir \"{dest_dir}\" --clobber",
            timeout=600, check=False,
        )
        if rc == 0:
            break
        log("[download] release not ready yet, retry in 15s")
        time.sleep(15)
    else:
        raise RuntimeError("release download timed out")

    files = [f for f in os.listdir(dest_dir) if f.lower().endswith(".apk")]
    if not files:
        raise RuntimeError("no APK in downloaded release")
    src = os.path.join(dest_dir, files[0])
    log(f"[download] got {src} ({os.path.getsize(src)} bytes)")
    return src, expected


def make_remote_filename():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    h = secrets.token_hex(2)
    return f"app_bug410_{ts}_{h}.apk"


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
        log(f"[verify] HTTPError {e.code} for {url}")
        return e.code, None
    except Exception as e:
        log(f"[verify] error: {e}")
        return -1, None


def main():
    started_at = time.time()
    log("=" * 60)
    log("[bug410] starting Android APK remote build & upload pipeline")

    version = make_version_tag()
    log(f"[bug410] version tag: {version}")

    trigger_workflow(version)

    time.sleep(8)
    run_id = None
    for _ in range(6):
        run_id = get_latest_run_id(version)
        if run_id:
            break
        time.sleep(5)
    if not run_id:
        raise RuntimeError("could not find new workflow run")
    run_url = get_run_url(run_id)
    log(f"[bug410] run id={run_id} url={run_url}")

    conclusion, run_url2 = poll_run(run_id)
    run_url = run_url2 or run_url
    if conclusion is None:
        raise RuntimeError(f"workflow timed out, run url: {run_url}")
    if conclusion != "success":
        tail = fetch_failure_log(run_id)
        raise RuntimeError(
            f"workflow conclusion={conclusion}, run url: {run_url}\n"
            f"--- failure log tail ---\n{tail}"
        )

    log(f"[bug410] workflow succeeded; downloading release {version}")
    tmp_dir = tempfile.mkdtemp(prefix="apk_bug410_")
    src_apk, expected_name = download_apk(version, tmp_dir)
    apk_size = os.path.getsize(src_apk)

    remote_name = make_remote_filename()
    log(f"[bug410] uploading as {remote_name}")
    sftp_upload(src_apk, remote_name)

    download_url = f"{BASE_URL}/apk/{remote_name}"
    code, length = verify_download(download_url)
    if code != 200:
        raise RuntimeError(f"HEAD verify failed code={code} url={download_url}")

    elapsed = int(time.time() - started_at)
    log("=" * 60)
    log("[bug410] SUCCESS")
    log(f"  APK_VERSION_TAG = {version}")
    log(f"  APK_FILENAME    = {remote_name}")
    log(f"  APK_SIZE        = {apk_size} bytes")
    log(f"  APK_HTTP_STATUS = {code}")
    log(f"  APK_DOWNLOAD_URL= {download_url}")
    log(f"  GH_RUN_URL      = {run_url}")
    log(f"  ELAPSED_SECONDS = {elapsed}")
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
        log(f"[bug410] FAILED: {e}")
        sys.exit(2)
