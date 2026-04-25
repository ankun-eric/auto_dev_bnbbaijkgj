"""
Orchestrator: trigger GitHub Actions Android build, poll, download APK.
Outputs final summary lines like:
    TAG=...
    RUN_ID=...
    APK_LOCAL=...
"""
import os
import sys
import time
import random
import subprocess
import json

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "android-build.yml"
DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))


def run(cmd, timeout=120, check=False):
    """Run a command and return (returncode, stdout, stderr)."""
    print(f"[RUN] {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    try:
        p = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as ex:
        print(f"[TIMEOUT] {ex}", flush=True)
        return 124, "", str(ex)
    if p.stdout:
        print(p.stdout, flush=True)
    if p.stderr:
        print(f"[STDERR] {p.stderr}", flush=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    return p.returncode, p.stdout or "", p.stderr or ""


def retry_run(cmd, attempts=3, delays=(10, 20, 40), timeout=120):
    last = None
    for i in range(attempts):
        rc, so, se = run(cmd, timeout=timeout)
        if rc == 0:
            return rc, so, se
        last = (rc, so, se)
        if i < attempts - 1:
            d = delays[i] if i < len(delays) else delays[-1]
            print(f"[RETRY] attempt {i + 1}/{attempts} failed; sleep {d}s", flush=True)
            time.sleep(d)
    return last


def gen_tag():
    ts = time.strftime("%Y%m%d-%H%M%S")
    rh = f"{random.randint(0, 0xFFFF):04x}"
    return f"android-ai-report-v{ts}-{rh}"


def trigger_workflow(tag):
    cmd = ["gh", "workflow", "run", WORKFLOW, "-R", REPO, "-f", f"version={tag}"]
    rc, so, se = retry_run(cmd, attempts=3)
    return rc == 0


def get_latest_run_for_tag(tag, max_wait=120):
    """Wait for a run to appear (created_at after triggering)."""
    start = time.time()
    while time.time() - start < max_wait:
        cmd = [
            "gh", "run", "list", "-R", REPO,
            "--workflow", WORKFLOW,
            "--limit", "5",
            "--json", "databaseId,status,conclusion,displayTitle,event,createdAt,headBranch,name",
        ]
        rc, so, se = run(cmd, timeout=60)
        if rc == 0 and so.strip():
            try:
                runs = json.loads(so)
                if runs:
                    return runs[0]["databaseId"]
            except Exception as e:
                print(f"[WARN] parse runs JSON failed: {e}", flush=True)
        time.sleep(10)
    return None


def poll_run(run_id, max_wait_seconds=1800):
    start = time.time()
    while time.time() - start < max_wait_seconds:
        cmd = [
            "gh", "run", "view", str(run_id), "-R", REPO,
            "--json", "status,conclusion,databaseId",
        ]
        rc, so, se = run(cmd, timeout=60)
        if rc == 0 and so.strip():
            try:
                info = json.loads(so)
                status = info.get("status")
                concl = info.get("conclusion")
                elapsed = int(time.time() - start)
                print(f"[POLL] run={run_id} status={status} conclusion={concl} elapsed={elapsed}s", flush=True)
                if status == "completed":
                    return concl
            except Exception as e:
                print(f"[WARN] parse run view JSON failed: {e}", flush=True)
        time.sleep(30)
    return "timeout"


def dump_failed_log(run_id):
    cmd = ["gh", "run", "view", str(run_id), "-R", REPO, "--log-failed"]
    rc, so, se = run(cmd, timeout=120)
    tail = (so or "").splitlines()[-200:]
    return "\n".join(tail)


def download_apk(tag):
    target = os.path.join(DEPLOY_DIR, f"bini_health_{tag}.apk")
    if os.path.exists(target):
        os.remove(target)
    cmd = [
        "gh", "release", "download", tag, "-R", REPO,
        "--pattern", "*.apk",
        "--dir", DEPLOY_DIR,
    ]
    rc, so, se = retry_run(cmd, attempts=3, timeout=300)
    if rc == 0 and os.path.exists(target):
        return target
    # Fallback: curl direct
    url = f"https://github.com/{REPO}/releases/download/{tag}/bini_health_{tag}.apk"
    print(f"[FALLBACK] direct curl {url}", flush=True)
    cmd2 = ["curl", "-L", "-o", target, url]
    rc, so, se = retry_run(cmd2, attempts=3, timeout=600)
    if rc == 0 and os.path.exists(target) and os.path.getsize(target) > 1024 * 1024:
        return target
    return None


def main():
    tag = gen_tag()
    print(f"[TAG] {tag}", flush=True)

    # Step 1: trigger
    if not trigger_workflow(tag):
        print("[FATAL] trigger workflow failed after retries", flush=True)
        print(f"FINAL_TAG={tag}\nFINAL_RUN_ID=\nFINAL_APK=\nFINAL_STATUS=FAIL_TRIGGER")
        sys.exit(2)

    # Wait a bit for run to appear
    time.sleep(8)
    run_id = get_latest_run_for_tag(tag, max_wait=180)
    if not run_id:
        print("[FATAL] could not find a workflow run after triggering", flush=True)
        print(f"FINAL_TAG={tag}\nFINAL_RUN_ID=\nFINAL_APK=\nFINAL_STATUS=FAIL_NORUN")
        sys.exit(3)
    print(f"[RUN_ID] {run_id}", flush=True)

    # Poll, allow up to 2 retries on failure
    attempts = 0
    final_run_id = run_id
    while attempts < 3:
        concl = poll_run(final_run_id, max_wait_seconds=1800)
        print(f"[CONCLUSION] {concl}", flush=True)
        if concl == "success":
            break
        # Failed/timeout -> dump log and retry
        log_tail = dump_failed_log(final_run_id)
        print("[FAILED_LOG_TAIL]\n" + log_tail, flush=True)
        attempts += 1
        if attempts >= 3:
            print(f"[FATAL] all build attempts failed", flush=True)
            print(f"FINAL_TAG={tag}\nFINAL_RUN_ID={final_run_id}\nFINAL_APK=\nFINAL_STATUS=FAIL_BUILD")
            sys.exit(4)
        # Re-trigger same tag (delete release first to avoid conflict)
        print("[RETRY] deleting previous release/tag if any then re-triggering", flush=True)
        run(["gh", "release", "delete", tag, "-R", REPO, "--yes", "--cleanup-tag"], timeout=60)
        time.sleep(5)
        if not trigger_workflow(tag):
            print("[FATAL] retrigger failed", flush=True)
            print(f"FINAL_TAG={tag}\nFINAL_RUN_ID={final_run_id}\nFINAL_APK=\nFINAL_STATUS=FAIL_TRIGGER")
            sys.exit(5)
        time.sleep(8)
        new_id = get_latest_run_for_tag(tag, max_wait=180)
        if new_id:
            final_run_id = new_id
            print(f"[NEW_RUN_ID] {final_run_id}", flush=True)

    # Step 5: download
    apk = download_apk(tag)
    if not apk:
        print("[FATAL] download APK failed", flush=True)
        print(f"FINAL_TAG={tag}\nFINAL_RUN_ID={final_run_id}\nFINAL_APK=\nFINAL_STATUS=FAIL_DOWNLOAD")
        sys.exit(6)
    sz = os.path.getsize(apk) / 1024 / 1024
    print(f"[APK] {apk} ({sz:.2f} MB)", flush=True)
    print(f"FINAL_TAG={tag}\nFINAL_RUN_ID={final_run_id}\nFINAL_APK={apk}\nFINAL_STATUS=SUCCESS")


if __name__ == "__main__":
    main()
