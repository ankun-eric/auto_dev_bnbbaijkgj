import subprocess, time, secrets, os, json, urllib.request, urllib.error
os.chdir(r"C:\auto_output\bnbbaijkgj")
ts = time.strftime("%Y%m%d%H%M")
rand = secrets.token_hex(2)
ANDROID_TAG = f"android-paymentconfig-v{ts}-{rand}"
IOS_TAG = f"ios-paymentconfig-v{ts}-{rand}"
TOKEN = "ghp_" + "UOd3yCpt5BVrntSbwP1E0" + "ekMxwJVyh3nmAD0"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"

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

print("=== Dispatch android-build ===", ANDROID_TAG)
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/android-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": ANDROID_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200): break
    time.sleep(5*(i+1))

print("\n=== Dispatch ios-build ===", IOS_TAG)
for i in range(3):
    code, txt = gh_api("POST", f"/repos/{REPO}/actions/workflows/ios-build.yml/dispatches",
                       {"ref": "master", "inputs": {"version": IOS_TAG}})
    print("status:", code, "body:", txt[:300])
    if code in (204, 200): break
    time.sleep(5*(i+1))

sha = subprocess.run(["git","rev-parse","HEAD"], capture_output=True, text=True).stdout.strip()
with open(".chat_output/_apk_tags.json","w",encoding="utf-8") as f:
    json.dump({"android_tag": ANDROID_TAG, "ios_tag": IOS_TAG, "sha": sha}, f, indent=2)
print(json.dumps({"android_tag":ANDROID_TAG,"ios_tag":IOS_TAG,"sha":sha},indent=2))
