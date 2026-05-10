"""PRD-443 iOS pack: trigger GitHub Actions macOS runner, wait, return Release URLs."""
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
LOG_FILE = os.path.join(PROJECT_ROOT, "_pack_prd443_ios.log")
WORKFLOW = "ios-build.yml"
POLL_INTERVAL = 30
MAX_WAIT_SEC = 30 * 60


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, retries=3, check=True, capture=True):
    last_err = None
    for attempt in range(1, retries + 1):
        log(f"$ {' '.join(cmd)} (attempt {attempt}/{retries})")
        try:
            r = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=capture,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if r.stdout:
                log(r.stdout.strip())
            if r.stderr:
                log("STDERR: " + r.stderr.strip())
            if r.returncode == 0:
                return r
            last_err = f"exit {r.returncode}: {r.stderr}"
        except Exception as e:
            last_err = str(e)
            log(f"EXCEPTION: {e}")
        if attempt < retries:
            time.sleep(5 * attempt)
    if check:
        raise RuntimeError(f"Command failed after {retries} attempts: {last_err}")
    return None


def main():
    open(LOG_FILE, "w", encoding="utf-8").close()
    log("=== PRD-443 iOS pack START ===")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand = secrets.token_hex(2)
    tag = f"ios-prd443-v{ts}-{rand}"
    log(f"Version tag: {tag}")

    log("Triggering workflow...")
    run(["gh", "workflow", "run", WORKFLOW, "-f", f"version={tag}"])

    time.sleep(8)
    log("Fetching latest run id...")
    r = run([
        "gh", "run", "list", "--workflow=" + WORKFLOW, "--limit", "1",
        "--json", "databaseId,status,headBranch,displayTitle,createdAt",
    ])
    runs = json.loads(r.stdout)
    if not runs:
        raise RuntimeError("No run found after dispatch")
    run_id = str(runs[0]["databaseId"])
    log(f"Run ID: {run_id}")

    log(f"Polling run {run_id} (max {MAX_WAIT_SEC}s)...")
    started = time.time()
    conclusion = None
    while time.time() - started < MAX_WAIT_SEC:
        r = run(
            ["gh", "run", "view", run_id, "--json", "status,conclusion"],
            retries=3,
            check=False,
        )
        if r and r.returncode == 0:
            data = json.loads(r.stdout)
            status = data.get("status")
            conclusion = data.get("conclusion")
            elapsed = int(time.time() - started)
            log(f"[{elapsed}s] status={status} conclusion={conclusion}")
            if status == "completed":
                break
        time.sleep(POLL_INTERVAL)
    else:
        raise RuntimeError(f"Build timed out after {MAX_WAIT_SEC}s, run_id={run_id}")

    if conclusion != "success":
        raise RuntimeError(f"Build failed: conclusion={conclusion}, run_id={run_id}")

    log("Build succeeded. Fetching release info...")
    time.sleep(5)
    r = run(["gh", "release", "view", tag, "--json", "url,assets"])
    rel = json.loads(r.stdout)
    release_url = rel.get("url", "")
    assets = rel.get("assets", []) or []
    ipa_url = ""
    ipa_name = ""
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa_name = name
            ipa_url = a.get("url", "") or a.get("browser_download_url", "") or ""
            break
    if not ipa_url and assets:
        ipa_name = assets[0].get("name", "")
        ipa_url = assets[0].get("url", "") or assets[0].get("browser_download_url", "") or ""

    result = {
        "tag": tag,
        "run_id": run_id,
        "release_url": release_url,
        "ipa_url": ipa_url,
        "ipa_name": ipa_name,
    }
    log("=== RESULT ===")
    log(json.dumps(result, indent=2, ensure_ascii=False))
    log("=== PRD-443 iOS pack END ===")
    print("\nRESULT_JSON=" + json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
