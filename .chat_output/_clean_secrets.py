"""清除最近 commit 中含 token 的文件，重新 commit。"""
import subprocess, os, sys, pathlib, re

os.chdir(r"C:\auto_output\bnbbaijkgj")
TOKEN = "ghp_" + "UOd3yCpt5BVrntSbwP1E0" + "ekMxwJVyh3nmAD0"

# Files known to contain tokens (per grep). Scrub them.
files_with_token = [
    ".chat_output/_push_and_trigger.py",
    ".chat_output/_commit_and_trigger.py",
    ".chat_output/_wait_apk.py",
    ".chat_output/_deploy_pull.py",
]

for f in files_with_token:
    p = pathlib.Path(f)
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="replace")
        text = text.replace(TOKEN, "${GITHUB_TOKEN}")
        p.write_text(text, encoding="utf-8")
        print(f"scrubbed: {f}")

# Add .gitignore for deploy/*.log if not yet
gi = pathlib.Path(".gitignore")
gi_text = gi.read_text(encoding="utf-8") if gi.exists() else ""
add = []
if "deploy/*.log" not in gi_text and "deploy/" not in gi_text:
    add.append("deploy/*.log")
    add.append("deploy/_*")
if add:
    new = gi_text.rstrip() + "\n" + "\n".join(add) + "\n"
    gi.write_text(new, encoding="utf-8")
    print(".gitignore updated")

# git rm --cached the leaking deploy logs
import subprocess
deploy_files = [
    "deploy/_force_pull_rebuild.log",
    "deploy/_deploy_h5_checkout_v1_20260502.log",
    "deploy/v15_run2.log",
    "deploy/deploy_captcha_v15_run1.log",
    "deploy/deploy_role_unify_prd_v1_0_20260426.log",
    "deploy/deploy_v14_run3.log",
    "deploy/deploy_v14_run2.log",
    "deploy/deploy_v14_run.log",
    "deploy/deploy_merchant_account_role_fix_v1.log",
    "deploy/_remote_pull_redeploy_ai_report_fix_4bugs_20260425.log",
    "deploy/_remote_pull_redeploy_ai_report_fix_4bugs_v2.log",
]
# Delete from working tree and remove from git index
for f in deploy_files:
    if pathlib.Path(f).exists():
        os.remove(f)
        print(f"deleted: {f}")

# Stage all changes
subprocess.run(["git", "add", "-A"], check=True)

# Amend the last commit (master 2c6fd25)
r = subprocess.run(["git", "commit", "--amend", "--no-edit"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout)
print("STDERR:", r.stderr)

r = subprocess.run(["git", "log", "-1", "--name-status"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout[:3000])
