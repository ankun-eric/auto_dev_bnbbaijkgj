#!/usr/bin/env python3
r"""[ANDROID-APK] 健康自查 SSE 安卓 APK GitHub Actions 远程构建 + 上传

针对本次健康自查 SSE 改造（chat_screen.dart / health_self_check_drawer.dart /
health_self_check_card.dart）通过 GitHub Actions 远程构建 Android APK，
下载到本地后重命名并 SFTP 上传到部署服务器 static/apk 目录，
最后通过 HTTPS 验证下载 URL 返回 200。

流程：
1. 生成唯一版本标签 android-v<YYYYMMDD>-<HHMMSS>-<4hex>
2. gh workflow run android-build.yml -f version=<tag> （3 次重试 10/20/40s）
3. 轮询 gh run view，每 30s 一次，最长 30 分钟
4. gh release download <tag> --pattern "*.apk" 下载 APK（自动重试）
5. 重命名为 app_<ts>_<hex>.apk，paramiko SFTP 上传到
   /home/ubuntu/<DEPLOY_ID>/static/apk/<filename>.apk
6. 验证 https://newbb.test.bangbangvip.com/autodev/<DEPLOY_ID>/apk/<filename>.apk
   返回 200 且 Content-Length > 10MB
"""
import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import paramiko


# ============ 配置 ============
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "android-build.yml"

HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
APK_DOWNLOAD_PREFIX = f"{BASE_URL}/apk"

HOST_APK_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

