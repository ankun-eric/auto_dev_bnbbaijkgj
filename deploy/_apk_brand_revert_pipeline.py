"""Trigger GitHub Actions android-build.yml, poll, download APK, upload to /downloads/, verify URL."""
import subprocess, time, os, sys, json, random, urllib.request, ssl
import paramiko

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_DL_DIR = f"/home/ubuntu/{DEPLOY_ID}/h5-web/public/downloads"
URL_PREFIX = f"https://{HOST}/autodev/{DEPLOY_ID}/downloads"

ENV = os.environ.copy()
ENV["GH_TOKEN"] = os.environ.get("GH_TOKEN") or ""  # 必须由调用方在环境变量中设置 GH_TOKEN

def now_ts_rnd():
    ts = time.strftime("%Y%m%d-%H%M%S")
    rnd = f"{random.randint(0, 0xFFFF):04x}"
    return ts, rnd

def retry(cmd, max_retries=3, delay=10, timeout=120):
    last = None
    d = delay
    for i in range(max_retries):
        print(f"[retry {i+1}/{max_retries}] {cmd[:200]}")
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout, env=ENV)
        if r.returncode == 0:
            return r.stdout
        last = r
        print(f"  -> failed rc={r.returncode}, stderr={r.stderr[:400]}")
        time.sleep(d); d *= 2
    raise RuntimeError(f"cmd failed after {max_retries}: {last.stderr if last else 'unknown'}")

