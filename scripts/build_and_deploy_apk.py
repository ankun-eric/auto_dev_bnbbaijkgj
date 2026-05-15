#!/usr/bin/env python3
"""[ANDROID-APK] GitHub Actions 远程构建 Flutter APK -> 下载 -> 上传 gateway -> 验证下载链接

流程：
1. 生成唯一版本标签：android-v<YYYYMMDD-HHMMSS>-<4位十六进制>
2. gh workflow run android-build.yml -f version=<tag>  （失败重试 3 次）
3. 轮询 gh run view 等待完成，最长 30 分钟
4. gh release download <tag>  下载 APK
5. 重命名为 app_<timestamp>_<hex>.apk
6. SFTP 到服务器 /home/ubuntu/，docker cp 到 gateway:/data/static/apk/
7. HTTP GET https://newbb.test.bangbangvip.com/autodev/<deploy_id>/apk/<filename>.apk 期望 200
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
import urllib.request
from datetime import datetime
from pathlib import Path

import paramiko


# ===== 配置 =====
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW_FILE = "android-build.yml"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
GATEWAY_CONTAINER = "gateway"
GATEWAY_APK_DIR = "/data/static/apk"

POLL_INTERVAL_S = 30
MAX_WAIT_S = 30 * 60  # 30 分钟


# ===== 工具 =====
def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd: list, timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess:
    """运行命令，返回 CompletedProcess。强制 UTF-8 编码。"""
    log(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cp = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    if check and cp.returncode != 0:
        log(f"[stdout]\n{cp.stdout}")
        log(f"[stderr]\n{cp.stderr}")
        raise RuntimeError(f"Command failed (rc={cp.returncode}): {' '.join(cmd)}")
    return cp


def run_with_retry(cmd: list, label: str, attempts: int = 3, base_sleep: int = 10,
                   timeout: int = 120) -> subprocess.CompletedProcess:
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


# ===== 主流程 =====
def gen_version_tag() -> tuple[str, str, str]:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    hexsuf = secrets.token_hex(2)
    tag = f"android-v{ts}-{hexsuf}"
    return tag, ts, hexsuf


def trigger_workflow(tag: str) -> None:
    log(f"===== 1. 触发 GH Actions workflow，version={tag} =====")
    cp = run_with_retry(
        ["gh", "workflow", "run", WORKFLOW_FILE, "-R", REPO, "-f", f"version={tag}"],
        label="gh workflow run", attempts=3, base_sleep=10, timeout=60,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"workflow run 三次仍失败:\n{cp.stderr}")
    log(f"[ok] workflow 已触发")
    if cp.stdout.strip():
        log(cp.stdout.strip())


def get_latest_run_id(tag: str) -> str:
    """获取我们刚触发的 run ID。
    通过 displayTitle/headBranch 不可靠，这里直接取最新的 workflow_dispatch run。
    """
    deadline = time.time() + 90
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
        # 优先选 event=workflow_dispatch 的最新一条
        runs.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
        for r in runs:
            if r.get("event") == "workflow_dispatch":
                rid = str(r["databaseId"])
                log(f"[ok] 找到 run_id={rid} status={r.get('status')} createdAt={r.get('createdAt')}")
                return rid
        log(f"[wait] 暂未发现 workflow_dispatch run, 5s 后再试 ...")
        time.sleep(5)
    raise RuntimeError(f"获取 run_id 超时: {last_err}")


def wait_for_run(run_id: str) -> str:
    log(f"===== 2. 等待 run {run_id} 完成 (轮询间隔 {POLL_INTERVAL_S}s，超时 {MAX_WAIT_S}s) =====")
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


def print_failed_log(run_id: str) -> None:
    log("===== 失败日志 (最后 100 行) =====")
    cp = run_cmd(["gh", "run", "view", run_id, "-R", REPO, "--log-failed"], timeout=120)
    text = (cp.stdout or "") + (cp.stderr or "")
    lines = text.splitlines()
    for line in lines[-100:]:
        print(line)


def download_release_apk(tag: str, dest_dir: Path) -> Path:
    log(f"===== 3. 下载 release {tag} APK =====")
    dest_dir.mkdir(parents=True, exist_ok=True)
    cp = run_with_retry(
        ["gh", "release", "download", tag, "-R", REPO,
         "--pattern", "*.apk", "--dir", str(dest_dir), "--clobber"],
        label="gh release download", attempts=3, base_sleep=10, timeout=600,
    )
    if cp.returncode != 0:
        # 尝试镜像
        log("[fallback] 尝试从 ghproxy 镜像下载 ...")
        # 先查询 release assets
        cp2 = run_cmd(["gh", "release", "view", tag, "-R", REPO,
                       "--json", "assets"], timeout=60)
        if cp2.returncode != 0:
            raise RuntimeError(f"release 未生成: {cp2.stderr}")
        assets = json.loads(cp2.stdout).get("assets", [])
        apk_asset = next((a for a in assets if a["name"].endswith(".apk")), None)
        if not apk_asset:
            raise RuntimeError(f"release {tag} 中找不到 APK asset")
        original = f"https://github.com/{REPO}/releases/download/{tag}/{apk_asset['name']}"
        mirror = f"https://ghproxy.com/{original}"
        local = dest_dir / apk_asset["name"]
        for url in (mirror, original):
            log(f"[curl] {url}")
            cp3 = run_cmd(["curl", "-L", "-fsS", "-o", str(local), url], timeout=600)
            if cp3.returncode == 0 and local.exists() and local.stat().st_size > 1024:
                break
        else:
            raise RuntimeError("镜像下载也失败")
    # 找出下载的 APK
    apks = list(dest_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError(f"未找到下载的 APK in {dest_dir}")
    apk = apks[0]
    log(f"[ok] downloaded: {apk} ({apk.stat().st_size/1024/1024:.2f} MB)")
    return apk


def upload_to_gateway(local_apk: Path, remote_filename: str) -> dict:
    log("===== 4. 上传到部署服务器 =====")
    log(f"local : {local_apk}")
    log(f"remote: /home/ubuntu/{remote_filename}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD,
                timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # SFTP 上传
        sftp = ssh.open_sftp()
        remote_path = f"/home/ubuntu/{remote_filename}"
        log(f"[sftp] putting -> {remote_path}")
        sftp.put(str(local_apk), remote_path)
        st = sftp.stat(remote_path)
        log(f"[sftp] uploaded, size={st.st_size} bytes")
        sftp.close()

        def _exec(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
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

        # 确保 gateway 容器内目录存在
        rc, _, _ = _exec(f"docker exec {GATEWAY_CONTAINER} sh -c 'mkdir -p {GATEWAY_APK_DIR}'")
        if rc != 0:
            raise RuntimeError("无法在 gateway 容器内创建 apk 目录")

        # docker cp
        gateway_path = f"{GATEWAY_APK_DIR}/{remote_filename}"
        rc, _, _ = _exec(
            f"docker cp /home/ubuntu/{remote_filename} {GATEWAY_CONTAINER}:{gateway_path}"
        )
        if rc != 0:
            raise RuntimeError("docker cp 失败")

        # 校验
        rc, out, _ = _exec(f"docker exec {GATEWAY_CONTAINER} ls -la {gateway_path}")
        if rc != 0:
            raise RuntimeError(f"容器内文件不存在: {gateway_path}")

        # 解析 size
        size_bytes = None
        for tok in out.split():
            if tok.isdigit() and int(tok) > 1024:
                size_bytes = int(tok)
                break

        return {"remote_path": remote_path, "gateway_path": gateway_path,
                "size_bytes": size_bytes}
    finally:
        ssh.close()


def http_status(url: str, timeout: int = 30) -> tuple[int, int]:
    """返回 (status_code, content_length)"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "deploy-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            # 只读部分用于校验，但拿到 Content-Length
            cl = resp.headers.get("Content-Length")
            return resp.status, int(cl) if cl else -1
    except urllib.error.HTTPError as e:
        return e.code, -1
    except Exception as e:
        log(f"[http] error: {e}")
        return 0, -1


