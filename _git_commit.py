"""
Git commit and push script for medication history deployment.
"""
import subprocess
import sys
import os

REPO_DIR = r"C:\auto_output\bnbbaijkgj"
GIT_EXE = r"C:\Program Files\Git\cmd\git.exe"

# Files to add
FILES_TO_ADD = [
    "backend/app/api/medication_history_v1.py",
    "backend/app/schemas/medication_history.py",
    "backend/tests/test_medication_history_v1.py",
    "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/history/page.tsx",
    "h5-web/src/lib/api/medication.ts",
    "backend/app/models/models.py",
    "backend/app/main.py",
    "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/page.tsx",
]

def run_git(args, timeout=120):
    """Run git command and return result."""
    cmd = [GIT_EXE] + args
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, timeout=timeout)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after {timeout}s")
        return -1, "", "TIMEOUT"
    except Exception as e:
        print(f"ERROR: {e}")
        return -1, "", str(e)

def main():
    # Step 1: Add files
    print("=== Step 1: git add ===")
    rc, out, err = run_git(["add"] + FILES_TO_ADD, timeout=120)
    if rc != 0:
        print(f"git add failed: {err}")
        # Try adding one by one
        for f in FILES_TO_ADD:
            full_path = os.path.join(REPO_DIR, f)
            if os.path.exists(full_path):
                print(f"File exists: {f}")
                rc2, out2, err2 = run_git(["add", f], timeout=60)
                if rc2 != 0:
                    print(f"  FAILED to add {f}: {err2}")
                else:
                    print(f"  Added {f}")
            else:
                print(f"File NOT FOUND: {f}")
    
    # Step 2: Commit
    print("\n=== Step 2: git commit ===")
    commit_msg = "feat: add medication reminder history check-in feature"
    rc, out, err = run_git(["commit", "-m", commit_msg], timeout=120)
    if rc != 0:
        print(f"git commit failed: {err}")
        # Check if there's nothing to commit
        if "nothing to commit" in err.lower() or "nothing to commit" in out.lower():
            print("Nothing to commit - may already be committed")
    
    # Step 3: Push
    print("\n=== Step 3: git push ===")
    for attempt in range(1, 4):
        print(f"Push attempt {attempt}/3...")
        rc, out, err = run_git(["push", "codeup", "master"], timeout=180)
        if rc == 0:
            print("Push SUCCESS!")
            break
        else:
            print(f"Push failed (attempt {attempt}): {err}")
            if attempt < 3:
                print("Retrying...")
    else:
        print("Push FAILED after 3 attempts!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
