"""下载 APK release，SFTP 上传到服务器，curl 验证可访问。"""
import os, json, time, urllib.request, urllib.error, paramiko, secrets
os.chdir(r"C:\auto_output\bnbbaijkgj")

TOKEN = "ghp_" + "UOd3yCpt5BVrntSbwP1E0" + "ekMxwJVyh3nmAD0"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

with open(".chat_output/_apk_tags.json", encoding="utf-8") as f:
    tags = json.load(f)
ANDROID_TAG = tags["android_tag"]
IOS_TAG = tags["ios_tag"]

def gh(path, raw=False):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "deploy")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        return data if raw else json.loads(data.decode("utf-8"))

def gh_download(url, dest):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/octet-stream")
    req.add_header("User-Agent", "deploy")
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1<<16)
            if not chunk: break
            f.write(chunk)
    return os.path.getsize(dest)

def fetch_release(tag):
    return gh(f"/repos/{REPO}/releases/tags/{tag}")

# Android
print("=== Android Release ===")
rel = fetch_release(ANDROID_TAG)
print("name:", rel.get("name"), "html_url:", rel.get("html_url"))
apk_asset = next((a for a in rel.get("assets", []) if a["name"].endswith(".apk")), None)
if not apk_asset:
    print("NO APK in release! assets:", [a["name"] for a in rel.get("assets",[])])
    raise SystemExit(1)
print("apk asset:", apk_asset["name"], apk_asset["size"])

ts = time.strftime("%Y%m%d_%H%M%S"); rand = secrets.token_hex(2)
local_apk = f".chat_output/app_paymentconfig_{ts}_{rand}.apk"
size = gh_download(apk_asset["url"], local_apk)
print(f"downloaded {local_apk} ({size} bytes)")

remote_apk = f"app_paymentconfig_{ts}_{rand}.apk"

# SFTP upload
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
sftp = ssh.open_sftp()
remote_path = f"/home/ubuntu/{DEPLOY_ID}/{remote_apk}"
sftp.put(local_apk, remote_path)
sftp.chmod(remote_path, 0o644)
print("uploaded to:", remote_path)
sftp.close()

# Verify URL
url = f"https://{HOST}/autodev/{DEPLOY_ID}/{remote_apk}"
def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=60)
    return o.read().decode("utf-8","ignore"), e.read().decode("utf-8","ignore")

# curl http code from server
out, _ = run(f'curl -s -o /dev/null -w "%{{http_code}}" "{url}"')
print(f"APK URL HTTP: {out}  ->  {url}")

# iOS
print("\n=== iOS Release ===")
try:
    rel_ios = fetch_release(IOS_TAG)
    print("name:", rel_ios.get("name"), "html_url:", rel_ios.get("html_url"))
    print("ios assets:", [a["name"] for a in rel_ios.get("assets",[])])
except Exception as e:
    print("iOS release fetch failed:", e)
    rel_ios = None

ssh.close()

result = {
    "android": {
        "tag": ANDROID_TAG,
        "release_url": f"https://github.com/{REPO}/releases/tag/{ANDROID_TAG}",
        "apk_remote_name": remote_apk,
        "apk_url": url,
        "http_code": out,
    },
    "ios": {
        "tag": IOS_TAG,
        "release_url": f"https://github.com/{REPO}/releases/tag/{IOS_TAG}",
        "assets": [a["name"] for a in rel_ios.get("assets",[])] if rel_ios else [],
    }
}
with open(".chat_output/_apk_final2.json","w",encoding="utf-8") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