POLL_INTERVAL_S = 30
MAX_WAIT_S = 30 * 60
MIN_APK_BYTES = 10 * 1024 * 1024  # 10MB

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DL_DIR = PROJECT_ROOT / "_apk_dl_hsc_sse"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd, timeout=120, check=False):
    log(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
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


def gen_version_tag():
    now = datetime.now()
    date = now.strftime("%Y%m%d")
    timepart = now.strftime("%H%M%S")
    hex4 = secrets.token_hex(2)
    tag = f"android-v{date}-{timepart}-{hex4}"
    ts_combined = f"{date}-{timepart}"
    return tag, ts_combined, hex4


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
                log(f"[ok] run_id={rid} status={r.get('status')} "
                    f"createdAt={r.get('createdAt')}")
                return rid
        log("[wait] 暂未发现 workflow_dispatch run, 5s 后再试 ...")
        time.sleep(5)
    raise RuntimeError(f"获取 run_id 超时: {last_err}")


def wait_for_run(run_id):
    log(f"===== 2. 等待 run {run_id} 完成 "
        f"(轮询 {POLL_INTERVAL_S}s，超时 {MAX_WAIT_S}s) =====")
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
    log("===== 失败日志 (最后 150 行) =====")
    cp = run_cmd(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"],
                 timeout=180)
    text = (cp.stdout or "") + (cp.stderr or "")
    for line in text.splitlines()[-150:]:
        print(line)


def download_release_apk(tag, dest_dir: Path):
    log(f"===== 3. 下载 release {tag} APK =====")
    if dest_dir.exists():
        for f in dest_dir.glob("*.apk"):
            try:
                f.unlink()
            except OSError:
                pass
    dest_dir.mkdir(parents=True, exist_ok=True)

    cp = run_with_retry(
        ["gh", "release", "download", tag, "-R", REPO,
         "--pattern", "*.apk", "--dir", str(dest_dir), "--clobber"],
        label="gh release download", attempts=3, base_sleep=10, timeout=600,
    )
    if cp.returncode != 0:
        log("[fallback] gh release download 失败，尝试 curl 直链 ...")
        cp2 = run_cmd(["gh", "release", "view", tag, "-R", REPO,
                       "--json", "assets"], timeout=60)
        if cp2.returncode != 0:
            raise RuntimeError(f"release 未生成: {cp2.stderr}")
        assets = json.loads(cp2.stdout).get("assets", [])
        apk_asset = next((a for a in assets if a["name"].endswith(".apk")), None)
        if not apk_asset:
            raise RuntimeError(f"release {tag} 中找不到 APK asset")
        gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        urls = [
            f"https://github.com/{REPO}/releases/download/{tag}/{apk_asset['name']}",
            f"https://ghproxy.com/https://github.com/{REPO}/releases/download/{tag}/{apk_asset['name']}",
        ]
        local = dest_dir / apk_asset["name"]
        ok = False
        for url in urls:
            log(f"[curl] try {url}")
            hdrs = []
            if gh_token and "ghproxy.com" not in url:
                hdrs = ["-H", f"Authorization: token {gh_token}"]
            cp3 = run_cmd(
                ["curl", "-L", "-fsS", "-o", str(local), *hdrs, url],
                timeout=600,
            )
            if cp3.returncode == 0 and local.exists() and local.stat().st_size > 1024:
                ok = True
                break
        if not ok:
            raise RuntimeError("curl 下载失败")

    apks = list(dest_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError(f"未找到下载的 APK in {dest_dir}")
    apk = apks[0]
    size_mb = apk.stat().st_size / 1024 / 1024
    log(f"[ok] downloaded: {apk.name} ({size_mb:.2f} MB)")
    return apk


def upload_to_server(local_apk: Path, remote_filename: str):
    log("===== 4. SFTP 上传到部署服务器 =====")
    remote_path = f"{HOST_APK_DIR}/{remote_filename}"
    log(f"local : {local_apk}")
    log(f"remote: {remote_path}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=SSH_USER, password=SSH_PASSWORD,
                timeout=30, allow_agent=False, look_for_keys=False)
    try:
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

        _exec(f"mkdir -p {HOST_APK_DIR}")

        sftp = ssh.open_sftp()
        try:
            log(f"[sftp] putting -> {remote_path}")
            sftp.put(str(local_apk), remote_path)
            st = sftp.stat(remote_path)
            log(f"[sftp] uploaded, size={st.st_size} bytes "
                f"({st.st_size/1024/1024:.2f} MB)")
        finally:
            sftp.close()

        _exec(f"chmod 644 {remote_path}")
        rc, out, _ = _exec(f"ls -la {remote_path}")
        if rc != 0:
            raise RuntimeError(f"上传后 ls 失败: {remote_path}")

        return {
            "remote_path": remote_path,
            "size_bytes": st.st_size,
        }
    finally:
        ssh.close()


def http_get_head(url, timeout=60):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "deploy-check/1.0",
                                              "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            cl = resp.headers.get("Content-Range") or resp.headers.get("Content-Length")
            total = -1
            if cl and "/" in cl:
                try:
                    total = int(cl.split("/")[-1])
                except Exception:
                    total = -1
            elif cl:
                try:
                    total = int(cl)
                except Exception:
                    total = -1
            return resp.status, total
    except urllib.error.HTTPError as e:
        return e.code, -1
    except Exception as e:
        log(f"[http] error: {e}")
        return 0, -1


def main():
    overall_start = time.time()

    tag, ts_combined, hex4 = gen_version_tag()
    log(f"[plan] version tag = {tag}")

    build_start = time.time()
    trigger_workflow(tag)
    time.sleep(5)

    run_id = get_latest_run_id()
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"[info] run_url = {run_url}")

    conclusion = wait_for_run(run_id)
    build_duration = time.time() - build_start

    if conclusion != "success":
        log(f"[fail] 构建失败 conclusion={conclusion}")
        print_failed_log(run_id)
        print()
        print("====== RESULT ======")
        print(f"VERSION_TAG : {tag}")
        print(f"RUN_ID      : {run_id}")
        print(f"RUN_URL     : {run_url}")
        print(f"CONCLUSION  : {conclusion}")
        print(f"BUILD_TIME  : {build_duration:.0f}s")
        print("====================")
        return 2

    log(f"[ok] 构建成功，用时 {build_duration:.0f}s")

    apk = download_release_apk(tag, DL_DIR)
    new_name = f"app_{ts_combined}_{hex4}.apk"
    renamed = DL_DIR / new_name
    shutil.copy2(apk, renamed)
    size_bytes = renamed.stat().st_size
    size_mb = size_bytes / 1024 / 1024
    log(f"[rename] {apk.name} -> {new_name}  ({size_mb:.2f} MB)")

    info = upload_to_server(renamed, new_name)

    log("===== 5. 验证 HTTPS 下载链接 =====")
    download_url = f"{APK_DOWNLOAD_PREFIX}/{new_name}"
    code, cl = 0, -1
    for attempt in range(1, 6):
        code, cl = http_get_head(download_url)
        log(f"[check#{attempt}] GET {download_url} -> {code} (total_size={cl})")
        if code in (200, 206) and cl >= MIN_APK_BYTES:
            break
        time.sleep(5)

    total = time.time() - overall_start
    ok = code in (200, 206) and cl >= MIN_APK_BYTES

    print()
    print("====== RESULT ======")
    print(f"APK_FILENAME : {new_name}")
    print(f"APK_URL      : {download_url}")
    print(f"FILE_SIZE_MB : {size_mb:.2f}")
    print(f"FILE_SIZE_BYTES : {size_bytes}")
    print(f"RUN_ID       : {run_id}")
    print(f"RUN_URL      : {run_url}")
    print(f"RELEASE_TAG  : {tag}")
    print(f"HTTP_STATUS  : {code}")
    print(f"HTTP_TOTAL_SIZE : {cl}")
    print(f"BUILD_TIME   : {build_duration:.0f}s ({build_duration/60:.1f} min)")
    print(f"TOTAL_TIME   : {total:.0f}s ({total/60:.1f} min)")
    print(f"REMOTE_PATH  : {info.get('remote_path')}")
    print("====================")
    return 0 if ok else 3


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
