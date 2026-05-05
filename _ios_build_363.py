"""iOS 构建触发脚本：通过 GitHub Actions 远程构建 IPA 并发布 Release。"""
import datetime
import json
import os
import secrets
import subprocess
import sys
import time

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
MAX_POLL_MIN = 30
POLL_INTERVAL = 30


def run(cmd, check=False, capture=True):
    print(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if capture:
        if r.stdout:
            print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr)
    if check and r.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    return r


def retry_gh(cmd, max_n=3):
    delay = 10
    for n in range(1, max_n + 1):
        r = run(cmd)
        if r.returncode == 0:
            return r
        print(f"gh 失败 (第 {n}/{max_n} 次)，{delay}s 后重试...")
        if n < max_n:
            time.sleep(delay)
            delay *= 2
    return r


def main():
    now = datetime.datetime.now()
    suffix = secrets.token_hex(2)
    tag = f"ios-login-layout-v{now.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    print(f"VERSION_TAG={tag}")

    print("=== Step 1: 触发 workflow ===")
    r = retry_gh(["gh", "workflow", "run", WORKFLOW, "-R", REPO, "-f", f"version={tag}", "--ref", "master"])
    if r.returncode != 0:
        print("ERROR: 触发 workflow 失败")
        sys.exit(2)

    time.sleep(8)

    print("=== Step 2: 获取 run id ===")
    run_id = None
    for _ in range(6):
        r = run(["gh", "run", "list", "-R", REPO, "-w", WORKFLOW, "--limit", "5", "--json", "databaseId,status,createdAt,headBranch"])
        if r.returncode == 0 and r.stdout.strip():
            try:
                runs = json.loads(r.stdout)
                if runs:
                    run_id = str(runs[0]["databaseId"])
                    print(f"RUN_ID={run_id}")
                    break
            except Exception as e:
                print(f"parse error: {e}")
        time.sleep(5)

    if not run_id:
        print("ERROR: 无法获取 run id")
        sys.exit(3)

    print("=== Step 3: 轮询构建状态 ===")
    deadline = time.time() + MAX_POLL_MIN * 60
    final_status = None
    final_concl = None
    while time.time() < deadline:
        r = run(["gh", "run", "view", run_id, "-R", REPO, "--json", "status,conclusion,displayTitle"])
        if r.returncode == 0 and r.stdout.strip():
            try:
                info = json.loads(r.stdout)
                status = info.get("status")
                concl = info.get("conclusion")
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] status={status} conclusion={concl}")
                if status == "completed":
                    final_status = status
                    final_concl = concl
                    break
            except Exception as e:
                print(f"parse error: {e}")
        time.sleep(POLL_INTERVAL)

    if final_status != "completed":
        print("ERROR: 构建超时（30分钟）")
        run(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"])
        sys.exit(4)

    if final_concl != "success":
        print(f"ERROR: 构建失败 conclusion={final_concl}")
        run(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"])
        sys.exit(5)

    print("=== Step 4: 获取 Release 信息 ===")
    r = retry_gh(["gh", "release", "view", tag, "-R", REPO, "--json", "url,assets"])
    if r.returncode != 0:
        print("ERROR: 无法获取 Release 信息")
        sys.exit(6)

    info = json.loads(r.stdout)
    release_url = f"https://github.com/{REPO}/releases/tag/{tag}"
    ipa_url = None
    for a in info.get("assets", []):
        name = a.get("name", "")
        if name.endswith(".ipa"):
            ipa_url = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
            break

    if not ipa_url:
        print("ERROR: 未找到 ipa 文件")
        sys.exit(7)

    print()
    print("=" * 60)
    print(f"IOS_RELEASE_PAGE={release_url}")
    print(f"IOS_IPA_DOWNLOAD={ipa_url}")
    print("=" * 60)

    with open("_ios_build_363_result.txt", "w", encoding="utf-8") as f:
        f.write(f"IOS_RELEASE_PAGE={release_url}\n")
        f.write(f"IOS_IPA_DOWNLOAD={ipa_url}\n")


if __name__ == "__main__":
    main()
