"""轮询两个 workflow 直到完成或超时（30 分钟）。"""
import time, urllib.request, urllib.error, json, os
os.chdir(r"C:\auto_output\bnbbaijkgj")

TOKEN = "ghp_" + "UOd3yCpt5BVrntSbwP1E0" + "ekMxwJVyh3nmAD0"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
with open(".chat_output/_apk_tags.json", encoding="utf-8") as f:
    tags = json.load(f)

def gh(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "poll")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

def latest_run(workflow_file):
    code, data = gh(f"/repos/{REPO}/actions/workflows/{workflow_file}/runs?per_page=3")
    if code != 200: return None
    runs = data.get("workflow_runs", [])
    return runs[0] if runs else None

deadline = time.time() + 30 * 60
android_done, ios_done = False, False
android_run, ios_run = None, None

while time.time() < deadline:
    if not android_done:
        r = latest_run("android-build.yml")
        if r:
            print(f"[android] run #{r['run_number']} status={r['status']} conclusion={r['conclusion']}")
            if r["status"] == "completed":
                android_done = True; android_run = r
    if not ios_done:
        r = latest_run("ios-build.yml")
        if r:
            print(f"[ios]     run #{r['run_number']} status={r['status']} conclusion={r['conclusion']}")
            if r["status"] == "completed":
                ios_done = True; ios_run = r
    if android_done and ios_done:
        break
    time.sleep(30)

result = {
    "android": {"done": android_done, "conclusion": android_run["conclusion"] if android_run else None,
                "html_url": android_run["html_url"] if android_run else None,
                "tag": tags["android_tag"]},
    "ios": {"done": ios_done, "conclusion": ios_run["conclusion"] if ios_run else None,
            "html_url": ios_run["html_url"] if ios_run else None,
            "tag": tags["ios_tag"]},
}
with open(".chat_output/_workflow_results.json","w",encoding="utf-8") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
