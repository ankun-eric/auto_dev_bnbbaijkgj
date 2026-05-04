#!/usr/bin/env python3
"""End-to-end iOS IPA packaging for checkout slot-grid feature.

Steps:
  1. Generate version tag.
  2. Trigger GitHub Actions workflow `ios-build.yml`.
  3. Poll until run completes (up to 45 minutes for macOS build).
  4. Download IPA from the GitHub release.
  5. SFTP upload to deploy server static ipa dir.
  6. Validate HTTPS download URL.
"""
import json
import os
import random
import string
import subprocess
import sys
import time
import urllib.request
import urllib.error

import paramiko

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
SERVER_IPA_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/ipa"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipa_download")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_WAIT_SEC = 45 * 60
POLL_INTERVAL = 30


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def retry_run(args, max_retries=3, retry_delay=10, timeout=120, check_json=False):
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            log(f"  attempt {attempt}/{max_retries}: {' '.join(args)}")
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                if check_json:
                    try:
                        return json.loads(r.stdout)
                    except Exception as e:
                        last_err = f"json parse: {e}; stdout={r.stdout[:200]}"
                else:
                    return r.stdout
            else:
                last_err = f"rc={r.returncode} stderr={r.stderr.strip()[:300]}"
                log(f"    failed: {last_err}")
        except Exception as e:
            last_err = f"exception: {e}"
            log(f"    exception: {e}")
        if attempt < max_retries:
            time.sleep(retry_delay)
            retry_delay *= 2
    raise RuntimeError(f"command failed after {max_retries} retries: {args}; last_err={last_err}")


def gen_tag_and_filename():
    ts_full = time.strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.hexdigits.lower()[:16], k=4))
    tag = f"ios-slotgrid-v{ts_full}-{suffix}"
    ts_under = time.strftime("%Y%m%d_%H%M%S")
    fname = f"bini_health_slotgrid_{ts_under}_{suffix}.ipa"
    return tag, fname


def trigger_workflow(tag):
    log(f"Triggering workflow {WORKFLOW} with version={tag}")
    retry_run([
        "gh", "workflow", "run", WORKFLOW,
        "--repo", REPO,
        "-f", f"version={tag}",
    ])
    log("  triggered. waiting 8s for run to register ...")
    time.sleep(8)


def find_run_id(tag):
    for attempt in range(6):
        out = retry_run([
            "gh", "run", "list",
            "--repo", REPO,
            "--workflow", WORKFLOW,
            "--limit", "10",
            "--json", "databaseId,displayTitle,status,conclusion,createdAt,headBranch",
        ], check_json=True)
        if out:
            for run in out:
                if run.get("status") in ("queued", "in_progress", "completed"):
                    return run["databaseId"]
        time.sleep(5)
    raise RuntimeError("Could not find run id after triggering workflow")


def poll_run(run_id):
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        if elapsed > MAX_WAIT_SEC:
            raise RuntimeError(f"TIMEOUT after {elapsed}s")
        try:
            data = retry_run([
                "gh", "run", "view", str(run_id),
                "--repo", REPO,
                "--json", "status,conclusion,displayTitle,url",
            ], check_json=True)
        except Exception as e:
            log(f"[{elapsed}s] poll error: {e}")
            time.sleep(POLL_INTERVAL)
            continue
        status = data.get("status", "?")
        conclusion = data.get("conclusion") or ""
        log(f"[{elapsed}s] run {run_id}: status={status} conclusion={conclusion}")
        if status == "completed":
            if conclusion == "success":
                return data
            raise RuntimeError(f"BUILD FAILED conclusion={conclusion} url={data.get('url')}")
        time.sleep(POLL_INTERVAL)


