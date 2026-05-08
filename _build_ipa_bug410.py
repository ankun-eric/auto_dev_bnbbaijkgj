#!/usr/bin/env python3
"""
阶段 4-C: Flutter iOS IPA 打包脚本
通过 GitHub Actions 远程在 macOS Runner 构建 IPA，并发布到 GitHub Release。
"""
import os
import sys
import time
import json
import random
import string
import subprocess
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
GH_TOKEN = "${GH_TOKEN_PLACEHOLDER}"
LOG_FILE = r"C:\auto_output\bnbbaijkgj\_build_ipa_bug410.log"

env = os.environ.copy()
env["GH_TOKEN"] = GH_TOKEN
env["GITHUB_TOKEN"] = GH_TOKEN

log_fp = open(LOG_FILE, "w", encoding="utf-8")


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    log_fp.write(line + "\n")
    log_fp.flush()


def run(cmd, check=False, capture=True, timeout=300):
    log(f"$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    try:
        r = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            env=env,
            capture_output=capture,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if capture:
            if r.stdout:
                log(f"STDOUT: {r.stdout.strip()[:2000]}")
            if r.stderr:
                log(f"STDERR: {r.stderr.strip()[:2000]}")
        log(f"exit code: {r.returncode}")
        if check and r.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}")
        return r
    except subprocess.TimeoutExpired as e:
        log(f"TIMEOUT after {timeout}s: {e}")
        raise


def gen_version_tag():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"ios-bug410-v{ts}-{suffix}"


def trigger_workflow(version, max_retries=3):
    for i in range(1, max_retries + 1):
        log(f"=== Trigger workflow (attempt {i}/{max_retries}) ===")
        r = run(
            f'gh workflow run {WORKFLOW} -R {REPO} -f version={version}',
            timeout=120,
        )
        if r.returncode == 0:
            log("Workflow trigger succeeded")
            return True
        log(f"Trigger failed, retrying in 10s...")
        time.sleep(10)
    return False


def get_run_id(version, wait_until=None):
    """Find the run id for the workflow we just dispatched."""
    log("=== Locating run id ===")
    deadline = wait_until or (time.time() + 120)
    last_id = None
    while time.time() < deadline:
        r = run(
            f'gh run list -R {REPO} --workflow={WORKFLOW} --limit 5 --json databaseId,status,conclusion,displayTitle,createdAt,event,headBranch',
            timeout=60,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                for entry in data:
                    if entry.get("event") == "workflow_dispatch":
                        last_id = entry["databaseId"]
                        log(f"Found dispatch run id={last_id} status={entry.get('status')} created={entry.get('createdAt')}")
                        return last_id
            except Exception as e:
                log(f"Parse error: {e}")
        time.sleep(5)
    return last_id


def poll_run(run_id, max_wait_sec=1800):
    """Poll until run completes or timeout."""
    log(f"=== Polling run {run_id} (max {max_wait_sec}s) ===")
    start = time.time()
    while time.time() - start < max_wait_sec:
        elapsed = int(time.time() - start)
        r = run(
            f'gh run view {run_id} -R {REPO} --json status,conclusion,url,name',
            timeout=60,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                status = data.get("status")
                conclusion = data.get("conclusion")
                url = data.get("url")
                log(f"[{elapsed}s] status={status} conclusion={conclusion} url={url}")
                if status == "completed":
                    return data
            except Exception as e:
                log(f"Parse error: {e}")
        time.sleep(30)
    log("Polling timeout reached")
    return None


def get_release_info(version):
    log(f"=== Get release info for {version} ===")
    r = run(
        f'gh release view {version} -R {REPO} --json url,assets,name,tagName,createdAt',
        timeout=60,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception as e:
        log(f"Parse error: {e}")
        return None


def get_failure_logs(run_id):
    log(f"=== Fetching failure logs for run {run_id} ===")
    r = run(
        f'gh run view {run_id} -R {REPO} --log-failed',
        timeout=120,
    )
    if r.stdout:
        snippet = r.stdout[-5000:]
        log(f"FAIL_LOG_SNIPPET:\n{snippet}")
        return snippet
    return ""


def main():
    start_time = time.time()
    result = {
        "success": False,
        "version": None,
        "release_url": None,
        "ipa_url": None,
        "ipa_size_bytes": None,
        "build_seconds": None,
        "actions_run_url": None,
        "error": None,
    }

    log("=" * 60)
    log("Stage 4-C: Flutter iOS IPA build via GitHub Actions")
    log("=" * 60)

    version = gen_version_tag()
    result["version"] = version
    log(f"Version tag: {version}")

    run("gh auth status", timeout=60)

    if not trigger_workflow(version):
        result["error"] = "Failed to trigger workflow after 3 attempts"
        return finalize(result, start_time)

    time.sleep(8)

    run_id = get_run_id(version)
    if not run_id:
        result["error"] = "Could not locate workflow run id"
        return finalize(result, start_time)

    actions_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    result["actions_run_url"] = actions_url
    log(f"Actions Run URL: {actions_url}")

    final = poll_run(run_id, max_wait_sec=1800)
    if final is None:
        result["error"] = f"Build timeout after 30 min. See {actions_url}"
        return finalize(result, start_time)

    conclusion = final.get("conclusion")
    if conclusion != "success":
        log(f"Build did NOT succeed: conclusion={conclusion}")
        snippet = get_failure_logs(run_id)
        result["error"] = f"GitHub Actions conclusion={conclusion}. URL={actions_url}. Log tail:\n{snippet[-2000:]}"
        return finalize(result, start_time)

    log("Build succeeded; fetching release info...")
    rel = None
    for attempt in range(6):
        rel = get_release_info(version)
        if rel and rel.get("assets"):
            break
        log(f"Release not ready yet, retry {attempt + 1}/6 in 10s")
        time.sleep(10)

    if not rel:
        result["error"] = f"Release {version} not found after build"
        return finalize(result, start_time)

    result["release_url"] = rel.get("url")
    assets = rel.get("assets") or []
    ipa_asset = None
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa_asset = a
            break
    if not ipa_asset and assets:
        ipa_asset = assets[0]

    if ipa_asset:
        result["ipa_url"] = ipa_asset.get("url") or ipa_asset.get("browser_download_url")
        result["ipa_size_bytes"] = ipa_asset.get("size")
        log(f"IPA asset: {ipa_asset}")
    else:
        result["error"] = "No assets in release"
        return finalize(result, start_time)

    result["success"] = True
    return finalize(result, start_time)


def finalize(result, start_time):
    result["build_seconds"] = int(time.time() - start_time)
    log("=" * 60)
    log("FINAL RESULT:")
    log(json.dumps(result, indent=2, ensure_ascii=False))
    log("=" * 60)
    log_fp.close()
    print("\n===RESULT_JSON_BEGIN===")
    print(json.dumps(result, ensure_ascii=False))
    print("===RESULT_JSON_END===")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
