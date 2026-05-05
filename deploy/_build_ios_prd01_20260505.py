# -*- coding: utf-8 -*-
"""
PRD-01 iOS IPA Build Script via GitHub Actions
Triggers ios-build.yml workflow on remote macOS runner.
"""
import os
import subprocess
import sys
import time
import json
import secrets
import datetime as dt

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
POLL_INTERVAL = 30
MAX_WAIT_SEC = 30 * 60


def run_cmd(args, retries=3, capture=True, allow_fail=False):
    """Run gh/git command with exponential backoff retry."""
    last_err = None
    for attempt in range(retries):
        try:
            res = subprocess.run(
                args,
                capture_output=capture,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if res.returncode == 0:
                return res.stdout.strip()
            last_err = f"exit={res.returncode} stderr={res.stderr} stdout={res.stdout}"
            print(f"[retry {attempt+1}/{retries}] cmd={' '.join(args)} failed: {last_err}", flush=True)
        except Exception as e:
            last_err = str(e)
            print(f"[retry {attempt+1}/{retries}] cmd exception: {e}", flush=True)
        if attempt < retries - 1:
            time.sleep(2 ** attempt * 2)
    if allow_fail:
        return None
    raise RuntimeError(f"Command failed after {retries} retries: {' '.join(args)}\n{last_err}")


def ensure_auth():
    out = run_cmd(["gh", "auth", "status"], retries=2, allow_fail=True)
    if out is None:
        print("Logging in with token...", flush=True)
        proc = subprocess.run(
            ["gh", "auth", "login", "--with-token"],
            input=TOKEN,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh auth login failed: {proc.stderr}")


def gen_version_tag():
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    rand = secrets.token_hex(2)
    return f"ios-prd01-v{ts}-{rand}"


def trigger_workflow(version):
    print(f"Triggering workflow with version={version}", flush=True)
    run_cmd([
        "gh", "workflow", "run", WORKFLOW,
        "-R", REPO,
        "-f", f"version={version}",
    ])


def find_run_id(version, attempts=20):
    """Locate the workflow run triggered for this version."""
    for i in range(attempts):
        out = run_cmd([
            "gh", "run", "list",
            "-R", REPO,
            "--workflow", WORKFLOW,
            "--limit", "10",
            "--json", "databaseId,displayTitle,status,conclusion,createdAt,event",
        ], allow_fail=True)
        if out:
            try:
                runs = json.loads(out)
                for r in runs:
                    if r.get("event") == "workflow_dispatch":
                        return r["databaseId"]
            except Exception as e:
                print(f"parse run list failed: {e}", flush=True)
        time.sleep(5)
    raise RuntimeError("Could not locate triggered workflow run")


def poll_run(run_id):
    deadline = time.time() + MAX_WAIT_SEC
    last_status = None
    while time.time() < deadline:
        out = run_cmd([
            "gh", "run", "view", str(run_id),
            "-R", REPO,
            "--json", "status,conclusion,displayTitle,url",
        ], allow_fail=True)
        if out:
            try:
                info = json.loads(out)
                status = info.get("status")
                conclusion = info.get("conclusion")
                if status != last_status:
                    print(f"[{time.strftime('%H:%M:%S')}] status={status} conclusion={conclusion}", flush=True)
                    last_status = status
                if status == "completed":
                    return conclusion, info
            except Exception as e:
                print(f"parse run view failed: {e}", flush=True)
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("Build timed out after 30 minutes")


def get_release_assets(version):
    out = run_cmd([
        "gh", "release", "view", version,
        "-R", REPO,
        "--json", "assets,url,tagName",
    ], allow_fail=True)
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def get_failure_log(run_id):
    proc = subprocess.run(
        ["gh", "run", "view", str(run_id), "-R", REPO, "--log-failed"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return log[-4000:]


def main():
    ensure_auth()
    version = gen_version_tag()
    print(f"=== Version tag: {version} ===", flush=True)

    trigger_workflow(version)
    time.sleep(8)
    run_id = find_run_id(version)
    print(f"Found run_id={run_id}", flush=True)

    conclusion, info = poll_run(run_id)
    print(f"=== Build finished: conclusion={conclusion} ===", flush=True)

    if conclusion != "success":
        log_tail = get_failure_log(run_id)
        print("=== FAILURE LOG TAIL ===", flush=True)
        print(log_tail, flush=True)
        result = {
            "version": version,
            "status": conclusion or "failure",
            "run_id": run_id,
            "run_url": info.get("url") if info else "",
            "log_tail": log_tail,
        }
        print("=== RESULT JSON ===", flush=True)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        sys.exit(1)

    rel = get_release_assets(version)
    release_page = f"https://github.com/{REPO}/releases/tag/{version}"
    ipa_url = ""
    if rel and rel.get("assets"):
        for a in rel["assets"]:
            name = a.get("name", "")
            if name.endswith(".ipa"):
                ipa_url = f"https://github.com/{REPO}/releases/download/{version}/{name}"
                break

    result = {
        "version": version,
        "status": "success",
        "run_id": run_id,
        "release_page": release_page,
        "ipa_url": ipa_url,
    }
    print("=== RESULT JSON ===", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
