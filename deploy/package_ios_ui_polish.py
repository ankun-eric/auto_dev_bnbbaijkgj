# -*- coding: utf-8 -*-
"""
iOS IPA build via GitHub Actions.

- Triggers workflow: .github/workflows/ios-build.yml on ankun-eric/auto_dev_bnbbaijkgj
- Version tag format: ios-v{YYYYMMDD}-{HHMMSS}-{4-hex}
- Polls build status every 30s (up to 30 min)
- On success, reads release info (page URL, IPA asset URL & size)
- Retries for network instability; on build failure, dumps failing log and retries up to 2 times total
"""

import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "ios-build.yml"
WORKFLOW_PATH = r"C:\auto_output\bnbbaijkgj\.github\workflows\ios-build.yml"
POLL_INTERVAL_SEC = 30
MAX_POLL_MINUTES = 30
MAX_BUILD_ATTEMPTS = 2
NET_RETRY_DELAYS = [10, 20, 40]


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_gh(args, capture=True, retries=3, timeout=120):
    """Run `gh` with retry for transient network errors."""
    last_err = ""
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                ["gh"] + args,
                capture_output=capture,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if proc.returncode == 0:
                return proc.stdout or ""
            last_err = f"rc={proc.returncode} stderr={proc.stderr.strip()} stdout={(proc.stdout or '').strip()}"
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout after {timeout}s: {e}"
        except Exception as e:
            last_err = f"exception: {e!r}"

        if attempt < retries - 1:
            delay = NET_RETRY_DELAYS[min(attempt, len(NET_RETRY_DELAYS) - 1)]
            log(f"gh {args[0]} failed ({last_err}); retry in {delay}s ({attempt+1}/{retries})")
            time.sleep(delay)
    raise RuntimeError(f"gh command failed after {retries} attempts: gh {' '.join(args)} -> {last_err}")


def gen_version_tag() -> str:
    now = datetime.now()
    return f"ios-v{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{secrets.token_hex(2)}"


def trigger_workflow(tag: str) -> None:
    log(f"Triggering workflow {WORKFLOW_FILE} with version={tag}")
    run_gh([
        "workflow", "run", WORKFLOW_FILE,
        "-R", REPO,
        "-f", f"version={tag}",
    ])
    log("Workflow dispatch accepted by GitHub")


def find_run_id(tag: str, since: float) -> str:
    """Find the run triggered for this tag. We match by workflow name + createdAt > since."""
    deadline = time.time() + 120
    while time.time() < deadline:
        out = run_gh([
            "run", "list",
            "-R", REPO,
            "--workflow", WORKFLOW_FILE,
            "--limit", "5",
            "--json", "databaseId,status,conclusion,createdAt,event,displayTitle,name",
        ])
        try:
            runs = json.loads(out)
        except json.JSONDecodeError:
            runs = []
        for r in runs:
            # workflow_dispatch events only
            if r.get("event") != "workflow_dispatch":
                continue
            # Parse createdAt (ISO8601 Z)
            created = r.get("createdAt", "")
            try:
                dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                t = dt.timestamp()
            except ValueError:
                continue
            if t + 5 >= since:  # small skew tolerance
                rid = str(r["databaseId"])
                log(f"Matched run: id={rid} status={r.get('status')} createdAt={created}")
                return rid
        log("Run not yet listed; waiting 5s...")
        time.sleep(5)
    raise RuntimeError("Could not locate triggered workflow run within 2 minutes")


def poll_run(run_id: str):
    """Poll until completed; returns (conclusion, status)."""
    log(f"Polling run {run_id} every {POLL_INTERVAL_SEC}s (max {MAX_POLL_MINUTES} min)")
    deadline = time.time() + MAX_POLL_MINUTES * 60
    last_status = ""
    while time.time() < deadline:
        out = run_gh([
            "run", "view", run_id,
            "-R", REPO,
            "--json", "status,conclusion,url",
        ])
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = {}
        status = data.get("status", "")
        conclusion = data.get("conclusion", "")
        if status != last_status:
            log(f"Run status: {status} conclusion={conclusion} url={data.get('url','')}")
            last_status = status
        if status == "completed":
            return conclusion, status
        time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError(f"Run {run_id} did not complete within {MAX_POLL_MINUTES} minutes")


def get_failed_log(run_id: str) -> str:
    try:
        out = run_gh([
            "run", "view", run_id,
            "-R", REPO,
            "--log-failed",
        ], timeout=180)
        return out
    except Exception as e:
        return f"<failed to fetch log: {e}>"


