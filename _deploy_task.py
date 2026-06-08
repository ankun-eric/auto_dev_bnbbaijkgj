
import subprocess
import sys
import os
import time

REPO = r"C:\auto_output\bnbbaijkgj"
GIT = r"C:\Program Files\Git\cmd\git.exe"

def run_git(args, timeout=120):
    cmd = [GIT] + args
    print(f"Running: {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        if p.stdout:
            print(p.stdout)
        if p.stderr:
            print(p.stderr, file=sys.stderr)
        return p.returncode
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after {timeout}s")
        return -1
    except Exception as e:
        print(f"ERROR: {e}")
        return -1

def main():
    # Step 1: Add files
    print("=== Step 1: git add ===")
    files_to_add = [
        "backend/app/api/medication_history_v1.py",
        "backend/app/schemas/medication_history.py",
        "backend/tests/test_medication_history_v1.py",
        "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/history/page.tsx",
        "h5-web/src/lib/api/medication.ts",
        "backend/app/models/models.py",
        "backend/app/main.py",
        "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/page.tsx",
    ]
    rc = run_git(["add"] + files_to_add, timeout=120)
    if rc != 0:
        print("ERROR: git add failed")
        return 1
    
    # Step 2: Commit
    print("\n=== Step 2: git commit ===")
    rc = run_git(["commit", "-m", "feat: add medication reminder history check-in feature"], timeout=120)
    if rc != 0:
        print("git commit might have nothing to commit (OK if already committed)")
    
    # Step 3: Push with retry
    print("\n=== Step 3: git push ===")
    for attempt in range(1, 4):
        print(f"\nPush attempt {attempt}/3...")
        rc = run_git(["push", "codeup", "master"], timeout=180)
        if rc == 0:
            print("PUSH SUCCESS!")
            return 0
        print(f"Push failed (rc={rc}), retrying in 5s...")
        time.sleep(5)
    
    print("PUSH FAILED after 3 attempts!")
    return 1

if __name__ == "__main__":
    sys.exit(main())
