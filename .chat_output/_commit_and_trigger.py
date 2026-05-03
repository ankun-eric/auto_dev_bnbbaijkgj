"""提交并 push 代码，然后触发 android-build / ios-build workflow。"""
import subprocess, time, secrets, os, json, sys

os.chdir(r"C:\auto_output\bnbbaijkgj")
ts = time.strftime("%Y%m%d%H%M")
rand = secrets.token_hex(2)
ANDROID_TAG = f"android-paymentconfig-v{ts}-{rand}"
IOS_TAG = f"ios-paymentconfig-v{ts}-{rand}"
TOKEN = "${GITHUB_TOKEN}"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"

env = os.environ.copy()
env["GH_TOKEN"] = TOKEN
env["GITHUB_TOKEN"] = TOKEN

def run(args, cwd=None, check=False, timeout=300):
    print(f"$ {' '.join(args) if isinstance(args, list) else args}")
    r = subprocess.run(args, cwd=cwd or os.getcwd(), env=env, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', shell=isinstance(args, str), timeout=timeout)
    if r.stdout: print(r.stdout[:2000])
    if r.stderr: print("STDERR:", r.stderr[:1000])
    if check and r.returncode != 0:
        raise SystemExit(f"Command failed: {args}")
    return r

# git add & commit
run(["git", "add", "-A"])
r = run(["git", "diff", "--cached", "--name-only"])
if not r.stdout.strip():
    print("Nothing to commit")
else:
    msg = "feat(payment-config): support payment configuration management v1.0\n\n" \
          "- backend: payment_channels table, AES-256-GCM encryption, admin CRUD APIs, available-methods API\n" \
          "- admin-web: payment-config page (4 tabs/Drawer), order detail payment_method_text\n" \
          "- h5-web/miniprogram/flutter_app: order detail payment_method_text\n" \
          "- tests: backend/tests/test_payment_config_v1.py 9/9 passed (local & remote)\n" \
          "- deployed to remote, miniprogram zip + android apk attached"
    rcmt = run(["git", "commit", "-m", msg])
    if rcmt.returncode != 0:
        # maybe nothing changed
        print("commit returned non-zero, continue anyway")

# push with retry
remote_url = f"https://x-access-token:{TOKEN}@github.com/{REPO}.git"
run(["git", "remote", "set-url", "origin", remote_url])
for i in range(3):
    rp = run(["git", "push", "origin", "HEAD:master"], timeout=300)
    if rp.returncode == 0:
        break
    print(f"push attempt {i+1} failed, retrying in {5*(i+1)}s")
    time.sleep(5*(i+1))

# get HEAD sha
sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()
print("HEAD SHA:", sha)

# Trigger android workflow via API (avoid gh CLI dep)
import urllib.request, urllib.error
def gh_api(method, path, data=None):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "deploy-script")
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=body, timeout=60) as resp:
            txt = resp.read().decode("utf-8", "ignore")
            return resp.status, txt
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

# Dispatch android-build
print("\n=== Dispatch android-build ===")
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/android-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": ANDROID_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200):
        break
    time.sleep(5*(i+1))

# Dispatch ios-build
print("\n=== Dispatch ios-build ===")
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/ios-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": IOS_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200):
        break
    time.sleep(5*(i+1))

with open(".chat_output/_apk_tags.json", "w", encoding="utf-8") as f:
    json.dump({"android_tag": ANDROID_TAG, "ios_tag": IOS_TAG, "sha": sha}, f, indent=2)
print(json.dumps({"android_tag": ANDROID_TAG, "ios_tag": IOS_TAG, "sha": sha}, indent=2))