def get_release_info(tag: str):
    out = run_gh([
        "release", "view", tag,
        "-R", REPO,
        "--json", "url,name,assets,tagName,publishedAt",
    ])
    data = json.loads(out)
    release_url = data.get("url") or f"https://github.com/{REPO}/releases/tag/{tag}"
    assets = data.get("assets", [])
    ipa = None
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa = a
            break
    return release_url, ipa, data


def build_once(tag: str, adopt_run_id: str = None):
    """Run one build attempt. Returns dict with results or raises on failure."""
    started = time.time()
    if adopt_run_id:
        log(f"Adopting existing run_id={adopt_run_id} (skip dispatch); tag={tag}")
        run_id = adopt_run_id
    else:
        trigger_workflow(tag)
        time.sleep(8)
        run_id = find_run_id(tag, since=started - 5)
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"Run URL: {run_url}")
    conclusion, _ = poll_run(run_id)
    duration = int(time.time() - started)
    if conclusion != "success":
        log(f"Build failed with conclusion={conclusion}")
        fail_log = get_failed_log(run_id)
        raise RuntimeError(f"Build {run_id} concluded={conclusion}\n---failed log (truncated)---\n{fail_log[-6000:]}")
    log(f"Build succeeded in {duration}s; fetching release info...")
    release_url, ipa, raw = get_release_info(tag)
    if not ipa:
        raise RuntimeError(f"No .ipa asset found in release {tag}; release raw: {json.dumps(raw)[:800]}")
    return {
        "version_tag": tag,
        "run_id": run_id,
        "run_url": run_url,
        "release_url": release_url,
        "ipa_name": ipa.get("name"),
        "ipa_url": ipa.get("url") or f"https://github.com/{REPO}/releases/download/{tag}/{ipa.get('name')}",
        "ipa_download_url": f"https://github.com/{REPO}/releases/download/{tag}/{ipa.get('name')}",
        "ipa_size_bytes": ipa.get("size"),
        "duration_sec": duration,
    }


def main() -> int:
    log(f"iOS packaging started for repo {REPO}")
    log(f"Workflow: {WORKFLOW_PATH}")

    # Optional: adopt an existing in-progress run via CLI args: --adopt <run_id> --tag <tag>
    adopt_run_id = None
    adopt_tag = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--adopt" and i + 1 < len(args):
            adopt_run_id = args[i + 1]; i += 2
        elif args[i] == "--tag" and i + 1 < len(args):
            adopt_tag = args[i + 1]; i += 2
        else:
            i += 1

    attempts = []
    for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
        if attempt == 1 and adopt_run_id and adopt_tag:
            tag = adopt_tag
            log(f"=== Attempt {attempt}/{MAX_BUILD_ATTEMPTS} ; adopting run {adopt_run_id} tag={tag} ===")
        else:
            tag = gen_version_tag()
            log(f"=== Attempt {attempt}/{MAX_BUILD_ATTEMPTS} ; tag={tag} ===")
        try:
            if attempt == 1 and adopt_run_id and adopt_tag:
                result = build_once(tag, adopt_run_id=adopt_run_id)
                adopt_run_id = None  # only once
            else:
                result = build_once(tag)
            result["attempts"] = attempt
            print("\n=== iOS BUILD RESULT ===")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            # Human-readable summary
            size_mb = (result["ipa_size_bytes"] or 0) / 1024 / 1024
            print("\n--- Summary ---")
            print(f"Version Tag       : {result['version_tag']}")
            print(f"Release Page URL  : {result['release_url']}")
            print(f"IPA Download URL  : {result['ipa_download_url']}")
            print(f"IPA Size          : {size_mb:.2f} MiB ({result['ipa_size_bytes']} bytes)")
            print(f"Build Duration    : {result['duration_sec']}s")
            print(f"Actions Run URL   : {result['run_url']}")
            # Persist JSON next to script
            out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "package_ios_ui_polish_result.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            log(f"Result saved to {out_path}")
            return 0
        except Exception as e:
            err_msg = str(e)
            log(f"Attempt {attempt} failed: {err_msg[:500]}")
            attempts.append({"tag": tag, "error": err_msg})
            if attempt < MAX_BUILD_ATTEMPTS:
                log("Will retry with a fresh tag after 15s...")
                time.sleep(15)

    print("\n=== iOS BUILD FAILED ===")
    print(json.dumps({"attempts": attempts}, indent=2, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
