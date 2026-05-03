"""push + dispatch workflows"""
import subprocess, time, secrets, os, json, urllib.request, urllib.error

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

def run(args, timeout=180):
    print(f"$ {' '.join(args)}")
    r = subprocess.run(args, env=env, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=timeout)
    if r.stdout: print(r.stdout[:1500])
    if r.stderr: print("STDERR:", r.stderr[:1000])
    return r

# set remote
remote_url = f"https://x-access-token:{TOKEN}@github.com/{REPO}.git"
run(["git", "remote", "set-url", "origin", remote_url])

# check status
r = run(["git", "status", "-sb"])

# push with retry
push_ok = False
for i in range(5):
    rp = run(["git", "push", "origin", "HEAD:master"], timeout=120)
    if rp.returncode == 0:
        push_ok = True
        break
    print(f"push attempt {i+1} failed, retry in {5*(i+1)}s...")
    time.sleep(5*(i+1))
print("push_ok:", push_ok)

sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()
print("HEAD SHA:", sha)

def gh_api(method, path, data=None):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "deploy-script")
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=body, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

print("\n=== Dispatch android-build ===")
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/android-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": ANDROID_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200): break
    time.sleep(5*(i+1))

print("\n=== Dispatch ios-build ===")
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/ios-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": IOS_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200): break
    time.sleep(5*(i+1))

with open(".chat_output/_apk_tags.json", "w", encoding="utf-8") as f:
    json.dump({"android_tag": ANDROID_TAG, "ios_tag": IOS_TAG, "sha": sha, "push_ok": push_ok}, f, indent=2)
print("WROTE", ANDROID_TAG, IOS_TAG)
