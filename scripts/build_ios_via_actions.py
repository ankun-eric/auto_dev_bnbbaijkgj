"""Trigger GitHub Actions iOS build, wait for completion, and return Release URL.

Usage:
    python scripts/build_ios_via_actions.py
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
POLL_INTERVAL_SEC = 30
MAX_WAIT_SEC = 30 * 60
MAX_RETRIES = 3
RETRY_BACKOFF = [10, 20, 40]


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_gh(args: list[str], retries: int = MAX_RETRIES) -> subprocess.CompletedProcess:
    last_err = None
    for i in range(retries):
        try:
            res = subprocess.run(
                ["gh", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if res.returncode == 0:
                return res
            last_err = f"exit={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}"
            log(f"gh {' '.join(args)} failed (attempt {i+1}/{retries}): {last_err[:300]}")
        except Exception as e:
            last_err = repr(e)
            log(f"gh {' '.join(args)} exception (attempt {i+1}/{retries}): {last_err}")
        if i < retries - 1:
            wait = RETRY_BACKOFF[min(i, len(RETRY_BACKOFF) - 1)]
            log(f"retrying after {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(f"gh command failed after {retries} retries: gh {' '.join(args)}\n{last_err}")


def generate_version() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"ios-v{ts}-{suffix}"


def trigger_workflow(version: str) -> None:
    log(f"Triggering workflow: {WORKFLOW} version={version}")
    run_gh([
        "workflow", "run", WORKFLOW,
        "-R", REPO,
        "-f", f"version={version}",
    ])
    log("workflow_dispatch sent")


def find_run_id(version: str, since_ts: float) -> str | None:
    res = run_gh([
        "run", "list",
        "-R", REPO,
        "--workflow", WORKFLOW,
        "--limit", "10",
        "--json", "databaseId,displayTitle,name,createdAt,event,status,conclusion",
    ])
    runs = json.loads(res.stdout)
    for r in runs:
        if r.get("event") != "workflow_dispatch":
            continue
        try:
            created = datetime.strptime(r["createdAt"], "%Y-%m-%dT%H:%M:%SZ").timestamp()
        except Exception:
            created = 0
        if created + 5 >= since_ts - 60:
            return str(r["databaseId"])
    if runs:
        return str(runs[0]["databaseId"])
    return None


def get_run_status(run_id: str) -> tuple[str, str | None]:
    res = run_gh([
        "run", "view", run_id,
        "-R", REPO,
        "--json", "status,conclusion",
    ])
    data = json.loads(res.stdout)
    return data.get("status", ""), data.get("conclusion")


def wait_for_run(run_id: str) -> str:
    log(f"Waiting for run {run_id} (timeout {MAX_WAIT_SEC}s)")
    start = time.time()
    while time.time() - start < MAX_WAIT_SEC:
        status, conclusion = get_run_status(run_id)
        elapsed = int(time.time() - start)
        log(f"  run {run_id}: status={status} conclusion={conclusion} elapsed={elapsed}s")
        if status == "completed":
            return conclusion or ""
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"Run {run_id} did not complete within {MAX_WAIT_SEC}s")


def dump_failed_logs(run_id: str, tail_lines: int = 150) -> str:
    try:
        res = subprocess.run(
            ["gh", "run", "view", run_id, "-R", REPO, "--log-failed"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        out = (res.stdout or "") + (res.stderr or "")
        lines = out.splitlines()
        tail = "\n".join(lines[-tail_lines:])
        log(f"--- failed log tail ({tail_lines} lines) ---\n{tail}\n--- end ---")
        return tail
    except Exception as e:
        log(f"failed to fetch failed logs: {e}")
        return ""


def get_release(version: str) -> dict:
    res = run_gh([
        "release", "view", version,
        "-R", REPO,
        "--json", "url,assets,tagName,name",
    ])
    return json.loads(res.stdout)


def verify_release_url(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ios-build-checker"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return -1, repr(e)


def main() -> int:
    overall_start = time.time()

    version = generate_version()
    log(f"Generated version tag: {version}")

    trigger_started = time.time()
    trigger_workflow(version)

    time.sleep(8)
    run_id = None
    for attempt in range(6):
        run_id = find_run_id(version, trigger_started)
        if run_id:
            break
        log(f"run not found yet, retry {attempt+1}/6")
        time.sleep(5)
    if not run_id:
        log("ERROR: could not locate the dispatched run")
        return 2
    log(f"Tracking run id: {run_id}")
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"Run URL: {run_url}")

    conclusion = wait_for_run(run_id)
    build_seconds = int(time.time() - trigger_started)
    log(f"Build finished with conclusion={conclusion} in {build_seconds}s")

    if conclusion != "success":
        dump_failed_logs(run_id)
        log("=" * 60)
        log(f"BUILD_FAILED version={version} run_id={run_id} conclusion={conclusion}")
        log(f"Run URL: {run_url}")
        log("=" * 60)
        return 3

    try:
        rel = get_release(version)
    except Exception as e:
        log(f"Could not fetch release: {e}")
        return 4

    release_url = rel.get("url") or f"https://github.com/{REPO}/releases/tag/{version}"
    assets = rel.get("assets") or []
    ipa_url = None
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa_url = a.get("url") or a.get("browserDownloadUrl") or a.get("apiUrl")
            ipa_name = name
            break
    if not ipa_url and assets:
        a = assets[0]
        ipa_url = a.get("url") or a.get("browserDownloadUrl")
        ipa_name = a.get("name")
    else:
        ipa_name = ipa_url and ipa_url.split("/")[-1]

    if not ipa_url:
        download_url = f"https://github.com/{REPO}/releases/download/{version}/bini_health_ios.ipa"
    else:
        download_url = ipa_url

    log(f"Release URL: {release_url}")
    log(f"IPA download URL: {download_url}")

    code, ctype = verify_release_url(release_url)
    log(f"Release page HTTP status: {code} ({ctype})")

    total = int(time.time() - overall_start)
    log("=" * 60)
    log("BUILD_SUCCESS")
    log(f"  version:       {version}")
    log(f"  run_id:        {run_id}")
    log(f"  run_url:       {run_url}")
    log(f"  release_url:   {release_url}")
    log(f"  ipa_download:  {download_url}")
    log(f"  release_http:  {code}")
    log(f"  build_seconds: {build_seconds}")
    log(f"  total_seconds: {total}")
    log("=" * 60)

    out = {
        "version": version,
        "run_id": run_id,
        "run_url": run_url,
        "release_url": release_url,
        "ipa_download": download_url,
        "release_http": code,
        "build_seconds": build_seconds,
        "total_seconds": total,
        "conclusion": conclusion,
    }
    print("RESULT_JSON=" + json.dumps(out, ensure_ascii=False))
    return 0 if code == 200 else 5


if __name__ == "__main__":
    sys.exit(main())
