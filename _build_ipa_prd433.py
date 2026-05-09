#!/usr/bin/env python3
"""[PRD-433] Flutter iOS IPA 远程构建脚本（GitHub Actions + GH Release）。"""
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
LOG_FILE = r"C:\auto_output\bnbbaijkgj\_build_ipa_prd433.log"

env = os.environ.copy()
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


def gh_retry(cmd, max_retries=3, timeout=120):
    """gh 命令重试包装：失败后等待 10/20/40s 重试。"""
    wait = 10
    last = None
    for i in range(1, max_retries + 1):
        log(f"gh attempt {i}/{max_retries}")
        r = run(cmd, timeout=timeout)
        last = r
        if r.returncode == 0:
            return r
        if i < max_retries:
            log(f"gh failed, sleep {wait}s before retry...")
            time.sleep(wait)
            wait *= 2
    return last


def gen_version_tag():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices("0123456789abcdef", k=4))
    return f"ios-prd433-v{ts}-{suffix}"


def trigger_workflow(version):
    log(f"=== Trigger workflow version={version} ===")
    r = gh_retry(f'gh workflow run {WORKFLOW} -R {REPO} -f version={version}')
    return r is not None and r.returncode == 0


def get_run_id():
    log("=== Locating run id ===")
    deadline = time.time() + 180
    last_id = None
    while time.time() < deadline:
        r = gh_retry(
            f'gh run list -R {REPO} --workflow={WORKFLOW} --limit 5 '
            f'--json databaseId,status,conclusion,displayTitle,createdAt,event,headBranch'
        )
        if r and r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                for entry in data:
                    if entry.get("event") == "workflow_dispatch":
                        last_id = entry["databaseId"]
                        log(f"Found dispatch run id={last_id}")
                        return last_id
            except Exception as e:
                log(f"Parse error: {e}")
        time.sleep(5)
    return last_id


def poll_run(run_id, max_wait_sec=1800):
    log(f"=== Polling run {run_id} (max {max_wait_sec}s) ===")
    start = time.time()
    while time.time() - start < max_wait_sec:
        elapsed = int(time.time() - start)
        r = gh_retry(f'gh run view {run_id} -R {REPO} --json status,conclusion,url,name')
        if r and r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                log(f"[{elapsed}s] status={data.get('status')} conclusion={data.get('conclusion')}")
                if data.get("status") == "completed":
                    return data
            except Exception as e:
                log(f"Parse error: {e}")
        time.sleep(30)
    log("Polling timeout reached")
    return None


def get_release_info(version):
    log(f"=== Get release info for {version} ===")
    r = gh_retry(
        f'gh release view {version} -R {REPO} --json url,assets,name,tagName,createdAt'
    )
    if not r or r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception as e:
        log(f"Parse error: {e}")
        return None


def get_failure_logs(run_id):
    log(f"=== Fetching failure logs for run {run_id} ===")
    r = run(f'gh run view {run_id} -R {REPO} --log-failed', timeout=180)
    if r.stdout:
        return r.stdout
    return ""


def extract_flutter_errors(log_text):
    """提取 Flutter 编译错误关键 50 行。"""
    lines = log_text.splitlines()
    keys = ["chat_screen.dart", "chat_message.dart", "Error:", "error:", "Failed", "FAILURE"]
    indices = [i for i, ln in enumerate(lines) if any(k in ln for k in keys)]
    if not indices:
        return "\n".join(lines[-50:])
    first = max(0, indices[0] - 5)
    last = min(len(lines), indices[-1] + 10)
    snippet_lines = lines[first:last]
    if len(snippet_lines) > 80:
        snippet_lines = snippet_lines[:80]
    return "\n".join(snippet_lines)