def main():
    state_file = r"C:\auto_output\bnbbaijkgj\deploy\.android_apk_brand_revert_state.json"
    state = {}
    if os.path.exists(state_file):
        state = json.loads(open(state_file).read())

    # STEP 1: trigger
    if "tag" not in state:
        ts, rnd = now_ts_rnd()
        tag = f"android-v{ts}-{rnd}"
        state["tag"] = tag
        state["ts"] = ts
        state["rnd"] = rnd
    tag = state["tag"]

    if "run_id" not in state:
        print(f"=== STEP 1: trigger workflow tag={tag} ===")
        retry(f'gh workflow run android-build.yml -R {REPO} -f version={tag}', max_retries=3, delay=10, timeout=60)
        time.sleep(10)
        out = retry(f'gh run list -R {REPO} --workflow=android-build.yml --limit 1 --json databaseId,status,conclusion,createdAt', max_retries=3, delay=5, timeout=60)
        runs = json.loads(out)
        state["run_id"] = runs[0]["databaseId"]
        open(state_file, "w").write(json.dumps(state, indent=2))
        print(f"   run_id={state['run_id']}")

    run_id = state["run_id"]

    # STEP 2: poll
    if state.get("conclusion") != "success":
        start = state.get("poll_start") or time.time()
        state["poll_start"] = start
        print(f"=== STEP 2: poll run {run_id} (tag={tag}) ===")
        deadline = start + 30 * 60
        last_status = None
        while time.time() < deadline:
            try:
                out = retry(f'gh run view {run_id} -R {REPO} --json status,conclusion', max_retries=3, delay=5, timeout=60)
                info = json.loads(out)
                if info["status"] != last_status:
                    print(f"   [{int(time.time()-start)}s] status={info['status']} conclusion={info['conclusion']}")
                    last_status = info["status"]
                if info["status"] == "completed":
                    state["conclusion"] = info["conclusion"]
                    state["build_duration"] = int(time.time() - start)
                    open(state_file, "w").write(json.dumps(state, indent=2))
                    if info["conclusion"] != "success":
                        print("FAILED. Fetching log:")
                        try:
                            log = subprocess.run(f'gh run view {run_id} -R {REPO} --log-failed', shell=True, capture_output=True, text=True, timeout=120, env=ENV)
                            print(log.stdout[-6000:])
                        except Exception as e:
                            print(f"log fetch err: {e}")
                        sys.exit(2)
                    break
            except Exception as e:
                print(f"   poll error: {e}")
            time.sleep(30)
        else:
            print("TIMEOUT 30 min")
            sys.exit(3)
        open(state_file, "w").write(json.dumps(state, indent=2))

    # STEP 3: download
    if "local_apk" not in state or not os.path.exists(state.get("local_apk", "")):
        print(f"=== STEP 3: download release artifact tag={tag} ===")
        dl_dir = r"C:\auto_output\bnbbaijkgj\apk_brand_revert_dl"
        os.makedirs(dl_dir, exist_ok=True)
        for f in os.listdir(dl_dir):
            if f.endswith(".apk"):
                try: os.remove(os.path.join(dl_dir, f))
                except: pass
        retry(f'gh release download {tag} -R {REPO} --pattern "*.apk" --dir "{dl_dir}" --clobber', max_retries=3, delay=15, timeout=600)
        local_apk = None
        for f in os.listdir(dl_dir):
            if f.endswith(".apk"):
                local_apk = os.path.join(dl_dir, f); break
        if not local_apk:
            raise RuntimeError("no APK found locally")
        state["local_apk"] = local_apk
        state["file_size"] = os.path.getsize(local_apk)
        open(state_file, "w").write(json.dumps(state, indent=2))
        print(f"   local APK: {local_apk} ({state['file_size']/1024/1024:.2f} MB)")

    # STEP 4: upload
    if "verified_http_status" not in state or state.get("verified_http_status") != 200:
        local_apk = state["local_apk"]
        ts = state["ts"].replace("-", "_")
        rnd = state["rnd"]
        remote_name = f"app_{ts}_{rnd}.apk"
        state["remote_name"] = remote_name
        url = f"{URL_PREFIX}/{remote_name}"
        state["url"] = url
        print(f"=== STEP 4: upload to {REMOTE_DL_DIR}/{remote_name} ===")
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, username=USER, password=PWD, timeout=60)
        sftp = c.open_sftp()
        t0 = time.time()
        sftp.put(local_apk, f"/tmp/{remote_name}")
        sftp.close()
        print(f"   sftp put done in {time.time()-t0:.1f}s")
        cmd = (
            f"echo {PWD} | sudo -S mkdir -p {REMOTE_DL_DIR} && "
            f"echo {PWD} | sudo -S cp /tmp/{remote_name} {REMOTE_DL_DIR}/{remote_name} && "
            f"echo {PWD} | sudo -S chmod 644 {REMOTE_DL_DIR}/{remote_name} && "
            f"echo {PWD} | sudo -S chown ubuntu:ubuntu {REMOTE_DL_DIR}/{remote_name} && "
            f"ls -la {REMOTE_DL_DIR}/{remote_name} && "
            f"rm -f /tmp/{remote_name}"
        )
        _, o, e = c.exec_command(cmd, timeout=180)
        out = o.read().decode(errors="ignore"); err = e.read().decode(errors="ignore")
        print(out)
        if err.strip(): print("STDERR:", err)
        c.close()
        open(state_file, "w").write(json.dumps(state, indent=2))

        # STEP 5: verify
        print(f"=== STEP 5: verify {url} ===")
        ctx = ssl.create_default_context()
        for i in range(6):
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
                r = urllib.request.urlopen(req, timeout=30, context=ctx)
                code = r.status
                size = r.headers.get("Content-Length")
                ctype = r.headers.get("Content-Type")
                print(f"   HTTP {code} size={size} type={ctype}")
                state["verified_http_status"] = code
                state["content_type"] = ctype
                state["remote_size"] = int(size) if size else None
                if code == 200:
                    break
            except Exception as ex:
                print(f"   try {i+1}: {ex}")
                time.sleep(10)
        open(state_file, "w").write(json.dumps(state, indent=2))

    print("\n=== FINAL STATE ===")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    print("\n=== RESULT ===")
    print(f"URL:           {state.get('url')}")
    print(f"Filename:      {state.get('remote_name')}")
    sz = state.get("remote_size") or state.get("file_size") or 0
    print(f"Size:          {sz/1024/1024:.2f} MB")
    print(f"Tag:           {state.get('tag')}")
    print(f"Release page:  https://github.com/{REPO}/releases/tag/{state.get('tag')}")
    print(f"HTTP verified: {state.get('verified_http_status')}")

if __name__ == "__main__":
    main()
