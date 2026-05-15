"""One-shot script: trigger GitHub Actions iOS build and return Release URLs.

Steps:
1. Ensure .github/workflows/ios-build.yml exists (reused if present).
2. gh auth login --with-token using the provided token.
3. Trigger workflow with a fresh version tag (ios-v<YYYYMMDD-HHMMSS>-<hex4>).
4. Poll run status every 30s, max 30 minutes.
5. On success: fetch Release page and IPA download URL via gh release view.

All gh commands are wrapped with a 3-attempt retry (10s, 20s, 40s back-off).

Usage:
    python scripts/build_ios_prd_aichat_home_grid_v1.py
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
TOKEN = os.environ.get("GH_PAT_TOKEN", "")  # 通过环境变量注入，避免明文 commit

POLL_INTERVAL_SEC = 30
MAX_WAIT_SEC = 30 * 60
MAX_RETRIES = 3
RETRY_BACKOFF = [10, 20, 40]


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _clean_env() -> dict:
    """Return a copy of os.environ without GITHUB_TOKEN/GH_TOKEN/etc.

    gh refuses ``auth login --with-token`` when GITHUB_TOKEN is set in env,
    and also prefers env tokens over the stored auth for other commands.
    To make the token from gh_auth_login actually take effect we strip
    these vars from the subprocess environment for every gh invocation.
    """
    env = os.environ.copy()
    for k in ("GITHUB_TOKEN", "GH_TOKEN", "GH_ENTERPRISE_TOKEN",
              "GITHUB_ENTERPRISE_TOKEN"):
        env.pop(k, None)
    return env


def run_cmd(cmd: list[str], timeout: int = 120,
            stdin_data: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_clean_env(),
    )


def run_gh(args: list[str], retries: int = MAX_RETRIES,
           timeout: int = 120) -> subprocess.CompletedProcess:
    last_err = None
    for i in range(retries):
        try:
            res = run_cmd(["gh", *args], timeout=timeout)
            if res.returncode == 0:
                return res
            last_err = (
                f"exit={res.returncode}\n"
                f"stdout={res.stdout}\n"
                f"stderr={res.stderr}"
            )
            log(f"gh {' '.join(args)} failed (attempt {i+1}/{retries}): "
                f"{last_err[:300]}")
        except Exception as e:  # pragma: no cover - network errors
            last_err = repr(e)
            log(f"gh {' '.join(args)} exception "
                f"(attempt {i+1}/{retries}): {last_err}")
        if i < retries - 1:
            wait = RETRY_BACKOFF[min(i, len(RETRY_BACKOFF) - 1)]
            log(f"retrying after {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(
        f"gh command failed after {retries} retries: gh {' '.join(args)}\n"
        f"{last_err}"
    )


def gh_auth_login(token: str) -> None:
    log("gh auth login --with-token (via stdin)")
    last_err = None
    for i in range(MAX_RETRIES):
        try:
            res = run_cmd(
                ["gh", "auth", "login", "--with-token"],
                timeout=60,
                stdin_data=token,
            )
            if res.returncode == 0:
                log("gh auth login OK")
                break
            last_err = (
                f"exit={res.returncode} stdout={res.stdout} "
                f"stderr={res.stderr}"
            )
            log(f"gh auth login failed (attempt {i+1}): {last_err[:300]}")
        except Exception as e:
            last_err = repr(e)
            log(f"gh auth login exception (attempt {i+1}): {last_err}")
        if i < MAX_RETRIES - 1:
            wait = RETRY_BACKOFF[min(i, len(RETRY_BACKOFF) - 1)]
            log(f"retrying gh auth login after {wait}s ...")
            time.sleep(wait)
    else:
        raise RuntimeError(f"gh auth login failed: {last_err}")

    res = run_gh(["auth", "status"])
    log(f"auth status:\n{res.stdout}{res.stderr}")


def ensure_workflow_exists() -> None:
    wf_path = os.path.join(".github", "workflows", "ios-build.yml")
    if os.path.exists(wf_path):
        log(f"Workflow exists: {wf_path}")
    else:
        raise FileNotFoundError(
            f"{wf_path} not found and this script will not create it "
            "automatically (assumes repo has the canonical one)."
        )


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
        "--json", "databaseId,displayTitle,name,createdAt,event,"
                  "status,conclusion",
    ])
    runs = json.loads(res.stdout)
    for r in runs:
        if r.get("event") != "workflow_dispatch":
            continue
        try:
            created = datetime.strptime(
                r["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
            ).timestamp()
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
        log(f"  run {run_id}: status={status} "
            f"conclusion={conclusion} elapsed={elapsed}s")
        if status == "completed":
            return conclusion or ""
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(
        f"Run {run_id} did not complete within {MAX_WAIT_SEC}s"
    )


def dump_failed_logs(run_id: str, tail_lines: int = 200) -> str:
    try:
        res = run_cmd(
            ["gh", "run", "view", run_id, "-R", REPO, "--log-failed"],
            timeout=180,
        )
        out = (res.stdout or "") + (res.stderr or "")
        lines = out.splitlines()
        tail = "\n".join(lines[-tail_lines:])
        log(f"--- failed log tail ({tail_lines} lines) ---\n"
            f"{tail}\n--- end ---")
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


def verify_url(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 ios-build-checker"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return -1, repr(e)


def main() -> int:
    overall_start = time.time()

    ensure_workflow_exists()
    gh_auth_login(TOKEN)

    version = generate_version()
    log(f"Generated version tag: {version}")

    trigger_started = time.time()
    trigger_workflow(version)

    time.sleep(8)
    run_id = None
    for attempt in range(8):
        try:
            run_id = find_run_id(version, trigger_started)
        except Exception as e:
            log(f"find_run_id error: {e}")
            run_id = None
        if run_id:
            break
        log(f"run not found yet, retry {attempt+1}/8")
        time.sleep(5)
    if not run_id:
        log("ERROR: could not locate the dispatched run")
        return 2
    log(f"Tracking run id: {run_id}")
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"Run URL: {run_url}")

    try:
        conclusion = wait_for_run(run_id)
    except TimeoutError as e:
        log(f"TIMEOUT: {e}")
        dump_failed_logs(run_id)
        elapsed = int(time.time() - trigger_started)
        log("=" * 60)
        log(f"BUILD_TIMEOUT version={version} run_id={run_id} "
            f"elapsed={elapsed}s")
        log(f"Run URL: {run_url}")
        log("=" * 60)
        return 6
    build_seconds = int(time.time() - trigger_started)
    log(f"Build finished with conclusion={conclusion} in {build_seconds}s")

    if conclusion != "success":
        dump_failed_logs(run_id)
        log("=" * 60)
        log(f"BUILD_FAILED version={version} run_id={run_id} "
            f"conclusion={conclusion}")
        log(f"Run URL: {run_url}")
        log("=" * 60)
        return 3

    try:
        rel = get_release(version)
    except Exception as e:
        log(f"Could not fetch release: {e}")
        return 4

    release_url = (
        rel.get("url")
        or f"https://github.com/{REPO}/releases/tag/{version}"
    )
    assets = rel.get("assets") or []
    ipa_url = None
    ipa_name = None
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa_url = (
                a.get("url")
                or a.get("browserDownloadUrl")
                or a.get("apiUrl")
            )
            ipa_name = name
            break
    if not ipa_url and assets:
        a = assets[0]
        ipa_url = a.get("url") or a.get("browserDownloadUrl")
        ipa_name = a.get("name")

    if not ipa_url:
        ipa_url = (
            f"https://github.com/{REPO}/releases/download/"
            f"{version}/bini_health_ios.ipa"
        )
        ipa_name = "bini_health_ios.ipa"

    log(f"Release URL: {release_url}")
    log(f"IPA download URL: {ipa_url}")

    rel_code, rel_ctype = verify_url(release_url)
    log(f"Release page HTTP status: {rel_code} ({rel_ctype})")

    total = int(time.time() - overall_start)
    log("=" * 60)
    log("BUILD_SUCCESS")
    log(f"  version:       {version}")
    log(f"  run_id:        {run_id}")
    log(f"  run_url:       {run_url}")
    log(f"  release_url:   {release_url}")
    log(f"  ipa_download:  {ipa_url}")
    log(f"  ipa_name:      {ipa_name}")
    log(f"  release_http:  {rel_code}")
    log(f"  build_seconds: {build_seconds}")
    log(f"  total_seconds: {total}")
    log("=" * 60)

    out = {
        "version": version,
        "run_id": run_id,
        "run_url": run_url,
        "release_url": release_url,
        "ipa_download": ipa_url,
        "ipa_name": ipa_name,
        "release_http": rel_code,
        "build_seconds": build_seconds,
        "total_seconds": total,
        "conclusion": conclusion,
    }
    print("RESULT_JSON=" + json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
