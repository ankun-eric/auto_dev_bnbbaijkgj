"""PRD-452 品牌化改造（包名收口为 com.benekang.app）APK 内测包构建 + 上传 + 验证 流水线
- 触发 GitHub Actions android-build.yml 进行构建
- 轮询直到完成
- 下载 release APK
- 上传到部署服务器
- 验证 URL 可达
"""
import subprocess
import time
import os
import sys
import json
import random
import urllib.request
import ssl
import hashlib
import paramiko

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"

STATE_FILE = r"C:\auto_output\bnbbaijkgj\deploy\.prd452_brand_apk_state.json"


def now_tag():
    return time.strftime("prd452-brand-v%Y%m%d-%H%M%S-") + f"{random.randint(0, 0xFFFF):04x}"


def retry(cmd, max_retries=3, delay=10, timeout=120):
    last = None
    d = delay
    for i in range(max_retries):
        print(f"[retry {i+1}/{max_retries}] {cmd[:200]}")
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)
        if r.returncode == 0:
            return r.stdout
        last = r
        print(f"  -> failed rc={r.returncode}, stderr={r.stderr[:300]}")
        time.sleep(d)
        d *= 2
    raise RuntimeError(f"cmd failed after {max_retries}: {last.stderr if last else 'unknown'}")