def download_ipa(tag):
    log(f"Downloading IPA for release tag {tag} -> {DOWNLOAD_DIR}")
    last_err = ""
    for attempt in range(1, 4):
        try:
            r = subprocess.run([
                "gh", "release", "download", tag,
                "--repo", REPO,
                "--pattern", "*.ipa",
                "--dir", DOWNLOAD_DIR,
                "--clobber",
            ], capture_output=True, text=True, timeout=900)
            if r.returncode == 0:
                break
            last_err = r.stderr.strip()[:300]
            log(f"  attempt {attempt} failed: {last_err}")
        except Exception as e:
            last_err = str(e)
            log(f"  attempt {attempt} exception: {e}")
        if attempt < 3:
            time.sleep(15 * attempt)
    else:
        raise RuntimeError(f"gh release download failed after 3 retries: {last_err}")
    ipas = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".ipa")]
    ipas.sort(key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f)), reverse=True)
    if not ipas:
        raise RuntimeError(f"No IPA file downloaded into {DOWNLOAD_DIR}")
    local_path = os.path.join(DOWNLOAD_DIR, ipas[0])
    size = os.path.getsize(local_path)
    log(f"  downloaded: {local_path} ({size} bytes)")
    return local_path, size


def sftp_upload(local_path, remote_filename):
    remote_tmp = f"/tmp/{remote_filename}"
    remote_final = f"{SERVER_IPA_DIR}/{remote_filename}"
    log(f"SSH connect {SSH_USER}@{SSH_HOST}:{SSH_PORT}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS,
                   timeout=60, banner_timeout=60, auth_timeout=60)
    try:
        sftp = client.open_sftp()
        log(f"  ensuring dir {SERVER_IPA_DIR}")
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {SERVER_IPA_DIR} && ls -ld {SERVER_IPA_DIR}")
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        log(f"    mkdir rc={rc} out={out.strip()} err={err.strip()}")

        log(f"  SFTP put -> {remote_tmp}")
        sftp.put(local_path, remote_tmp)
        st = sftp.stat(remote_tmp)
        log(f"    uploaded {st.st_size} bytes")

        log(f"  mv -> {remote_final}")
        cmd = f"mv {remote_tmp} {remote_final} && chmod 644 {remote_final} && ls -la {remote_final}"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        log(f"    rc={rc}\n    out={out.strip()}\n    err={err.strip()}")
        if rc != 0:
            raise RuntimeError(f"server-side mv failed rc={rc} err={err}")
        sftp.close()
    finally:
        client.close()
    return remote_final


def verify_url(url):
    log(f"Verifying HTTP {url}")
    last_err = ""
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                length = resp.headers.get("Content-Length", "?")
                log(f"  attempt {attempt}: HTTP {code} length={length}")
                if code == 200:
                    return True, int(length) if length and length.isdigit() else None
                last_err = f"HTTP {code}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTPError {e.code}"
            log(f"  attempt {attempt}: {last_err}")
        except Exception as e:
            last_err = f"{e}"
            log(f"  attempt {attempt}: {last_err}")
        time.sleep(5 * attempt)
    raise RuntimeError(f"URL verify failed after retries: {last_err}")


def main():
    tag, server_fname = gen_tag_and_filename()
    log(f"VERSION TAG: {tag}")
    log(f"SERVER FILENAME: {server_fname}")

    trigger_workflow(tag)
    run_id = find_run_id(tag)
    log(f"RUN ID: {run_id}")

    run_data = poll_run(run_id)
    log(f"BUILD SUCCESS: {run_data.get('url')}")

    local_ipa, size = download_ipa(tag)

    remote_path = sftp_upload(local_ipa, server_fname)

    download_url = f"{BASE_URL}/ipa/{server_fname}"
    ok, remote_size = verify_url(download_url)

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"VERSION_TAG    : {tag}")
    print(f"RUN_ID         : {run_id}")
    print(f"RUN_URL        : {run_data.get('url')}")
    print(f"CONCLUSION     : {run_data.get('conclusion')}")
    print(f"LOCAL_IPA      : {local_ipa}")
    print(f"REMOTE_PATH    : {remote_path}")
    print(f"DOWNLOAD_URL   : {download_url}")
    print(f"FILE_SIZE      : {size} bytes")
    print(f"HTTP_STATUS    : 200 (verified)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
