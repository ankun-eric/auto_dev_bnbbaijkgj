"""Build Android APK for drawer-v1.2 via GitHub Actions, download, upload, verify.

Pipeline:
  1. Generate unique version tag android-v<YYYYMMDD-HHMMSS>-<4hex>
  2. gh workflow run android-build.yml -f version=<tag>  (3 retries 10/20/40s)
  3. Wait for the new run, poll every 30s (max 30 min)
  4. gh release download <tag> --pattern *.apk
  5. Rename to app_<YYYYMMDD_HHMMSS>_<4hex>.apk
  6. paramiko SFTP -> /home/ubuntu/<id>/<name>.apk
  7. curl -I verify HTTP 200 at https://<base>/<name>.apk
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

import paramiko

PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
APK_TMP = PROJECT_ROOT / "_apk_download_drawer_v12"
WORKFLOW_FILE = "android-build.yml"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

POLL_INTERVAL = 30
POLL_MAX_MINUTES = 30


def log(msg: str) -> None:
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def retry(cmd_list, max_retries=3, base_delay=10, timeout=300, cwd=None):
    last = None
    delay = base_delay
    for i in range(max_retries):
        try:
            r = subprocess.run(
                cmd_list, capture_output=True, text=True,
                timeout=timeout, cwd=cwd,
                encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            log(f"  retry {i+1}/{max_retries} timeout; sleep {delay}s")
            time.sleep(delay); delay *= 2; last = e; continue
        if r.returncode == 0:
            return r
        last = r
        msg = ((r.stderr or "") + (r.stdout or "")).strip()[:300]
        log(f"  retry {i+1}/{max_retries} rc={r.returncode}: {msg}")
        if i + 1 < max_retries:
            time.sleep(delay); delay *= 2
    if isinstance(last, subprocess.CompletedProcess):
        raise RuntimeError(
            f"cmd failed: {last.stderr or last.stdout}"
        )
    raise RuntimeError(f"cmd failed: {last}")


def make_tag():
    now = _dt.datetime.now()
    ymd = now.strftime("%Y%m%d")
    hms = now.strftime("%H%M%S")
    hx = secrets.token_hex(2)
    tag = f"android-v{ymd}-{hms}-{hx}"
    return tag, ymd, hms, hx


def trigger_workflow(tag: str):
    log(f"trigger {WORKFLOW_FILE} version={tag}")
    retry(
        ["gh", "workflow", "run", WORKFLOW_FILE,
         "--repo", REPO, "-f", f"version={tag}"],
        max_retries=3, base_delay=10, timeout=90, cwd=str(PROJECT_ROOT),
    )


def wait_new_run(since_ts: float) -> str:
    log("waiting for new run ...")
    for _ in range(30):
        try:
            r = retry(
                ["gh", "run", "list", "--workflow", WORKFLOW_FILE,
                 "--repo", REPO, "--limit", "5",
                 "--json", "databaseId,status,createdAt,event"],
                max_retries=3, base_delay=5, timeout=60,
                cwd=str(PROJECT_ROOT),
            )
            runs = json.loads(r.stdout)
        except Exception as exc:
            log(f"  list err: {exc}"); runs = []
        for run in runs:
            try:
                t = _dt.datetime.strptime(
                    run.get("createdAt", ""), "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=_dt.timezone.utc).timestamp()
            except Exception:
                t = 0
            if t >= since_ts - 5 and run.get("event") == "workflow_dispatch":
                rid = str(run["databaseId"])
                log(f"  new run: id={rid} created={run.get('createdAt')}")
                return rid
        time.sleep(5)
    raise RuntimeError("timed out waiting for new run")


def poll_run(run_id: str):
    deadline = time.time() + POLL_MAX_MINUTES * 60
    last_status = ""
    while time.time() < deadline:
        try:
            r = retry(
                ["gh", "run", "view", run_id, "--repo", REPO,
                 "--json", "status,conclusion"],
                max_retries=3, base_delay=5, timeout=60,
                cwd=str(PROJECT_ROOT),
            )
            info = json.loads(r.stdout)
        except Exception as exc:
            log(f"  view err: {exc}"); info = {}
        status = info.get("status", "")
        conclusion = info.get("conclusion") or ""
        if status != last_status:
            log(f"  run {run_id} status={status} conclusion={conclusion}")
            last_status = status
        if status == "completed":
            return status, conclusion
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"poll timeout > {POLL_MAX_MINUTES} min")


def fetch_fail_log(run_id: str) -> str:
    try:
        r = subprocess.run(
            ["gh", "run", "view", run_id, "--repo", REPO, "--log-failed"],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT), encoding="utf-8", errors="replace",
        )
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as e:
        return f"<fetch log failed: {e}>"


def download_apk(tag: str) -> Path:
    if APK_TMP.exists():
        shutil.rmtree(APK_TMP, ignore_errors=True)
    APK_TMP.mkdir(parents=True, exist_ok=True)
    for i in range(8):
        try:
            r = retry(
                ["gh", "release", "view", tag, "--repo", REPO,
                 "--json", "tagName"],
                max_retries=2, base_delay=5, timeout=45,
                cwd=str(PROJECT_ROOT),
            )
            if tag in r.stdout:
                break
        except Exception:
            pass
        log(f"  release not ready, wait {(i+1)*5}s")
        time.sleep((i + 1) * 5)
    retry(
        ["gh", "release", "download", tag, "--repo", REPO,
         "--pattern", "*.apk", "--dir", str(APK_TMP)],
        max_retries=4, base_delay=15, timeout=600,
        cwd=str(PROJECT_ROOT),
    )
    apks = list(APK_TMP.glob("*.apk"))
    if not apks:
        raise RuntimeError("no apk downloaded")
    return apks[0]


def sftp_put(local: str, remote: str):
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASSWORD)
    try:
        sftp = paramiko.SFTPClient.from_transport(t)
        sftp.put(local, remote)
        try:
            sftp.chmod(remote, 0o644)
        except Exception:
            pass
    finally:
        t.close()


def upload_and_verify(local_apk: Path, new_name: str):
    remote_path = f"{REMOTE_DIR}/{new_name}"
    log(f"SFTP upload -> {remote_path}")
    sftp_put(str(local_apk), remote_path)

    url = f"{BASE_URL}/{new_name}"
    log(f"HTTPS verify HEAD: {url}")
    size = 0
    code_seen = ""
    last_err = None
    for i in range(8):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                code_seen = str(code)
                cl = int(resp.headers.get("Content-Length", "0"))
                log(f"  try{i+1} status={code} content-length={cl}")
                if code == 200 and cl > 1024 * 1024:
                    size = cl
                    break
        except Exception as e:
            last_err = e
            log(f"  try{i+1} err: {e}")
        time.sleep(6)
    if size == 0:
        raise RuntimeError(
            f"HEAD failed (code={code_seen} err={last_err})"
        )
    return url, size, code_seen


def main() -> int:
    log("=== Android APK drawer-v1.2 pipeline start ===")
    start = time.time()
    tag, ymd, hms, hx = make_tag()
    log(f"tag = {tag}")
    release_url = f"https://github.com/{REPO}/releases/tag/{tag}"

    try:
        trigger_ts = time.time()
        trigger_workflow(tag)
        time.sleep(8)
        run_id = wait_new_run(trigger_ts)
        status, conclusion = poll_run(run_id)
        if conclusion != "success":
            tail = fetch_fail_log(run_id)
            log(f"BUILD FAILED conclusion={conclusion}")
            log(tail[-3000:])
            print("\n================ RESULT ================")
            print(json.dumps({
                "success": False, "reason": "build_failed",
                "tag": tag, "run_id": run_id,
                "release_page": release_url,
                "conclusion": conclusion,
            }, ensure_ascii=False, indent=2))
            return 1
        log(f"build OK run={run_id}")

        apk_local = download_apk(tag)
        new_name = f"app_{ymd}_{hms}_{hx}.apk"
        renamed = APK_TMP / new_name
        shutil.move(str(apk_local), str(renamed))
        log(f"local: {renamed.name} size={renamed.stat().st_size}")

        url, size, http_code = upload_and_verify(renamed, new_name)
        result = {
            "success": True,
            "apk_name": new_name,
            "download_url": url,
            "file_size_bytes": size,
            "file_size_mb": round(size / 1024 / 1024, 2),
            "http_status": http_code,
            "release_page": release_url,
            "tag": tag,
            "run_id": run_id,
            "elapsed_sec": int(time.time() - start),
        }
        print("\n================ RESULT ================")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("========================================")
        print(f"DOWNLOAD_URL={url}")
        return 0
    except Exception as exc:
        import traceback
        log(f"FATAL: {exc}")
        traceback.print_exc()
        print("\n================ RESULT ================")
        print(json.dumps({
            "success": False, "reason": "exception",
            "error": str(exc), "tag": tag,
            "release_page": release_url,
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