def main():
    state = {}
    if os.path.exists(STATE_FILE):
        state = json.loads(open(STATE_FILE).read())

    if "tag" not in state:
        state["tag"] = now_tag()
    tag = state["tag"]
    print(f"=== Tag: {tag} ===")

    if "run_id" not in state:
        print(f"=== STEP 1: trigger workflow with tag={tag} ===")
        retry(f'gh workflow run android-build.yml -R {REPO} -f version={tag}', max_retries=3, delay=10, timeout=60)
        time.sleep(8)
        out = retry(
            f'gh run list -R {REPO} --workflow=android-build.yml --limit 1 --json databaseId,status,conclusion,createdAt,headBranch',
            max_retries=3, delay=5, timeout=60,
        )
        runs = json.loads(out)
        run_id = runs[0]["databaseId"]
        state["run_id"] = run_id
        open(STATE_FILE, "w").write(json.dumps(state, indent=2))
        print(f"   run_id={run_id}")

    run_id = state["run_id"]

    if state.get("conclusion") != "success":
        start = state.get("poll_start") or time.time()
        state["poll_start"] = start
        open(STATE_FILE, "w").write(json.dumps(state, indent=2))
        print(f"=== STEP 2: poll run {run_id} (tag={tag}) ===")
        deadline = start + 30 * 60
        while time.time() < deadline:
            try:
                out = retry(f'gh run view {run_id} -R {REPO} --json status,conclusion', max_retries=3, delay=5, timeout=60)
                info = json.loads(out)
                print(f"   [{int(time.time()-start)}s] status={info['status']} conclusion={info['conclusion']}")
                if info["status"] == "completed":
                    state["conclusion"] = info["conclusion"]
                    state["build_duration"] = int(time.time() - start)
                    open(STATE_FILE, "w").write(json.dumps(state, indent=2))
                    if info["conclusion"] != "success":
                        print("FAILED. Fetching log:")
                        try:
                            log = subprocess.run(
                                f'gh run view {run_id} -R {REPO} --log-failed',
                                shell=True, capture_output=True, text=True, timeout=120,
                            )
                            print(log.stdout[-5000:])
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
        open(STATE_FILE, "w").write(json.dumps(state, indent=2))

    if not state.get("local_apk") or not os.path.exists(state.get("local_apk", "")):
        print(f"=== STEP 3: download release artifact for tag={tag} ===")
        dl_dir = r"C:\auto_output\bnbbaijkgj\apk_download"
        os.makedirs(dl_dir, exist_ok=True)
        local_apk = None
        try:
            retry(
                f'gh release download {tag} -R {REPO} --pattern "*.apk" --dir "{dl_dir}" --clobber',
                max_retries=3, delay=15, timeout=600,
            )
        except Exception as e:
            print(f"gh download failed: {e}; trying direct + ghproxy")
            url1 = f"https://github.com/{REPO}/releases/download/{tag}/bini_health_{tag}.apk"
            url2 = f"https://ghproxy.com/{url1}"
            local_apk = os.path.join(dl_dir, f"bini_health_{tag}.apk")
            ok = False
            for u in (url1, url2):
                try:
                    print(f"   try direct {u}")
                    urllib.request.urlretrieve(u, local_apk)
                    ok = True
                    break
                except Exception as e2:
                    print(f"   fail: {e2}")
            if not ok:
                raise RuntimeError("download exhausted")
        for f in os.listdir(dl_dir):
            if f.endswith(".apk") and tag in f:
                local_apk = os.path.join(dl_dir, f)
                break
        if not local_apk or not os.path.exists(local_apk):
            for f in os.listdir(dl_dir):
                if f.endswith(".apk"):
                    p = os.path.join(dl_dir, f)
                    if os.path.getmtime(p) > time.time() - 1800:
                        local_apk = p
                        break
        if not local_apk or not os.path.exists(local_apk):
            raise RuntimeError("no APK found locally")
        state["local_apk"] = local_apk
        state["file_size"] = os.path.getsize(local_apk)
        h = hashlib.sha256()
        with open(local_apk, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        state["sha256"] = h.hexdigest()
        open(STATE_FILE, "w").write(json.dumps(state, indent=2))
        print(f"   local APK: {local_apk} ({state['file_size']/1024/1024:.2f} MB)")
        print(f"   sha256: {state['sha256']}")

    local_apk = state["local_apk"]
    if not state.get("remote_name"):
        ts = time.strftime("%Y%m%d_%H%M%S")
        rnd = f"{random.randint(0, 0xFFFF):04x}"
        remote_name = f"benekang_v1.0.0_inner_{ts}_{rnd}.apk"
        state["remote_name"] = remote_name
        print(f"=== STEP 4: upload to server as {remote_name} ===")
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, username=USER, password=PWD, timeout=60)
        sftp = c.open_sftp()
        t0 = time.time()
        sftp.put(local_apk, f"/tmp/{remote_name}")
        sftp.close()
        print(f"   sftp put done in {time.time()-t0:.1f}s")
        apk_dir = f"/home/ubuntu/{DEPLOY_ID}/static/apk"
        cmd = (
            f"echo {PWD} | sudo -S mkdir -p {apk_dir} && "
            f"echo {PWD} | sudo -S cp /tmp/{remote_name} {apk_dir}/{remote_name} && "
            f"echo {PWD} | sudo -S chmod 644 {apk_dir}/{remote_name} && "
            f"echo {PWD} | sudo -S chown ubuntu:ubuntu {apk_dir}/{remote_name} && "
            f"ls -la {apk_dir}/{remote_name}"
        )
        _, o, e = c.exec_command(cmd, timeout=180)
        print(o.read().decode(errors="ignore"))
        err = e.read().decode(errors="ignore")
        if err.strip():
            print("STDERR:", err)
        c.close()
        open(STATE_FILE, "w").write(json.dumps(state, indent=2))

    remote_name = state["remote_name"]
    url = f"https://{HOST}/autodev/{DEPLOY_ID}/apk/{remote_name}"
    print(f"=== STEP 5: verify {url} ===")
    ctx = ssl.create_default_context()
    for i in range(5):
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            r = urllib.request.urlopen(req, timeout=30, context=ctx)
            code = r.status
            size = r.headers.get("Content-Length")
            ctype = r.headers.get("Content-Type")
            print(f"   HTTP {code} size={size} type={ctype}")
            state["verified_http_status"] = code
            state["url"] = url
            state["content_type"] = ctype
            state["remote_size"] = int(size) if size else None
            if code == 200:
                break
        except Exception as ex:
            print(f"   try {i+1}: {ex}")
            time.sleep(10)
    open(STATE_FILE, "w").write(json.dumps(state, indent=2))

    print("\n=== FINAL STATE ===")
    print(json.dumps(state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
