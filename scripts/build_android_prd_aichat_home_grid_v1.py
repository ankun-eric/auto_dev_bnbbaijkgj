#!/usr/bin/env python3
r"""[ANDROID-APK] PRD aichat-home-grid v1 - Flutter Android APK 远程构建 + 部署

流程：
1. 复用现有 .github/workflows/android-build.yml（subosito/flutter-action +
   flutter build apk --release + softprops/action-gh-release）
2. 生成唯一版本标签 android-v<YYYYMMDD-HHMMSS>-<4位hex>
3. gh workflow run android-build.yml -f version=<tag>（失败重试 3 次，间隔 10/20/40s）
4. 每 30s 轮询 gh run view，最长 30 分钟
5. gh release download <tag> --pattern "*.apk" 下载到本地（自动重试 3 次）
6. 重命名为 app_<时间戳>_<hex>.apk，SFTP 上传到部署服务器 /home/ubuntu/，
   再 docker cp 到 gateway:/data/static/apk/ —— 已有 nginx 顶层正则路由
   ^/autodev/<id>/(app_[A-Za-z0-9_\-]+\.apk)$ -> alias /data/static/apk/$1
7. curl 验证 {项目基础URL}/<文件名>.apk 返回 HTTP 200
"""
import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import paramiko


# ============ 配置 ============
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "android-build.yml"

GH_TOKEN = os.environ.get("GH_PAT_TOKEN", "")  # 通过环境变量注入，避免明文 commit

HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

GATEWAY_CONTAINER = "gateway"
GATEWAY_APK_DIR = "/data/static/apk"  # 容器内路径（只读 bind 挂载）
# 宿主机实际写入路径（gateway 的 /data/static 是只读 bind，
# 源在 /home/ubuntu/<DEPLOY_ID>/static/apk）
HOST_APK_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

POLL_INTERVAL_S = 30
MAX_WAIT_S = 30 * 60


# ============ 工具 ============
def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd, timeout=120, check=False):
    log(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["GH_TOKEN"] = GH_TOKEN
    env["GITHUB_TOKEN"] = GH_TOKEN
    cp = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=timeout, env=env,
    )
    if check and cp.returncode != 0:
        log(f"[stdout]\n{cp.stdout}")
        log(f"[stderr]\n{cp.stderr}")
        raise RuntimeError(f"Command failed (rc={cp.returncode}): {' '.join(cmd)}")
    return cp


def run_with_retry(cmd, label, attempts=3, base_sleep=10, timeout=120):
    last = None
    for i in range(1, attempts + 1):
        cp = run_cmd(cmd, timeout=timeout)
        if cp.returncode == 0:
            return cp
        last = cp
        log(f"[retry] {label} 第 {i}/{attempts} 次失败 (rc={cp.returncode})")
        if cp.stderr:
            log(f"[stderr] {cp.stderr.strip()[:400]}")
        if i < attempts:
            sleep_s = base_sleep * (2 ** (i - 1))
            log(f"[retry] sleeping {sleep_s}s ...")
            time.sleep(sleep_s)
    return last  # type: ignore[return-value]


# ============ Step: tag ============
def gen_version_tag():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    hex4 = secrets.token_hex(2)
    return f"android-v{ts}-{hex4}", ts, hex4


# ============ Step: trigger ============
def trigger_workflow(tag):
    log(f"===== 1. 触发 GH Actions workflow，version={tag} =====")
    cp = run_with_retry(
        ["gh", "workflow", "run", WORKFLOW_FILE, "-R", REPO, "-f", f"version={tag}"],
        label="gh workflow run", attempts=3, base_sleep=10, timeout=60,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"workflow run 三次仍失败:\n{cp.stderr}")
    log("[ok] workflow 已触发")
    if cp.stdout.strip():
        log(cp.stdout.strip())


# ============ Step: get run id ============
def get_latest_run_id():
    deadline = time.time() + 120
    last_err = ""
    while time.time() < deadline:
        cp = run_cmd(
            ["gh", "run", "list", "--workflow", WORKFLOW_FILE, "-R", REPO,
             "--limit", "5",
             "--json", "databaseId,status,conclusion,event,createdAt,displayTitle"],
            timeout=60,
        )
        if cp.returncode != 0:
            last_err = cp.stderr
            time.sleep(5)
            continue
        try:
            runs = json.loads(cp.stdout)
        except Exception as e:
            log(f"[warn] parse json failed: {e}, raw: {cp.stdout[:200]}")
            time.sleep(5)
            continue
        runs.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
        for r in runs:
            if r.get("event") == "workflow_dispatch":
                rid = str(r["databaseId"])
                log(f"[ok] run_id={rid} status={r.get('status')} createdAt={r.get('createdAt')}")
                return rid
        log("[wait] 暂未发现 workflow_dispatch run, 5s 后再试 ...")
        time.sleep(5)
    raise RuntimeError(f"获取 run_id 超时: {last_err}")


