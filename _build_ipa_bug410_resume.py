#!/usr/bin/env python3
"""Resume polling for already-triggered run 25535852316."""
import os
import sys
import time
import json
import subprocess
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
RUN_ID = "25535852316"
VERSION = "ios-bug410-v20260508-115806-oixd"
GH_TOKEN = "${GH_TOKEN_PLACEHOLDER}"
LOG_FILE = r"C:\auto_output\bnbbaijkgj\_build_ipa_bug410.log"

env = os.environ.copy()
env["GH_TOKEN"] = GH_TOKEN
env["GITHUB_TOKEN"] = GH_TOKEN

log_fp = open(LOG_FILE, "a", encoding="utf-8")


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    log_fp.write(line + "\n")
    log_fp.flush()


def run(cmd, timeout=120):
    log(f"$ {cmd}")
    try:
        r = subprocess.run(
            cmd, shell=True, env=env, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        if r.stdout:
            log(f"STDOUT: {r.stdout.strip()[:1500]}")
        if r.stderr:
            log(f"STDERR: {r.stderr.strip()[:1500]}")
        log(f"exit={r.returncode}")
        return r
    except Exception as e:
        log(f"EXC: {e}")
        return None


def poll(run_id, max_wait_sec=1800):
    log(f"=== Polling run {run_id} ===")
    start = time.time()
    while time.time() - start < max_wait_sec:
        elapsed = int(time.time() - start)
        r = run(f'gh run view {run_id} -R {REPO} --json status,conclusion,url')
        if r and r.returncode == 0 and r.stdout.strip():
            try:
                d = json.loads(r.stdout)
                log(f"[{elapsed}s] status={d.get('status')} conclusion={d.get('conclusion')}")
                if d.get("status") == "completed":
                    return d
            except Exception as e:
                log(f"Parse: {e}")
        time.sleep(30)
    return None


def get_release(version):
    r = run(f'gh release view {version} -R {REPO} --json url,assets,name,tagName')
    if r and r.returncode == 0 and r.stdout.strip():
        try:
            return json.loads(r.stdout)
        except Exception as e:
            log(f"Parse: {e}")
    return None


def main():
    start = time.time()
    result = {
        "success": False,
        "version": VERSION,
        "release_url": None,
        "ipa_url": None,
        "ipa_size_bytes": None,
        "build_seconds": None,
        "actions_run_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}",
        "error": None,
    }

    final = poll(RUN_ID, max_wait_sec=1800)
    if final is None:
        result["error"] = f"Build timeout. URL={result['actions_run_url']}"
    elif final.get("conclusion") != "success":
        log("Build did not succeed; fetching failure logs")
        rlog = run(f'gh run view {RUN_ID} -R {REPO} --log-failed', timeout=180)
        snip = (rlog.stdout or "")[-3000:] if rlog else ""
        result["error"] = f"conclusion={final.get('conclusion')}. URL={result['actions_run_url']}. Tail:\n{snip}"
    else:
        log("Build succeeded; fetch release")
        rel = None
        for i in range(8):
            rel = get_release(VERSION)
            if rel and rel.get("assets"):
                break
            log(f"retry {i+1}/8")
            time.sleep(10)
        if not rel:
            result["error"] = "Release not found"
        else:
            result["release_url"] = rel.get("url")
            assets = rel.get("assets") or []
            ipa = next((a for a in assets if a.get("name", "").lower().endswith(".ipa")), None)
            if not ipa and assets:
                ipa = assets[0]
            if ipa:
                result["ipa_url"] = ipa.get("url") or ipa.get("browser_download_url")
                result["ipa_size_bytes"] = ipa.get("size")
                result["success"] = True
                log(f"IPA: {ipa}")
            else:
                result["error"] = "No assets in release"

    result["build_seconds"] = int(time.time() - start)
    log("=" * 60)
    log("RESULT: " + json.dumps(result, ensure_ascii=False, indent=2))
    log_fp.close()
    print("\n===RESULT_JSON_BEGIN===")
    print(json.dumps(result, ensure_ascii=False))
    print("===RESULT_JSON_END===")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
