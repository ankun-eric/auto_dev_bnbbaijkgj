"""
iOS IPA 打包脚本 - v3 全系统时区根治
通过 GitHub Actions 远程 macOS Runner 构建 Flutter iOS IPA，并在 GitHub Release 发布。
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

WORK_DIR = r"C:\auto_output\bnbbaijkgj"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "ios-build.yml"
LOG_FILE = os.path.join(WORK_DIR, "_build_ipa_v3_log.txt")

# Force UTF-8 stdio on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str) -> None:
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd: list[str], cwd: str = WORK_DIR, check: bool = False, timeout: int = 120) -> tuple[int, str, str]:
    """Run a command, return (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        if check and p.returncode != 0:
            log(f"CMD FAILED: {' '.join(cmd)}\n  STDOUT: {p.stdout}\n  STDERR: {p.stderr}")
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        log(f"CMD TIMEOUT: {' '.join(cmd)}")
        return -1, "", "timeout"
    except Exception as e:
        log(f"CMD EXCEPTION: {' '.join(cmd)} -> {e}")
        return -2, "", str(e)


def retry_gh(cmd: list[str], description: str, max_retries: int = 3, timeout: int = 120) -> tuple[int, str, str]:
    """Retry a gh / git command with exponential backoff (10s/20s/40s)."""
    delays = [10, 20, 40]
    last_rc, last_out, last_err = 0, "", ""
    for i in range(max_retries):
        log(f"[{description}] attempt {i+1}/{max_retries}: {' '.join(cmd)}")
        rc, out, err = run(cmd, timeout=timeout)
        last_rc, last_out, last_err = rc, out, err
        if rc == 0:
            return rc, out, err
        log(f"[{description}] failed (rc={rc}): {err[:300] if err else out[:300]}")
        if i < max_retries - 1:
            time.sleep(delays[i])
    return last_rc, last_out, last_err


def ensure_code_pushed() -> bool:
    """Commit all timezone-v3 changes and push to origin/master."""
    log("=== Step 1: ensure code committed & pushed ===")

    # Check status: if working tree clean and origin/master in sync, skip
    rc, out, _ = run(["git", "status", "--porcelain"])
    has_local_changes = bool(out.strip())

    # Fetch latest
    retry_gh(["git", "fetch", "origin"], "git fetch", max_retries=3, timeout=60)

    rc, out, _ = run(["git", "log", "origin/master..HEAD", "--oneline"])
    has_unpushed_commits = bool(out.strip())

    if not has_local_changes and not has_unpushed_commits:
        log("Working tree clean and origin/master in sync. No push needed.")
        return True

    if has_local_changes:
        log("Local changes detected, committing all v3 timezone fixes...")
        rc, out, err = run(["git", "add", "-A"], timeout=120)
        if rc != 0:
            log(f"git add failed: {err}")
            return False

        msg = "fix(timezone-v3): 全系统时间字段时区根治 - 多端 datetime_utils 统一调用 [v3]"
        rc, out, err = run(["git", "commit", "-m", msg], timeout=120)
        if rc != 0:
            # Maybe nothing to commit
            log(f"git commit rc={rc} stdout={out[:300]} stderr={err[:300]}")
            if "nothing to commit" not in out.lower() and "nothing to commit" not in err.lower():
                # try anyway
                pass

    # Push
    rc, out, err = retry_gh(["git", "push", "origin", "HEAD:master"], "git push", max_retries=3, timeout=180)
    if rc != 0:
        log(f"git push failed: rc={rc} err={err[:500]}")
        return False

    log("Push successful.")
    return True


def make_version_tag() -> str:
    """Generate version tag: ios-vYYYYMMDD-HHMMSS-XXXX"""
    now = datetime.now(timezone(timedelta(hours=8)))
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"ios-v{now.strftime('%Y%m%d-%H%M%S')}-{suffix}"


def trigger_workflow(version: str) -> bool:
    log(f"=== Step 2: trigger workflow with version={version} ===")
    rc, out, err = retry_gh(
        ["gh", "workflow", "run", WORKFLOW_FILE, "-f", f"version={version}"],
        "gh workflow run",
        max_retries=3,
        timeout=120,
    )
    if rc != 0:
        log(f"Trigger failed: {err}")
        return False
    log(f"Workflow triggered for {version}")
    return True


def find_run_id(version: str, max_wait_sec: int = 90) -> str | None:
    """Poll gh run list to find the run id corresponding to our trigger."""
    log("Waiting for run to appear...")
    start = time.time()
    while time.time() - start < max_wait_sec:
        rc, out, err = run([
            "gh", "run", "list",
            "--workflow", WORKFLOW_FILE,
            "--limit", "5",
            "--json", "databaseId,status,conclusion,createdAt,event,displayTitle,headBranch",
        ], timeout=60)
        if rc == 0 and out.strip():
            try:
                runs = json.loads(out)
            except Exception:
                runs = []
            # Pick the most recent workflow_dispatch run
            for r in runs:
                # Most recent comes first
                created = r.get("createdAt", "")
                # Only consider runs created within last 5 minutes
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - created_dt).total_seconds()
                    if age < 300 and r.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
                        log(f"Found run id={r['databaseId']} status={r['status']}")
                        return str(r["databaseId"])
                except Exception:
                    pass
            # Fallback: just take the latest
            if runs:
                first = runs[0]
                try:
                    created_dt = datetime.fromisoformat(first.get("createdAt", "").replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - created_dt).total_seconds()
                    if age < 120:
                        log(f"Fallback: using latest run id={first['databaseId']} status={first.get('status')}")
                        return str(first["databaseId"])
                except Exception:
                    pass
        time.sleep(5)
    return None


