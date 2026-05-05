#!/usr/bin/env python3
"""触发 GitHub Actions iOS 构建并轮询直到完成，最后输出 Release URL 和 IPA 下载 URL.

本次任务：订单详情页门店行整行点击触发 ContactStoreSheet (deploy id 6b099ed3)
"""
import json
import random
import subprocess
import sys
import time
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
MAX_WAIT_SEC = 30 * 60
INTERVAL = 30


def gen_tag():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choice("0123456789abcdef") for _ in range(4))
    return f"ios-v{ts}-{suffix}"


def retry_gh(args, max_retries=3, retry_delay=10, timeout=180, parse_json=False):
    last_err = ""
    delay = retry_delay
    for attempt in range(1, max_retries + 1):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                out = (r.stdout or "").strip()
                if parse_json:
                    return json.loads(out) if out else None
                return out
            last_err = (r.stderr or r.stdout or "").strip()
            print(f"[retry {attempt}/{max_retries}] gh failed: {last_err[:300]}", flush=True)
        except Exception as e:
            last_err = str(e)
            print(f"[retry {attempt}/{max_retries}] gh exception: {e}", flush=True)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"gh failed after {max_retries} retries: {last_err}")


def trigger_build(tag):
    print(f"\n>>> Triggering workflow with version={tag}", flush=True)
    retry_gh([
        "gh", "workflow", "run", WORKFLOW,
        "--repo", REPO,
        "-f", f"version={tag}",
    ])
    print("Workflow triggered, waiting for run id...", flush=True)
    time.sleep(8)


def get_latest_run_id():
    for attempt in range(8):
        data = retry_gh([
            "gh", "run", "list",
            "--repo", REPO,
            "--workflow", WORKFLOW,
            "--limit", "1",
            "--json", "databaseId,status,headBranch,displayTitle,createdAt",
        ], parse_json=True)
        if data:
            run = data[0]
            return str(run["databaseId"]), run
        time.sleep(5)
    raise RuntimeError("Could not get run id")


def poll_run(run_id):
    start = time.time()
    last_status = ""
    while True:
        elapsed = int(time.time() - start)
        if elapsed > MAX_WAIT_SEC:
            print(f"TIMEOUT after {elapsed}s", flush=True)
            return None
        try:
            data = retry_gh([
                "gh", "run", "view", run_id,
                "--repo", REPO,
                "--json", "status,conclusion,displayTitle,url",
            ], parse_json=True, max_retries=2, retry_delay=5)
        except Exception as e:
            print(f"[{elapsed}s] poll error: {e}", flush=True)
            time.sleep(INTERVAL)
            continue
        status = data.get("status", "?")
        conclusion = data.get("conclusion") or ""
        sig = f"{status}/{conclusion}"
        if sig != last_status:
            print(f"[{elapsed}s] status={status} conclusion={conclusion} url={data.get('url')}", flush=True)
            last_status = sig
        else:
            print(f"[{elapsed}s] still {status}", flush=True)
        if status == "completed":
            return conclusion
        time.sleep(INTERVAL)


def get_release_info(tag):
    rel = retry_gh([
        "gh", "release", "view", tag,
        "--repo", REPO,
        "--json", "url,assets",
    ], parse_json=True)
    return rel


def main():
    tag = gen_tag()
    print(f"=== iOS Store-Contact IPA Build ===")
    print(f"Tag: {tag}")
    print(f"Repo: {REPO}")

    trigger_build(tag)
    run_id, run_meta = get_latest_run_id()
    print(f"Run ID: {run_id}")
    print(f"Run meta: {json.dumps(run_meta, ensure_ascii=False)}")

    conclusion = poll_run(run_id)
    print(f"\n=== Build conclusion: {conclusion} ===")

    if conclusion != "success":
        print("BUILD FAILED")
        sys.exit(1)

    rel = get_release_info(tag)
    rel_url = rel.get("url", "")
    assets = rel.get("assets", []) or []
    ipa = next((a for a in assets if a.get("name", "").endswith(".ipa")), None)
    ipa_name = ipa.get("name") if ipa else ""
    ipa_url = ""
    if ipa:
        ipa_url = ipa.get("url") or ipa.get("apiUrl") or ""
    if not ipa_url and ipa_name and rel_url:
        ipa_url = f"https://github.com/{REPO}/releases/download/{tag}/{ipa_name}"
    size = ipa.get("size") if ipa else 0

    print("\n=== RESULT ===")
    print(f"TAG={tag}")
    print(f"RUN_ID={run_id}")
    print(f"CONCLUSION={conclusion}")
    print(f"RELEASE_URL={rel_url}")
    print(f"IPA_NAME={ipa_name}")
    print(f"IPA_URL={ipa_url}")
    print(f"IPA_SIZE={size}")


if __name__ == "__main__":
    main()