# ============ Step: wait ============
def wait_for_run(run_id):
    log(f"===== 2. 等待 run {run_id} 完成 (轮询 {POLL_INTERVAL_S}s，超时 {MAX_WAIT_S}s) =====")
    deadline = time.time() + MAX_WAIT_S
    last_status = ""
    while time.time() < deadline:
        cp = run_cmd(
            ["gh", "run", "view", run_id, "-R", REPO,
             "--json", "status,conclusion,name,createdAt,updatedAt"],
            timeout=60,
        )
        if cp.returncode != 0:
            log(f"[warn] gh run view 失败: {cp.stderr.strip()[:200]}")
            time.sleep(POLL_INTERVAL_S)
            continue
        try:
            data = json.loads(cp.stdout)
        except Exception:
            log(f"[warn] parse json failed: {cp.stdout[:200]}")
            time.sleep(POLL_INTERVAL_S)
            continue
        status = data.get("status", "")
        conclusion = data.get("conclusion", "")
        if status != last_status:
            log(f"[status] status={status} conclusion={conclusion}")
            last_status = status
        if status == "completed":
            log(f"[done] conclusion={conclusion}")
            return conclusion or ""
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"等待 run {run_id} 超时（>{MAX_WAIT_S}s）")


def print_failed_log(run_id):
    log("===== 失败日志 (最后 120 行) =====")
    cp = run_cmd(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"], timeout=180)
    text = (cp.stdout or "") + (cp.stderr or "")
    for line in text.splitlines()[-120:]:
        print(line)


# ============ Step: download release ============
def download_release_apk(tag, dest_dir):
    log(f"===== 3. 下载 release {tag} APK =====")
    dest_dir.mkdir(parents=True, exist_ok=True)
    cp = run_with_retry(
        ["gh", "release", "download", tag, "-R", REPO,
         "--pattern", "*.apk", "--dir", str(dest_dir), "--clobber"],
        label="gh release download", attempts=3, base_sleep=10, timeout=600,
    )
    if cp.returncode != 0:
        # fallback: 查 assets，用 curl 直链下载
        log("[fallback] gh release download 失败，尝试直接 curl ...")
        cp2 = run_cmd(["gh", "release", "view", tag, "-R", REPO,
                       "--json", "assets"], timeout=60)
        if cp2.returncode != 0:
            raise RuntimeError(f"release 未生成: {cp2.stderr}")
        assets = json.loads(cp2.stdout).get("assets", [])
        apk_asset = next((a for a in assets if a["name"].endswith(".apk")), None)
        if not apk_asset:
            raise RuntimeError(f"release {tag} 中找不到 APK asset")
        url = f"https://github.com/{REPO}/releases/download/{tag}/{apk_asset['name']}"
        local = dest_dir / apk_asset["name"]
        cp3 = run_cmd(["curl", "-L", "-fsS", "-o", str(local),
                       "-H", f"Authorization: token {GH_TOKEN}", url], timeout=600)
        if cp3.returncode != 0 or not local.exists() or local.stat().st_size < 1024:
            raise RuntimeError(f"curl 下载失败: {cp3.stderr[:200]}")
    apks = list(dest_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError(f"未找到下载的 APK in {dest_dir}")
    apk = apks[0]
    size_mb = apk.stat().st_size / 1024 / 1024
    log(f"[ok] downloaded: {apk.name} ({size_mb:.2f} MB)")
    return apk


# ============ Step: upload to gateway ============
def upload_to_gateway(local_apk, remote_filename):
    log("===== 4. 上传到部署服务器 =====")
    log(f"local : {local_apk}")
    log(f"remote: /home/ubuntu/{remote_filename}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=SSH_USER, password=SSH_PASSWORD,
                timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = ssh.open_sftp()
        remote_path = f"/home/ubuntu/{remote_filename}"
        log(f"[sftp] putting -> {remote_path}")
        sftp.put(str(local_apk), remote_path)
        st = sftp.stat(remote_path)
        log(f"[sftp] uploaded, size={st.st_size} bytes")
        sftp.close()

        def _exec(cmd, timeout=120):
            log(f"[ssh] $ {cmd}")
            _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            rc = stdout.channel.recv_exit_status()
            if out.strip():
                print(out.rstrip())
            if err.strip():
                print(f"[stderr] {err.rstrip()}")
            return rc, out, err

        # gateway 的 /data/static 是只读 bind 挂载，docker cp 会失败；
        # 直接写入宿主机源目录即可生效（同一 inode）
        sudo = f"echo {SSH_PASSWORD} | sudo -S"
        rc, _, _ = _exec(f"{sudo} mkdir -p {HOST_APK_DIR}")
        if rc != 0:
            raise RuntimeError(f"无法创建宿主机 apk 目录 {HOST_APK_DIR}")

        host_path = f"{HOST_APK_DIR}/{remote_filename}"
        rc, _, _ = _exec(f"{sudo} cp /home/ubuntu/{remote_filename} {host_path}")
        if rc != 0:
            raise RuntimeError(f"cp 到 {host_path} 失败")
        _exec(f"{sudo} chmod 644 {host_path}")

        # 通过 gateway 容器内只读视图验证文件已生效
        rc, out, _ = _exec(
            f"docker exec {GATEWAY_CONTAINER} ls -la {GATEWAY_APK_DIR}/{remote_filename}"
        )
        if rc != 0:
            raise RuntimeError(f"容器内仍看不到文件: {GATEWAY_APK_DIR}/{remote_filename}")

        size_bytes = None
        for tok in out.split():
            if tok.isdigit() and int(tok) > 1024:
                size_bytes = int(tok)
                break

        # 清理 /home/ubuntu 中转文件
        _exec(f"rm -f /home/ubuntu/{remote_filename}", timeout=30)

        return {
            "host_path": host_path,
            "gateway_path": f"{GATEWAY_APK_DIR}/{remote_filename}",
            "size_bytes": size_bytes,
        }
    finally:
        ssh.close()


# ============ Step: verify URL ============
def http_status(url, timeout=30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "deploy-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            cl = resp.headers.get("Content-Length")
            return resp.status, int(cl) if cl else -1
    except urllib.error.HTTPError as e:
        return e.code, -1
    except Exception as e:
        log(f"[http] error: {e}")
        return 0, -1


def verify_url_with_curl(url):
    cp = run_cmd(["curl", "-sk", "-o", "NUL" if os.name == "nt" else "/dev/null",
                  "-w", "%{http_code} %{size_download}", url], timeout=60)
    return cp.stdout.strip()


# ============ main ============
def main():
    overall_start = time.time()

    tag, ts, hex4 = gen_version_tag()
    log(f"[plan] version tag = {tag}")

    build_start = time.time()
    trigger_workflow(tag)
    time.sleep(5)

    run_id = get_latest_run_id()

    conclusion = wait_for_run(run_id)
    build_duration = time.time() - build_start

    if conclusion != "success":
        log(f"[fail] 构建失败 conclusion={conclusion}")
        print_failed_log(run_id)
        print()
        print("====== RESULT ======")
        print(f"VERSION_TAG : {tag}")
        print(f"RUN_ID      : {run_id}")
        print(f"CONCLUSION  : {conclusion}")
        print(f"BUILD_TIME  : {build_duration:.0f}s")
        print("====================")
        return 2

    log(f"[ok] 构建成功，用时 {build_duration:.0f}s")

    tmp_dir = Path(tempfile.mkdtemp(prefix="apk_dl_"))
    try:
        apk = download_release_apk(tag, tmp_dir)
        new_name = f"app_{ts}_{hex4}.apk"
        renamed = tmp_dir / new_name
        shutil.copy2(apk, renamed)
        size_mb = renamed.stat().st_size / 1024 / 1024
        log(f"[rename] {apk.name} -> {new_name}  ({size_mb:.2f} MB)")

        info = upload_to_gateway(renamed, new_name)

        log("===== 5. 验证 HTTPS 顶层下载链接 =====")
        download_url = f"{BASE_URL}/{new_name}"
        code, cl = 0, -1
        for attempt in range(1, 5):
            code, cl = http_status(download_url)
            log(f"[check#{attempt}] GET {download_url} -> {code} (CL={cl})")
            if code == 200:
                break
            time.sleep(5)
        curl_info = verify_url_with_curl(download_url)
        log(f"[curl] http_code size_download = {curl_info}")

        total = time.time() - overall_start
        ok = code == 200
        print()
        print("====== RESULT ======")
        print(f"APK_FILENAME : {new_name}")
        print(f"APK_URL      : {download_url}")
        print(f"FILE_SIZE_MB : {size_mb:.2f}")
        print(f"RUN_ID       : {run_id}")
        print(f"RELEASE_TAG  : {tag}")
        print(f"HTTP_STATUS  : {code}")
        print(f"BUILD_TIME   : {build_duration:.0f}s ({build_duration/60:.1f} min)")
        print(f"TOTAL_TIME   : {total:.0f}s ({total/60:.1f} min)")
        print(f"HOST_PATH    : {info.get('host_path')}")
        print(f"GATEWAY_PATH : {info.get('gateway_path')}")
        print("====================")
        return 0 if ok else 3
    finally:
        log(f"[tmp] 临时目录: {tmp_dir}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("[abort] user interrupted")
        sys.exit(130)
    except Exception as exc:
        log(f"[fatal] {exc!r}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