def main() -> int:
    overall_start = time.time()

    # Step 1: tag
    tag, ts, hexsuf = gen_version_tag()
    log(f"[plan] version tag = {tag}")

    # Step 2: trigger
    build_start = time.time()
    trigger_workflow(tag)
    time.sleep(5)

    # Step 3: get run id
    run_id = get_latest_run_id(tag)

    # Step 4: wait
    conclusion = wait_for_run(run_id)
    build_duration = time.time() - build_start
    if conclusion != "success":
        log(f"[fail] 构建失败 conclusion={conclusion}")
        print_failed_log(run_id)
        return 2
    log(f"[ok] 构建成功，用时 {build_duration:.0f}s")

    # Step 5: download
    tmp_dir = Path(tempfile.mkdtemp(prefix="apk_dl_"))
    try:
        apk = download_release_apk(tag, tmp_dir)
        new_name = f"app_{ts}_{hexsuf}.apk"
        renamed = tmp_dir / new_name
        shutil.copy2(apk, renamed)
        size_mb = renamed.stat().st_size / 1024 / 1024
        log(f"[rename] {apk.name} -> {new_name}  ({size_mb:.2f} MB)")

        # Step 6: upload
        info = upload_to_gateway(renamed, new_name)

        # Step 7: verify
        log("===== 5. 验证 HTTPS 下载链接 =====")
        primary_url = f"{BASE_URL}/apk/{new_name}"
        fallback_url = f"{BASE_URL}/{new_name}"
        for attempt in range(1, 4):
            code, cl = http_status(primary_url)
            log(f"[check] GET {primary_url} -> {code} (CL={cl})")
            if code == 200:
                break
            time.sleep(5)
        else:
            log(f"[fallback] 尝试顶层路径 {fallback_url}")
            code, cl = http_status(fallback_url)
            log(f"[check] GET {fallback_url} -> {code} (CL={cl})")

        total = time.time() - overall_start
        if code == 200:
            log("===== 全部完成 =====")
            print()
            print("====== RESULT ======")
            print(f"VERSION_TAG : {tag}")
            print(f"APK_FILENAME: {new_name}")
            print(f"APK_URL     : {primary_url}")
            print(f"APK_URL_ALT : {fallback_url}")
            print(f"FILE_SIZE   : {size_mb:.2f} MB")
            print(f"HTTP_STATUS : {code}")
            print(f"BUILD_TIME  : {build_duration:.0f}s ({build_duration/60:.1f} min)")
            print(f"TOTAL_TIME  : {total:.0f}s ({total/60:.1f} min)")
            print("====================")
            return 0
        else:
            log(f"[fail] HTTPS 验证失败 status={code}")
            return 3
    finally:
        # 保留临时文件方便排错
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
