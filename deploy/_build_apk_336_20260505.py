# -*- coding: utf-8 -*-
"""[bugfix-336 改约按钮文案统一] 通过 GitHub Actions 远程构建 Android APK，下载并部署到服务器。

流程：
  1. 生成版本标签
  2. 触发 .github/workflows/android-build.yml
  3. 轮询构建状态（30 分钟超时）
  4. 下载 release artifact
  5. SCP 上传到服务器 /home/ubuntu/<DEPLOY_ID>/static/apk/
  6. curl 验证 HTTP 200
"""
import json
import os
import random
import ssl
import subprocess
import sys
import time
import urllib.request

import paramiko

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
APK_DIR_REMOTE = f"/home/ubuntu/{DEPLOY_ID}/static/apk"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
DL_DIR = r"C:\auto_output\bnbbaijkgj\apk_download"
STATE_FILE = r"C:\auto_output\bnbbaijkgj\deploy\.android_apk_336_state.json"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def now_tag():
    rnd = f"{random.randint(0, 0xFFFF):04x}"
    return time.strftime("android-v%Y%m%d-%H%M%S-") + rnd


def retry_cmd(cmd, max_retries=3, delays=(10, 20, 40), timeout=120):
    last_err = None
    for i in range(max_retries):
        log(f"[try {i+1}/{max_retries}] {cmd[:200]}")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)
            if r.returncode == 0:
                return r.stdout
            last_err = f"rc={r.returncode}, stderr={r.stderr[:500]}"
            log(f"  failed: {last_err}")
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout: {e}"
            log(f"  failed: {last_err}")
        if i < max_retries - 1:
            d = delays[i] if i < len(delays) else delays[-1]
            log(f"  sleep {d}s ...")
            time.sleep(d)
    raise RuntimeError(f"cmd failed after {max_retries}: {last_err}")


def load_state():
    if os.path.exists(STATE_FILE):
        return json.loads(open(STATE_FILE, "r", encoding="utf-8").read())
    return {}


def save_state(state):
    open(STATE_FILE, "w", encoding="utf-8").write(json.dumps(state, indent=2, ensure_ascii=False))


def step_trigger(state):
    tag = state.get("tag") or now_tag()
    state["tag"] = tag
    save_state(state)
    log(f"=== STEP 1: trigger workflow tag={tag} ===")
    retry_cmd(f'gh workflow run android-build.yml -R {REPO} -f version={tag}',
              max_retries=3, timeout=60)
    log("workflow dispatched, waiting 12s for run id ...")
    time.sleep(12)
    out = retry_cmd(
        f'gh run list -R {REPO} --workflow=android-build.yml --limit 5 '
        f'--json databaseId,status,conclusion,createdAt,headBranch,displayTitle',
        max_retries=3, timeout=60)
    runs = json.loads(out)
    run_id = None
    for r in runs:
        if r["status"] != "completed":
            run_id = r["databaseId"]
            break
    if run_id is None:
        run_id = runs[0]["databaseId"]
    state["run_id"] = run_id
    save_state(state)
    log(f"  run_id={run_id}")
    return state


def step_poll(state):
    tag = state["tag"]
    run_id = state["run_id"]
    log(f"=== STEP 2: poll run {run_id} (tag={tag}) ===")
    start = state.get("poll_start") or time.time()
    state["poll_start"] = start
    save_state(state)
    deadline = start + 30 * 60
    while time.time() < deadline:
        try:
            out = retry_cmd(
                f'gh run view {run_id} -R {REPO} --json status,conclusion',
                max_retries=3, timeout=60)
            info = json.loads(out)
            log(f"  [{int(time.time()-start)}s] status={info['status']} conclusion={info['conclusion']}")
            if info["status"] == "completed":
                state["conclusion"] = info["conclusion"]
                state["build_duration"] = int(time.time() - start)
                save_state(state)
                if info["conclusion"] != "success":
                    log("BUILD FAILED. Fetching log ...")
                    try:
                        r = subprocess.run(
                            f'gh run view {run_id} -R {REPO} --log-failed',
                            shell=True, capture_output=True, text=True, timeout=120)
                        print(r.stdout[-8000:])
                        print("STDERR:", r.stderr[-1000:])
                    except Exception as e:
                        log(f"log fetch error: {e}")
                    raise RuntimeError(f"build failed: conclusion={info['conclusion']}")
                return state
        except Exception as e:
            log(f"  poll error: {e}")
        time.sleep(30)
    raise RuntimeError("build timeout 30 min")


