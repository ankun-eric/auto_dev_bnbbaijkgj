import subprocess
cwd = r"C:\auto_output\bnbbaijkgj"
# 起始 commit -> 工作区（含 staged/unstaged/untracked）
r1 = subprocess.run(["git", "diff", "--name-only", "4d5cf0f129fb85d98628cf472ec911f72c0ea012"],
                    capture_output=True, text=True, cwd=cwd)
r2 = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                    capture_output=True, text=True, cwd=cwd)
files = sorted(set(
    [l for l in (r1.stdout + r2.stdout).splitlines() if l.strip()]
))
with open(r"C:\auto_output\bnbbaijkgj\.chat_output\_changed_files.txt", "w", encoding="utf-8") as f:
    for fl in files:
        f.write(fl + "\n")
print(f"total changed: {len(files)}")
groups = {"backend": 0, "admin-web": 0, "h5-web": 0, "miniprogram": 0, "flutter_app": 0, "other": 0}
for fl in files:
    matched = False
    for k in groups:
        if fl.startswith(k + "/"):
            groups[k] += 1
            matched = True
            break
    if not matched:
        groups["other"] += 1
print(groups)
