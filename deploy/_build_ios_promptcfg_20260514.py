"""Trigger GitHub Actions iOS build & poll for completion.

- Uses workflow_dispatch with `version` input as the release tag.
- Retries gh commands up to 3 times with 10s/20s/40s backoff.
- Polls every 30s up to 30 minutes.
- Prints final IPA filename, Release URL, IPA direct URL, and Run ID.
"""
from __future__ import annotations

import json
import secrets
import subprocess
import sys
import time

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
BRANCH = "master"
POLL_INTERVAL = 30
MAX_WAIT = 30 * 60  # 30 minutes


def retry_gh(args: list[str], capture: bool = True, attempts: int = 3) -> subprocess.CompletedProcess:
    delays = [10, 20, 40]
    last_err = None
    for i in range(attempts):
        try:
            r = subprocess.run(
                ["gh", *args],
                capture_output=capture,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if r.returncode == 0:
                return r
            last_err = f"exit={r.returncode} stderr={r.stderr}"
            print(f"[retry_gh] attempt {i+1}/{attempts} failed: {last_err}", flush=True)
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            print(f"[retry_gh] attempt {i+1}/{attempts} exception: {e}", flush=True)
        if i < attempts - 1:
            time.sleep(delays[i])
    raise RuntimeError(f"gh {' '.join(args)} failed after {attempts} attempts: {last_err}")


def main() -> int:
    tag = f"ios-promptcfg-v{int(time.time())}-{secrets.token_hex(2)}"
    print(f"[tag] {tag}", flush=True)

    # 1) record current latest run id before dispatch to detect the new one
    pre = retry_gh([
        "run", "list", "-R", REPO, "--workflow", WORKFLOW,
        "--limit", "5", "--json", "databaseId,status,headBranch,createdAt",
    ])
    pre_runs = json.loads(pre.stdout or "[]")
    pre_ids = {r["databaseId"] for r in pre_runs}
    print(f"[pre_run_ids] {sorted(pre_ids)}", flush=True)

    # 2) dispatch workflow with version=tag
    print(f"[dispatch] triggering {WORKFLOW} version={tag}", flush=True)
    retry_gh([
        "workflow", "run", WORKFLOW, "-R", REPO,
        "--ref", BRANCH, "-f", f"version={tag}",
    ])

    # 3) find the new run id (poll for it briefly)
    run_id = None
    for _ in range(20):
        time.sleep(3)
        r = retry_gh([
            "run", "list", "-R", REPO, "--workflow", WORKFLOW,
            "--limit", "10", "--json", "databaseId,status,headBranch,createdAt",
        ])
        runs = json.loads(r.stdout or "[]")
        candidates = [x for x in runs if x["databaseId"] not in pre_ids]
        if candidates:
            run_id = candidates[0]["databaseId"]
            break
    if run_id is None and runs:
        run_id = runs[0]["databaseId"]
        print(f"[warn] fallback to latest run_id={run_id}", flush=True)
    if run_id is None:
        print("[err] could not locate workflow run", flush=True)
        return 2
    print(f"[run_id] {run_id}", flush=True)
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    print(f"[run_url] {run_url}", flush=True)

    # 4) poll
    deadline = time.time() + MAX_WAIT
    final_status = None
    final_conclusion = None
    while time.time() < deadline:
        try:
            r = retry_gh([
                "run", "view", str(run_id), "-R", REPO,
                "--json", "status,conclusion,displayTitle,headSha",
            ])
            info = json.loads(r.stdout or "{}")
        except Exception as e:  # noqa: BLE001
            print(f"[poll] view failed: {e}", flush=True)
            time.sleep(POLL_INTERVAL)
            continue
        status = info.get("status")
        conclusion = info.get("conclusion")
        remaining = int(deadline - time.time())
        print(f"[poll] status={status} conclusion={conclusion} remaining={remaining}s", flush=True)
        if status == "completed":
            final_status = status
            final_conclusion = conclusion
            break
        time.sleep(POLL_INTERVAL)

    if final_status != "completed":
        print("[timeout] build did not finish within 30 minutes", flush=True)
        print(f"RUN_ID={run_id}")
        print(f"RUN_URL={run_url}")
        print(f"TAG={tag}")
        print("RELEASE_URL=")
        print("IPA_URL=")
        return 3

    if final_conclusion != "success":
        print(f"[fail] conclusion={final_conclusion}", flush=True)
        print(f"RUN_ID={run_id}")
        print(f"RUN_URL={run_url}")
        print(f"TAG={tag}")
        print("RELEASE_URL=")
        print("IPA_URL=")
        return 4

    # 5) fetch release info
    try:
        r = retry_gh([
            "release", "view", tag, "-R", REPO,
            "--json", "tagName,name,url,assets",
        ])
        rel = json.loads(r.stdout or "{}")
    except Exception as e:  # noqa: BLE001
        print(f"[err] release view failed: {e}", flush=True)
        rel = {}

    release_url = rel.get("url") or f"https://github.com/{REPO}/releases/tag/{tag}"
    ipa_name = None
    ipa_url = None
    for a in rel.get("assets", []) or []:
        if a.get("name", "").endswith(".ipa"):
            ipa_name = a["name"]
            ipa_url = a.get("url") or f"https://github.com/{REPO}/releases/download/{tag}/{ipa_name}"
            break
    if not ipa_url and ipa_name is None:
        ipa_name = "bini_health_ios.ipa"
        ipa_url = f"https://github.com/{REPO}/releases/download/{tag}/{ipa_name}"

    print("")
    print("=" * 60)
    print(f"IPA_NAME={ipa_name}")
    print(f"RUN_ID={run_id}")
    print(f"TAG={tag}")
    print(f"RELEASE_URL={release_url}")
    print(f"IPA_URL={ipa_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