def step_download(state):
    tag = state["tag"]
    log(f"=== STEP 3: download release artifact for tag={tag} ===")
    os.makedirs(DL_DIR, exist_ok=True)
    expected = os.path.join(DL_DIR, f"bini_health_{tag}.apk")
    try:
        retry_cmd(
            f'gh release download {tag} -R {REPO} --pattern "*.apk" --dir "{DL_DIR}" --clobber',
            max_retries=3, delays=(10, 20, 40), timeout=600)
    except Exception as e:
        log(f"gh download failed: {e}; trying direct + ghproxy")
        url1 = f"https://github.com/{REPO}/releases/download/{tag}/bini_health_{tag}.apk"
        url2 = f"https://ghproxy.com/{url1}"
        ok = False
        for u in (url1, url2):
            try:
                log(f"  try direct {u}")
                urllib.request.urlretrieve(u, expected)
                ok = True
                break
            except Exception as e2:
                log(f"  fail: {e2}")
        if not ok:
            raise RuntimeError("download exhausted")

    local_apk = None
    for f in os.listdir(DL_DIR):
        if f.endswith(".apk") and tag in f:
            local_apk = os.path.join(DL_DIR, f)
            break
    if not local_apk:
        latest = None
        for f in os.listdir(DL_DIR):
            if f.endswith(".apk"):
                p = os.path.join(DL_DIR, f)
                m = os.path.getmtime(p)
                if latest is None or m > latest[1]:
                    latest = (p, m)
        if latest and latest[1] > time.time() - 1800:
            local_apk = latest[0]
    if not local_apk or not os.path.exists(local_apk):
        raise RuntimeError("no APK found locally")
    state["local_apk"] = local_apk
    state["file_size"] = os.path.getsize(local_apk)
    save_state(state)
    log(f"  local APK: {local_apk} ({state['file_size']/1024/1024:.2f} MB)")
    return state


def step_upload(state):
    tag = state["tag"]
    local_apk = state["local_apk"]
    ts = time.strftime("%Y%m%d_%H%M%S")
    rnd = f"{random.randint(0, 0xFFFF):04x}"
    remote_name = f"bini_health_android_reschedule_btn_{ts}_{rnd}.apk"
    state["remote_name"] = remote_name
    save_state(state)
    log(f"=== STEP 4: upload {os.path.basename(local_apk)} -> {remote_name} ===")

    last_err = None
    for attempt in range(3):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, username=USER, password=PWD, timeout=60)
            sftp = c.open_sftp()
            t0 = time.time()
            sftp.put(local_apk, f"/tmp/{remote_name}")
            sftp.close()
            log(f"  sftp put done in {time.time()-t0:.1f}s")

            cmd = (
                f"mkdir -p {APK_DIR_REMOTE} && "
                f"cp /tmp/{remote_name} {APK_DIR_REMOTE}/{remote_name} && "
                f"chmod 644 {APK_DIR_REMOTE}/{remote_name} && "
                f"ls -la {APK_DIR_REMOTE}/{remote_name} && "
                f"rm -f /tmp/{remote_name}"
            )
            _, o, e = c.exec_command(cmd, timeout=180)
            stdout = o.read().decode(errors="ignore")
            stderr = e.read().decode(errors="ignore")
            print(stdout)
            if stderr.strip():
                print("STDERR:", stderr)
            c.close()
            return state
        except Exception as ex:
            last_err = ex
            log(f"  upload attempt {attempt+1} failed: {ex}")
            time.sleep((10, 20, 40)[attempt])
    raise RuntimeError(f"upload failed: {last_err}")


def step_verify(state):
    remote_name = state["remote_name"]
    url = f"{BASE_URL}/apk/{remote_name}"
    state["url"] = url
    save_state(state)
    log(f"=== STEP 5: verify {url} ===")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    code = 0
    for i in range(5):
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0"})
            r = urllib.request.urlopen(req, timeout=30, context=ctx)
            code = r.status
            size = r.headers.get("Content-Length")
            ctype = r.headers.get("Content-Type")
            log(f"  HTTP {code} size={size} type={ctype}")
            state["http_code"] = code
            state["content_type"] = ctype
            state["remote_size"] = int(size) if size else None
            save_state(state)
            if code == 200:
                return state
        except Exception as ex:
            log(f"  try {i+1}: {ex}")
            time.sleep(10)
    state["http_code"] = code
    save_state(state)
    return state


def main():
    state = load_state()
    log(f"current state: {state}")

    if not state.get("run_id"):
        state = step_trigger(state)

    if state.get("conclusion") != "success":
        state = step_poll(state)

    if not state.get("local_apk") or not os.path.exists(state.get("local_apk", "")):
        state = step_download(state)

    if not state.get("remote_name"):
        state = step_upload(state)

    if state.get("http_code") != 200:
        state = step_verify(state)

    print()
    print("=== FINAL STATE ===")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    print()
    print("=== RESULT ===")
    print(f"DOWNLOAD_URL={state.get('url')}")
    print(f"HTTP_CODE={state.get('http_code')}")
    print(f"APK_FILENAME={state.get('remote_name')}")
    print(f"GITHUB_RELEASE_URL=https://github.com/{REPO}/releases/tag/{state['tag']}")
    print(f"RUN_ID={state.get('run_id')}")
    return 0 if state.get("http_code") == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
