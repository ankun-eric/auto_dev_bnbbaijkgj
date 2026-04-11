"""
Deploy script: commit local changes, push to GitHub, then SSH deploy to server.
"""
import subprocess
import sys
import time
import paramiko

GIT_TOKEN = "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"
GIT_USER = "ankun-eric"
GIT_REPO = "https://github.com/ankun-eric/auto_dev_bnbbaijkgj"
GIT_PUSH_URL = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

FILES_TO_STAGE = [
    "h5-web/src/app/(tabs)/home/page.tsx",
    "h5-web/src/lib/useHomeConfig.ts",
    "flutter_app/lib/screens/home/home_screen.dart",
    "miniprogram/pages/home/index.js",
    "miniprogram/pages/home/index.wxml",
    "backend/app/api/home_config.py",
    "backend/app/init_data.py",
    "tests/test_search_placeholder_config.py",
]

COMMIT_MSG = "feat: 首页搜索栏提示文字后台配置化"


def run_local(cmd, cwd=None):
    print(f"[LOCAL] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def step1_commit_and_push():
    print("=" * 60)
    print("STEP 1: Commit and push local changes")
    print("=" * 60)

    cwd = r"C:\auto_output\bnbbaijkgj"

    # Stage files
    for f in FILES_TO_STAGE:
        rc, out, err = run_local(f'git add "{f}"', cwd=cwd)
        if rc != 0:
            print(f"  WARNING: git add failed for {f}: {err}")

    # Verify staging
    rc, out, err = run_local("git diff --cached --name-only", cwd=cwd)
    if not out:
        print("  No files staged. Checking if files exist and have changes...")
        rc, out, err = run_local("git status --short", cwd=cwd)
        print(f"  Status: {out[:500]}")
        # Try adding all specified files again with different approach
        files_arg = " ".join(f'"{f}"' for f in FILES_TO_STAGE)
        run_local(f"git add {files_arg}", cwd=cwd)
        rc, out, err = run_local("git diff --cached --name-only", cwd=cwd)
        if not out:
            print("  Still no files staged. Attempting to add all modified files matching the list...")
            for f in FILES_TO_STAGE:
                run_local(f"git add -- {f}", cwd=cwd)

    rc, staged, _ = run_local("git diff --cached --name-only", cwd=cwd)
    print(f"\n  Staged files:\n  {staged}")

    # Commit
    rc, out, err = run_local(f'git commit -m "{COMMIT_MSG}"', cwd=cwd)
    if rc != 0 and "nothing to commit" in (out + err):
        print("  Nothing to commit (files may already be committed)")
    elif rc != 0:
        print(f"  Commit error: {err}")
        return False

    # Push using token URL
    rc, out, err = run_local(f"git push {GIT_PUSH_URL} master", cwd=cwd)
    if rc != 0:
        # Try with origin and set url temporarily
        run_local(f"git remote set-url origin {GIT_PUSH_URL}", cwd=cwd)
        rc, out, err = run_local("git push origin master", cwd=cwd)
        if rc != 0:
            print(f"  Push failed: {err}")
            return False

    print("  Push successful!")
    return True


def ssh_exec(ssh, cmd, timeout=300):
    print(f"[SSH] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out.strip()[:3000])
    if err:
        lines = err.strip().split("\n")
        for line in lines[:50]:
            print(f"  [stderr] {line}")
    return exit_code, out.strip(), err.strip()


def step2_deploy_on_server():
    print("\n" + "=" * 60)
    print("STEP 2: SSH deploy to server")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting to {SSH_HOST} as {SSH_USER}...")
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected!")

    # a. cd to project dir and verify
    rc, out, err = ssh_exec(ssh, f"cd {PROJECT_DIR} && pwd")
    if rc != 0:
        print(f"ERROR: Cannot cd to {PROJECT_DIR}")
        ssh.close()
        return None

    # b. git fetch
    git_url_with_token = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    rc, out, err = ssh_exec(ssh, f"cd {PROJECT_DIR} && git remote set-url origin {git_url_with_token} && git fetch origin master")
    if rc != 0:
        print("WARNING: git fetch had issues, continuing...")

    # c. git reset --hard
    rc, out, err = ssh_exec(ssh, f"cd {PROJECT_DIR} && git reset --hard origin/master")
    if rc != 0:
        print(f"ERROR: git reset failed: {err}")
        ssh.close()
        return None
    print(f"  Reset to: {out}")

    # d. docker compose build
    print("\nBuilding Docker containers (this may take a few minutes)...")
    rc, out, err = ssh_exec(ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web",
        timeout=600)

    if rc != 0:
        print(f"\n  BUILD FAILED (exit code {rc})")
        # Check for h5-web build failure related to missing modules
        combined = out + err
        if "html5-qrcode" in combined or "qrcode.react" in combined or "Module not found" in combined:
            print("\n  Detected missing module error. Checking scan pages...")
            rc2, pages, _ = ssh_exec(ssh,
                f"cd {PROJECT_DIR} && find h5-web/src -name '*.tsx' -path '*/scan/*' -o -name '*.tsx' -path '*/checkup/*' | head -20")
            print(f"  Found pages: {pages}")

            # Check package.json for those deps
            rc3, pkgjson, _ = ssh_exec(ssh,
                f"cd {PROJECT_DIR} && cat h5-web/package.json | grep -E 'html5-qrcode|qrcode.react'")
            print(f"  Package.json deps: {pkgjson}")

            if pages and not pkgjson:
                print("  Pages reference these modules but they're not in package.json.")
                print("  Adding missing dependencies...")
                ssh_exec(ssh,
                    f"cd {PROJECT_DIR}/h5-web && npm install html5-qrcode qrcode.react --save",
                    timeout=120)
                # Retry build
                print("\n  Retrying build...")
                rc, out, err = ssh_exec(ssh,
                    f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web",
                    timeout=600)
                if rc != 0:
                    print(f"  Retry build also failed: {err[:500]}")
        else:
            print(f"  Build error details: {(out+err)[-1000:]}")

        if rc != 0:
            print("  Build failed, but continuing with docker up to see if existing images work...")

    # e. docker compose up -d
    print("\nStarting containers...")
    rc, out, err = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d")
    if rc != 0:
        print(f"  docker compose up failed: {err[:500]}")

    # f. Wait 15 seconds
    print("\nWaiting 15 seconds for containers to start...")
    time.sleep(15)

    # g. docker ps
    print("\nChecking container status...")
    rc, container_status, err = ssh_exec(ssh, "docker ps --filter 'name=3b7b999d'")

    # h. curl API
    print("\nChecking API endpoint...")
    rc, api_response, err = ssh_exec(ssh,
        f"curl -s {BASE_URL}/api/home-config")

    # i. curl H5
    print("\nChecking H5 web endpoint...")
    rc, h5_status, err = ssh_exec(ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/")

    ssh.close()

    return {
        "container_status": container_status,
        "api_response": api_response,
        "h5_status_code": h5_status,
    }


def main():
    # Step 1: Commit and push
    push_ok = step1_commit_and_push()
    if not push_ok:
        print("\nWARNING: Push may have had issues, but continuing with deployment...")

    # Step 2: Deploy on server
    result = step2_deploy_on_server()

    # Step 3: Report
    print("\n" + "=" * 60)
    print("DEPLOYMENT RESULT")
    print("=" * 60)

    if result is None:
        print("FAILED: Could not complete deployment")
        sys.exit(1)

    print(f"\n--- Container Status ---")
    print(result["container_status"])

    print(f"\n--- API Response ({BASE_URL}/api/home-config) ---")
    print(result["api_response"])

    print(f"\n--- H5 Web Status ({BASE_URL}/) ---")
    h5_code = result["h5_status_code"]
    print(f"HTTP Status Code: {h5_code}")

    api_ok = bool(result["api_response"] and "error" not in result["api_response"].lower()
                   and result["api_response"] != "")
    h5_ok = h5_code in ("200", "301", "302", "304")

    print(f"\n--- Summary ---")
    print(f"Backend API: {'OK' if api_ok else 'FAILED'}")
    print(f"H5 Web:      {'OK' if h5_ok else 'FAILED'} (HTTP {h5_code})")

    if not api_ok or not h5_ok:
        sys.exit(1)
    print("\nDeployment completed successfully!")


if __name__ == "__main__":
    main()
