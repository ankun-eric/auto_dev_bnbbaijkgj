"""
iOS IPA build orchestration via GitHub Actions (macOS Runner).

bugfix-336: 改约按钮文案统一 (unified_orders_screen.dart / unified_order_detail_screen.dart)
Repo: ankun-eric/auto_dev_bnbbaijkgj
Workflow: .github/workflows/ios-build.yml (workflow_dispatch, input=version)

Steps:
  1. Generate version tag: ios-v20260505-<HHMMSS>-<4hex>
  2. Trigger workflow (retry 3x: 10s/20s/40s)
  3. Locate the matching run id
  4. Poll status every 30s, max 30min
  5. On success, fetch release URL + IPA download URL via gh
  6. Print result block in required format
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
MAX_WAIT_SECONDS = 30 * 60
POLL_INTERVAL = 30
RETRY_DELAYS = [10, 20, 40]


def run(cmd: list[str], check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    print(f"[cmd] {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_with_retry(cmd: list[str], desc: str) -> subprocess.CompletedProcess:
    last: subprocess.CompletedProcess | None = None
    for i, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            print(f"[retry] {desc} attempt {i+1} after {delay}s sleep", flush=True)
            time.sleep(delay)
        cp = run(cmd)
        if cp.returncode == 0:
            return cp
        last = cp
        print(f"[warn] {desc} failed (rc={cp.returncode})", flush=True)
        print(f"  stdout: {cp.stdout[-500:] if cp.stdout else ''}", flush=True)
        print(f"  stderr: {cp.stderr[-500:] if cp.stderr else ''}", flush=True)
    raise RuntimeError(f"{desc} failed after retries: {last.stderr if last else 'no result'}")


def generate_version_tag() -> str:
    now = datetime.now()
    return f"ios-v20260505-{now.strftime('%H%M%S')}-{secrets.token_hex(2)}"


def trigger_workflow(version: str) -> None:
    run_with_retry(
        ["gh", "workflow", "run", WORKFLOW, "-R", REPO, "-f", f"version={version}"],
        "trigger workflow",
    )


def find_run_id(version: str) -> str:
    deadline = time.time() + 90
    while time.time() < deadline:
        cp = run([
            "gh", "run", "list", "-R", REPO, "--workflow", WORKFLOW,
            "--limit", "10", "--json", "databaseId,headBranch,status,createdAt,displayTitle,event",
        ])
        if cp.returncode == 0 and cp.stdout.strip():
            try:
                data = json.loads(cp.stdout)
            except json.JSONDecodeError:
                data = []
            if data:
                latest = data[0]
                run_id = str(latest["databaseId"])
                print(f"[info] picked latest workflow run id={run_id} status={latest.get('status')}", flush=True)
                return run_id
        time.sleep(5)
    raise RuntimeError("Could not locate workflow run within 90s")


def wait_for_completion(run_id: str) -> str:
    start = time.time()
    while time.time() - start < MAX_WAIT_SECONDS:
        cp = run([
            "gh", "run", "view", run_id, "-R", REPO,
            "--json", "status,conclusion",
        ])
        if cp.returncode == 0 and cp.stdout.strip():
            try:
                data = json.loads(cp.stdout)
            except json.JSONDecodeError:
                data = {}
            status = data.get("status")
            conclusion = data.get("conclusion")
            elapsed = int(time.time() - start)
            print(f"[poll] elapsed={elapsed}s status={status} conclusion={conclusion}", flush=True)
            if status == "completed":
                return conclusion or "unknown"
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Build timed out after {MAX_WAIT_SECONDS}s")


def fetch_release_info(version: str) -> tuple[str, str]:
    deadline = time.time() + 120
    release_url = ""
    ipa_url = ""
    while time.time() < deadline:
        cp1 = run([
            "gh", "release", "view", version, "-R", REPO,
            "--json", "url", "-q", ".url",
        ])
        cp2 = run([
            "gh", "release", "view", version, "-R", REPO,
            "--json", "assets", "-q", ".assets[].browser_download_url",
        ])
        if cp1.returncode == 0 and cp2.returncode == 0:
            release_url = cp1.stdout.strip()
            ipa_url = cp2.stdout.strip().splitlines()[0] if cp2.stdout.strip() else ""
            if release_url and ipa_url:
                return release_url, ipa_url
        time.sleep(10)
    raise RuntimeError(f"Failed to fetch release info for {version}")


def dump_failure_log(run_id: str) -> None:
    print("=" * 60, flush=True)
    print(f"[fail-log] gh run view {run_id} --log-failed", flush=True)
    cp = run(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"])
    print(cp.stdout[-8000:] if cp.stdout else "", flush=True)
    print(cp.stderr[-2000:] if cp.stderr else "", flush=True)


def main() -> int:
    version = generate_version_tag()
    print(f"[version] {version}", flush=True)

    trigger_workflow(version)

    time.sleep(8)
    run_id = find_run_id(version)

    try:
        conclusion = wait_for_completion(run_id)
    except Exception as exc:
        print(f"[error] {exc}", flush=True)
        dump_failure_log(run_id)
        return 2

    if conclusion != "success":
        print(f"[error] build conclusion={conclusion}", flush=True)
        dump_failure_log(run_id)
        return 3

    release_url, ipa_url = fetch_release_info(version)

    print("\n" + "=" * 60, flush=True)
    print("RESULT", flush=True)
    print("=" * 60, flush=True)
    print(f"GITHUB_RELEASE_URL={release_url}")
    print(f"IPA_DOWNLOAD_URL={ipa_url}")
    print(f"VERSION_TAG={version}")
    print(f"RUN_ID={run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