def build_once(retry_attempt):
    """完整执行一次构建（触发->轮询->取 release）。返回 result dict。"""
    result = {
        "attempt": retry_attempt,
        "success": False,
        "version": None,
        "run_id": None,
        "actions_run_url": None,
        "release_url": None,
        "ipa_url": None,
        "ipa_size_bytes": None,
        "conclusion": None,
        "error": None,
        "fail_log_snippet": None,
    }

    version = gen_version_tag()
    result["version"] = version
    log(f"Version tag: {version}")

    if not trigger_workflow(version):
        result["error"] = "Failed to trigger workflow after 3 attempts"
        return result

    log("Sleep 30s before locating run id...")
    time.sleep(30)

    run_id = get_run_id()
    if not run_id:
        result["error"] = "Could not locate workflow run id"
        return result
    result["run_id"] = run_id
    result["actions_run_url"] = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"Actions Run URL: {result['actions_run_url']}")

    final = poll_run(run_id, max_wait_sec=1800)
    if final is None:
        result["error"] = f"Build timeout after 30 min. See {result['actions_run_url']}"
        return result

    conclusion = final.get("conclusion")
    result["conclusion"] = conclusion
    if conclusion != "success":
        log(f"Build did NOT succeed: conclusion={conclusion}")
        full_log = get_failure_logs(run_id)
        snippet = extract_flutter_errors(full_log)
        result["fail_log_snippet"] = snippet
        result["error"] = f"conclusion={conclusion}"
        log("=== FAILURE LOG SNIPPET (key 50 lines) ===")
        log(snippet)
        log("=== END SNIPPET ===")
        return result

    log("Build succeeded; fetching release info...")
    rel = None
    for attempt in range(6):
        rel = get_release_info(version)
        if rel and rel.get("assets"):
            break
        log(f"Release not ready, retry {attempt + 1}/6 in 10s")
        time.sleep(10)

    if not rel:
        result["error"] = f"Release {version} not found after build"
        return result

    result["release_url"] = rel.get("url")
    assets = rel.get("assets") or []
    ipa_asset = None
    for a in assets:
        if a.get("name", "").lower().endswith(".ipa"):
            ipa_asset = a
            break
    if not ipa_asset and assets:
        ipa_asset = assets[0]

    if ipa_asset:
        result["ipa_url"] = (
            ipa_asset.get("url")
            or ipa_asset.get("browser_download_url")
            or f"https://github.com/{REPO}/releases/download/{version}/{ipa_asset.get('name')}"
        )
        result["ipa_size_bytes"] = ipa_asset.get("size")
        log(f"IPA asset: {ipa_asset}")
        result["success"] = True
    else:
        result["error"] = "No assets in release"

    return result


def main():
    start_time = time.time()
    log("=" * 60)
    log("PRD-433: Flutter iOS IPA build via GitHub Actions")
    log("=" * 60)

    final_result = {
        "success": False,
        "version": None,
        "run_id": None,
        "release_url": None,
        "ipa_url": None,
        "ipa_size_bytes": None,
        "conclusion": None,
        "actions_run_url": None,
        "build_seconds": None,
        "error": None,
        "fail_log_snippet": None,
        "attempts": [],
    }

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        log(f"\n========== BUILD ATTEMPT {attempt}/{max_attempts} ==========")
        r = build_once(attempt)
        final_result["attempts"].append(r)
        for k in ("version", "run_id", "release_url", "ipa_url",
                  "ipa_size_bytes", "conclusion", "actions_run_url",
                  "error", "fail_log_snippet"):
            final_result[k] = r.get(k)
        if r["success"]:
            final_result["success"] = True
            break
        if attempt < max_attempts:
            log("Build failed, retry once...")
            time.sleep(15)

    final_result["build_seconds"] = int(time.time() - start_time)
    log("=" * 60)
    log("FINAL RESULT:")
    log(json.dumps({k: v for k, v in final_result.items() if k != "attempts"},
                   indent=2, ensure_ascii=False))
    log("=" * 60)
    log_fp.close()
    print("\n===RESULT_JSON_BEGIN===")
    print(json.dumps(final_result, ensure_ascii=False))
    print("===RESULT_JSON_END===")
    return 0 if final_result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
