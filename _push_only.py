import subprocess, sys, time

REPO = r"C:\auto_output\bnbbaijkgj"
GIT = r"C:\Program Files\Git\cmd\git.exe"

success = False
for i in range(1, 4):
    print(f"Push attempt {i}/3...")
    p = subprocess.run([GIT, "push", "codeup", "master"], cwd=REPO, capture_output=True, text=True, timeout=180)
    print("rc:", p.returncode)
    if p.stdout:
        print(p.stdout[:500])
    if p.stderr:
        print(p.stderr[:500])
    if p.returncode == 0:
        print("PUSH SUCCESS!")
        success = True
        break
    print(f"Push failed (attempt {i}), retrying in 5s...")
    time.sleep(5)

if not success:
    print("PUSH FAILED after 3 attempts!")
    sys.exit(1)