def poll_run(run_id: str, max_wait_min: int = 30) -> tuple[bool, str]:
    """Poll a workflow run until it finishes or times out.
    Returns (success, conclusion)."""
    log(f"=== Step 3: polling run {run_id} (max {max_wait_min} min) ===")
    start = time.time()
    deadline = start + max_wait_min * 60
    last_status = ""

    while time.time() < deadline:
        rc, out, err = run([
            "gh", "run", "view", run_id,
            "--json", "status,conclusion,displayTitle,createdAt,updatedAt,url",
        ], timeout=60)
        if rc != 0:
            log(f"poll view failed: {err[:200]}")
            time.sleep(30)
            continue
        try:
            info = json.loads(out)
        except Exception:
            log(f"failed to parse run view json: {out[:300]}")
            time.sleep(30)
            continue

        status = info.get("status", "")
        conclusion = info.get("conclusion", "")
        elapsed = int(time.time() - start)

        if status != last_status:
            log(f"  [{elapsed}s] status={status} conclusion={conclusion}")
            last_status = status

        if status == "completed":
            log(f"Run completed: conclusion={conclusion} (elapsed {elapsed}s)")
            return conclusion == "success", conclusion or ""

        log(f"  [{elapsed}s] still {status}, sleeping 30s...")
        time.sleep(30)

    log(f"Polling exceeded {max_wait_min} min limit")
    return False, "timeout"


def get_release_info(version: str) -> tuple[str | None, str | None]:
    """Return (release_page_url, ipa_download_url)."""
    log(f"=== Step 4: fetch release info for {version} ===")
    # Wait a bit for release to publish
    time.sleep(5)
    for attempt in range(5):
        rc, out, err = run([
            "gh", "release", "view", version,
            "--json", "url,assets,tagName",
        ], timeout=60)
        if rc == 0 and out.strip():
            try:
                info = json.loads(out)
                release_url = info.get("url") or f"https://github.com/{REPO}/releases/tag/{version}"
                assets = info.get("assets", [])
                ipa_url = None
                for a in assets:
                    if a.get("name", "").endswith(".ipa"):
                        ipa_url = a.get("url") or f"https://github.com/{REPO}/releases/download/{version}/{a.get('name')}"
                        break
                return release_url, ipa_url
            except Exception as e:
                log(f"parse release info failed: {e}")
        log(f"release view failed (attempt {attempt+1}): {err[:200]}")
        time.sleep(10)
    return None, None


def main() -> int:
    log("============================================")
    log("iOS IPA v3 timezone build START")
    log("============================================")

    # Step 1: ensure code pushed
    if not ensure_code_pushed():
        log("ERROR: failed to ensure code pushed")
        return 1

    # Step 2: generate version & trigger
    version = make_version_tag()
    log(f"Version tag: {version}")
    with open(os.path.join(WORK_DIR, "_ios_tag_v3.txt"), "w", encoding="utf-8") as f:
        f.write(version + "\n")

    if not trigger_workflow(version):
        log("ERROR: workflow trigger failed")
        return 2

    # Step 3: find run id & poll
    run_id = find_run_id(version)
    if not run_id:
        log("ERROR: could not find run id within 90s")
        return 3

    success, conclusion = poll_run(run_id, max_wait_min=30)
    actions_page = f"https://github.com/{REPO}/actions/runs/{run_id}"

    if not success:
        log(f"BUILD FAILED: conclusion={conclusion}")
        log(f"GitHub Actions page: {actions_page}")
        # Try to get logs summary
        rc, out, err = run(["gh", "run", "view", run_id, "--log-failed"], timeout=180)
        log(f"--- Failed log tail ---\n{out[-3000:] if out else err[-2000:]}")
        return 4

    # Step 4: get release info
    release_url, ipa_url = get_release_info(version)

    log("============================================")
    log("BUILD SUCCESS")
    log(f"Version tag        : {version}")
    log(f"Release page URL   : {release_url}")
    log(f"IPA download URL   : {ipa_url}")
    log(f"GH Actions run URL : {actions_page}")
    log("============================================")

    result = {
        "version": version,
        "release_url": release_url,
        "ipa_url": ipa_url,
        "actions_url": actions_page,
        "conclusion": conclusion,
    }
    with open(os.path.join(WORK_DIR, "_ios_build_result_v3.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
