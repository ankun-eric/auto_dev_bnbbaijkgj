"""Build Android APK via GitHub Actions, download, upload to deploy server, verify.

Pipeline:
  1. Generate unique version tag android-promptcfg-v<ts>-<4hex>
  2. gh workflow run android-build.yml -f version=<tag>  (3 retries)
  3. Wait for the new run, poll every 30s (max 30 min)
  4. gh release download <tag> --pattern *.apk
  5. Rename to app_promptcfg_<ymd>_<hms>_<hex>.apk
  6. SCP to /home/ubuntu/<id>/static/  (root, served at /autodev/<id>/<name>.apk)
     Also mirror to /home/ubuntu/<id>/uploads/static/ per task spec.
  7. HTTPS HEAD verify 200 at the root-level URL.
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
import paramiko  # noqa: E402

# ---- constants ---------------------------------------------------------------
PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
DEPLOY_DIR = PROJECT_ROOT / "deploy"
APK_TMP = DEPLOY_DIR / "_apk_promptcfg_tmp"
WORKFLOW_FILE = "android-build.yml"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# nginx serves /home/ubuntu/<id>/static/<file>.apk at /autodev/<id>/<file>.apk
PRIMARY_REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static"
# per task description (mirror only; backend doesn't expose /uploads/static/)
MIRROR_REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/uploads/static"

BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

POLL_INTERVAL = 30
POLL_MAX_MINUTES = 30
MAX_BUILD_RETRY = 1  # one rebuild on failure


def log(msg: str) -> None:
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def retry(cmd_list, max_retries: int = 3, base_delay: int = 10,
          timeout: int = 300, cwd: str | None = None):
    """Run a command up to max_retries times with exponential backoff (10s/20s/40s)."""
    last = None
    delay = base_delay
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
            log(f"  retry {i+1}/{max_retries} timeout: {e}; sleep {delay}s")
            time.sleep(delay)
            delay *= 2
            last = e
            continue
        if r.returncode == 0:
            return r
        last = r
        msg = ((r.stderr or "") + (r.stdout or "")).strip()[:200]
        log(f"  retry {i+1}/{max_retries} rc={r.returncode}: {msg}")
        if i + 1 < max_retries:
            time.sleep(delay)
            delay *= 2
    if isinstance(last, subprocess.CompletedProcess):
        raise RuntimeError(
            f"command failed after {max_retries} attempts: {last.stderr or last.stdout}"
        )
    raise RuntimeError(f"command failed after {max_retries} attempts: {last}")


def make_version_tag() -> tuple[str, str, str, str]:
    now = _dt.datetime.now()
    ymd = now.strftime("%Y%m%d")
    hms = now.strftime("%H%M%S")
    hx = secrets.token_hex(2)
    tag = f"android-promptcfg-v{ymd}{hms}-{hx}"
    return tag, ymd, hms, hx


def trigger_workflow(tag: str) -> None:
    log(f"trigger workflow {WORKFLOW_FILE}  version={tag}")
    retry(
        ["gh", "workflow", "run", WORKFLOW_FILE,
         "--repo", REPO, "-f", f"version={tag}"],
        max_retries=3, base_delay=10, timeout=90,
        cwd=str(PROJECT_ROOT),
    )
    log("  workflow_dispatch submitted")


def wait_new_run(since_ts: float) -> str:
    log("waiting for new run to appear ...")
    for attempt in range(24):
        try:
            r = retry(
                ["gh", "run", "list", "--workflow", WORKFLOW_FILE,
                 "--repo", REPO, "--limit", "5",
                 "--json", "databaseId,status,createdAt,event"],
                max_retries=3, base_delay=5, timeout=60, cwd=str(PROJECT_ROOT),
            )
            runs = json.loads(r.stdout)
        except Exception as exc:
            log(f"  list err: {exc}")
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
                log(f"  new run detected: id={rid} created={created}")
                return rid
        time.sleep(5)
    raise RuntimeError("timed out waiting for new run")


def poll_run(run_id: str) -> tuple[str, str]:
    deadline = time.time() + POLL_MAX_MINUTES * 60
    last_status = ""
    while time.time() < deadline:
        try:
            r = retry(
                ["gh", "run", "view", run_id, "--repo", REPO,
                 "--json", "status,conclusion"],
                max_retries=3, base_delay=5, timeout=60, cwd=str(PROJECT_ROOT),
            )
            info = json.loads(r.stdout)
        except Exception as exc:
            log(f"  view err: {exc}; will retry")
            info = {}
        status = info.get("status", "")
        conclusion = info.get("conclusion") or ""
        if status != last_status:
            log(f"  run {run_id} status={status} conclusion={conclusion}")
            last_status = status
        if status == "completed":
            return status, conclusion
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"poll timeout (> {POLL_MAX_MINUTES} min)")


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
    # wait a bit for the release to appear
    for i in range(6):
        try:
            r = retry(
                ["gh", "release", "view", tag, "--repo", REPO,
                 "--json", "tagName"],
                max_retries=2, base_delay=5, timeout=45, cwd=str(PROJECT_ROOT),
            )
            if tag in r.stdout:
                break
        except Exception:
            pass
        log(f"  release not ready yet, wait {(i+1)*5}s")
        time.sleep((i + 1) * 5)
    retry(
        ["gh", "release", "download", tag, "--repo", REPO,
         "--pattern", "*.apk", "--dir", str(APK_TMP)],
        max_retries=4, base_delay=15, timeout=600, cwd=str(PROJECT_ROOT),
    )
    apks = list(APK_TMP.glob("*.apk"))
    if not apks:
        raise RuntimeError("release downloaded but no apk file found")
    return apks[0]


def ssh_client() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20,
              look_for_keys=False, allow_agent=False)
    return c


def ssh_exec(cmd: str, timeout: int = 60) -> tuple[int, str]:
    c = ssh_client()
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        rc = o.channel.recv_exit_status()
        return rc, out + (("\n[STDERR]\n" + err) if err.strip() else "")
    finally:
        c.close()


def sftp_put(local: str, remote: str) -> None:
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


def upload_and_verify(local_apk: Path, new_name: str) -> tuple[str, int, str]:
    primary_remote = f"{PRIMARY_REMOTE_DIR}/{new_name}"
    mirror_remote = f"{MIRROR_REMOTE_DIR}/{new_name}"
    log(f"ensure remote dirs exist")
    ssh_exec(f"mkdir -p {PRIMARY_REMOTE_DIR} {MIRROR_REMOTE_DIR}")
    log(f"SFTP upload -> {primary_remote}")
    sftp_put(str(local_apk), primary_remote)
    rc, out = ssh_exec(f"ls -la {primary_remote}")
    log(f"  {out.strip()}")
    # mirror via server-side copy
    log(f"mirror copy -> {mirror_remote}")
    ssh_exec(
        f"cp -f {primary_remote} {mirror_remote} && chmod 644 {mirror_remote}"
    )

    url = f"{BASE_URL}/{new_name}"
    log(f"HTTPS verify: {url}")
    size = 0
    code_seen = ""
    last_err = None
    for i in range(6):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                code_seen = str(code)
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
        raise RuntimeError(
            f"HTTPS check failed (last code={code_seen}, err={last_err})"
        )
    return url, size, code_seen


def run_one() -> dict:
    start = time.time()
    attempt = 0
    failure_notes: list[str] = []

    while attempt <= MAX_BUILD_RETRY:
        attempt += 1
        tag, ymd, hms, hx = make_version_tag()
        log(f"=== Attempt {attempt}/{MAX_BUILD_RETRY+1}  tag={tag} ===")
        trigger_ts = time.time()
        trigger_workflow(tag)
        time.sleep(8)
        run_id = wait_new_run(trigger_ts)
        status, conclusion = poll_run(run_id)
        release_url = (
            f"https://github.com/{REPO}/releases/tag/{tag}"
        )
        if conclusion != "success":
            log(f"build failed: conclusion={conclusion}")
            tail = fetch_fail_log(run_id)
            failure_notes.append(
                f"attempt {attempt} run={run_id} conclusion={conclusion}\n"
                f"--- failed log (tail) ---\n{tail[-3000:]}"
            )
            if attempt > MAX_BUILD_RETRY:
                return {
                    "success": False,
                    "reason": "build_failed",
                    "attempts": attempt,
                    "last_run_id": run_id,
                    "last_tag": tag,
                    "release_page": release_url,
                    "failure_notes": failure_notes,
                    "elapsed_sec": int(time.time() - start),
                }
            log("will retry build with a fresh tag ...")
            continue

        log(f"build succeeded run={run_id}")
        apk_local = download_apk(tag)
        new_name = f"app_promptcfg_{ymd}_{hms}_{hx}.apk"
        renamed = APK_TMP / new_name
        shutil.move(str(apk_local), str(renamed))
        log(f"  renamed locally: {renamed.name}  size={renamed.stat().st_size}")
        url, size, http_code = upload_and_verify(renamed, new_name)
        return {
            "success": True,
            "apk_name": new_name,
            "download_url": url,
            "file_size_bytes": size,
            "file_size_mb": round(size / 1024 / 1024, 2),
            "http_status": http_code,
            "release_page": release_url,
            "tag": tag,
            "run_id": run_id,
            "attempts": attempt,
            "elapsed_sec": int(time.time() - start),
        }
    return {"success": False, "reason": "unknown"}


def main() -> int:
    log("=== Android APK promptcfg build pipeline start ===")
    try:
        result = run_one()
    except Exception as exc:
        log(f"FATAL: {exc}")
        import traceback
        traceback.print_exc()
        result = {"success": False, "reason": "exception", "error": str(exc)}
    print("\n================ RESULT ================")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("========================================")
    if result.get("success"):
        print(f"DOWNLOAD_URL={result['download_url']}")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
