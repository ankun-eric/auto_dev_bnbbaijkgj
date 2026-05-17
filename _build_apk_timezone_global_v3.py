"""
全系统时区根治 v3 - Flutter 安卓 APK 打包自动化脚本

流程：
  1. 提交 flutter_app/ 与 .android_tag.txt 变更并推送
  2. 生成版本标签 android-v<YYYYMMDD>-<HHMMSS>-<4hex>
  3. 触发 GitHub Actions workflow（android-build.yml）
  4. 轮询监控（每 30s，最多 30 分钟）
  5. 下载 APK
  6. 通过 SSH/SCP 上传到服务器 docker 容器 + 宿主机持久化
  7. 验证 HTTP 可访问性
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(r"C:\auto_output\bnbbaijkgj")
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

LOG_FILE = REPO_DIR / "_build_apk_v3_log.txt"

# ------------------------------------------------------------------ utils


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        pass


def run(cmd: list[str], cwd: Path | None = None, check: bool = True,
        timeout: int = 120, capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        timeout=timeout,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if proc.stdout:
        log("stdout: " + proc.stdout.strip()[:1500])
    if proc.stderr:
        log("stderr: " + proc.stderr.strip()[:1500])
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (rc={proc.returncode}): {' '.join(cmd)}")
    return proc


def run_retry(cmd: list[str], cwd: Path | None = None, max_retries: int = 3,
              timeout: int = 120, base_delay: int = 10) -> subprocess.CompletedProcess:
    delay = base_delay
    last: subprocess.CompletedProcess | None = None
    for attempt in range(1, max_retries + 1):
        try:
            proc = run(cmd, cwd=cwd, check=False, timeout=timeout)
            last = proc
            if proc.returncode == 0:
                return proc
            log(f"attempt {attempt}/{max_retries} failed rc={proc.returncode}")
        except subprocess.TimeoutExpired:
            log(f"attempt {attempt}/{max_retries} timed out after {timeout}s")
        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"All {max_retries} attempts failed: {' '.join(cmd)}")


# ------------------------------------------------------------------ steps


def commit_and_push() -> None:
    log("=== STEP 1/2: commit + push flutter changes ===")
    proc = run(["git", "status", "--porcelain", "flutter_app/", ".android_tag.txt"],
               cwd=REPO_DIR, check=True)
    changed = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not changed:
        log("No flutter changes to commit. Skipping commit step.")
        return

    log(f"Found {len(changed)} flutter-related changes to stage")
    run(["git", "add", "flutter_app/", ".android_tag.txt"], cwd=REPO_DIR)

    proc = run(["git", "diff", "--cached", "--name-only"], cwd=REPO_DIR)
    staged = (proc.stdout or "").strip().splitlines()
    log(f"Staged files: {len(staged)}")
    if not staged:
        log("Nothing actually staged, skipping commit.")
        return

    msg = "fix(flutter): timezone v3 - 替换 DateTime.parse 散写为统一工具"
    run(["git", "commit", "-m", msg], cwd=REPO_DIR)

    run_retry(["git", "push", "origin", "HEAD:master"], cwd=REPO_DIR, max_retries=3, timeout=180)
    log("Push succeeded.")


def generate_version_tag() -> str:
    now = datetime.now()
    rand_hex = secrets.token_hex(2)  # 4 hex chars
    tag = f"android-v{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{rand_hex}"
    log(f"Generated version tag: {tag}")
    (REPO_DIR / ".android_tag.txt").write_text(tag + "\n", encoding="utf-8")
    return tag


def trigger_workflow(tag: str) -> None:
    log(f"=== STEP 3: trigger workflow with version={tag} ===")
    run_retry(
        ["gh", "workflow", "run", "android-build.yml", "-f", f"version={tag}"],
        cwd=REPO_DIR, max_retries=3, timeout=120,
    )
    time.sleep(5)


def get_latest_run_id() -> int:
    proc = run_retry(
        ["gh", "run", "list", "--workflow=android-build.yml", "--limit", "1",
         "--json", "databaseId,status,conclusion,headBranch,event,createdAt"],
        cwd=REPO_DIR, max_retries=3, timeout=60,
    )
    runs = json.loads(proc.stdout or "[]")
    if not runs:
        raise RuntimeError("No workflow runs found.")
    return int(runs[0]["databaseId"])


def poll_run(run_id: int, max_minutes: int = 30) -> str:
    log(f"=== STEP 5: polling run {run_id} ===")
    deadline = time.time() + max_minutes * 60
    last_status = None
    while time.time() < deadline:
        try:
            proc = run(
                ["gh", "run", "view", str(run_id), "--json", "status,conclusion"],
                cwd=REPO_DIR, check=False, timeout=60,
            )
            if proc.returncode != 0:
                log("gh run view failed, retrying in 30s")
                time.sleep(30)
                continue
            data = json.loads(proc.stdout or "{}")
            status = data.get("status")
            conclusion = data.get("conclusion")
            if status != last_status:
                log(f"status={status} conclusion={conclusion}")
                last_status = status
            if status == "completed":
                return conclusion or "unknown"
        except Exception as e:  # noqa: BLE001
            log(f"poll error: {e}")
        time.sleep(30)
    raise TimeoutError(f"Workflow run {run_id} did not finish in {max_minutes}m")


def download_apk(tag: str) -> Path:
    log(f"=== STEP 6: download APK for release {tag} ===")
    out_dir = REPO_DIR / "_apk_downloads"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*.apk"):
        try:
            f.unlink()
        except Exception:
            pass

    # try gh release download (with retry)
    last_exc = None
    for attempt in range(1, 4):
        try:
            run(
                ["gh", "release", "download", tag, "--pattern", "*.apk", "--dir", str(out_dir)],
                cwd=REPO_DIR, check=True, timeout=600,
            )
            break
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log(f"gh release download attempt {attempt} failed: {e}")
            time.sleep(15 * attempt)
    else:
        # fallback: read assets and curl
        log("Falling back to curl download")
        proc = run(["gh", "release", "view", tag, "--json", "assets"], cwd=REPO_DIR, timeout=60)
        info = json.loads(proc.stdout or "{}")
        assets = info.get("assets", [])
        apk_asset = next((a for a in assets if a.get("name", "").endswith(".apk")), None)
        if not apk_asset:
            raise RuntimeError(f"No APK asset in release {tag}") from last_exc
        url = apk_asset.get("url") or apk_asset.get("browserDownloadUrl") or apk_asset["apiUrl"]
        out_file = out_dir / apk_asset["name"]
        run(["curl", "-L", "-o", str(out_file), url], check=True, timeout=600)

    apks = list(out_dir.glob("*.apk"))
    if not apks:
        raise RuntimeError("APK download finished but no .apk file present")
    apk = apks[0]
    log(f"Downloaded APK: {apk} ({apk.stat().st_size:,} bytes)")
    return apk


def _ssh_exec(client, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    log(f"ssh$ {cmd[:300]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        log("stdout: " + out.strip()[:1500])
    if err:
        log("stderr: " + err.strip()[:1500])
    log(f"rc={rc}")
    return rc, out, err


def upload_to_server(apk_path: Path) -> tuple[str, str]:
    log("=== STEP 7: upload APK to server (via paramiko) ===")
    import paramiko  # type: ignore

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(3)
    remote_name = f"app_{ts}_{rand}.apk"

    remote_tmp = f"/tmp/{remote_name}"
    persist_dir = f"/home/ubuntu/{PROJECT_ID}/h5-web/public"
    persist_path = f"{persist_dir}/{remote_name}"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last_exc = None
    for attempt in range(1, 4):
        try:
            client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30, banner_timeout=30, auth_timeout=30)
            break
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log(f"ssh connect attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    else:
        raise RuntimeError(f"SSH connect failed: {last_exc}")

    try:
        # 1. SFTP upload to /tmp
        log(f"sftp upload {apk_path} -> {remote_tmp} ({apk_path.stat().st_size:,} bytes)")
        sftp = client.open_sftp()
        try:
            sftp.put(str(apk_path), remote_tmp)
        finally:
            sftp.close()
        rc, _, _ = _ssh_exec(client, f"ls -la {remote_tmp}")
        if rc != 0:
            raise RuntimeError("upload verify failed")

        # 2. persistent copy + docker cp into h5-web container
        remote_cmd = (
            f"set -e; "
            f"echo '[mkdir persist]'; sudo -n mkdir -p {persist_dir} 2>&1 || mkdir -p {persist_dir}; "
            f"echo '[cp persist]'; sudo -n cp {remote_tmp} {persist_path} 2>&1 || cp {remote_tmp} {persist_path}; "
            f"sudo -n chmod 644 {persist_path} 2>/dev/null || chmod 644 {persist_path}; "
            f"echo '[find h5-web container]'; "
            f"CID=$(sudo -n docker ps --format '{{{{.ID}}}} {{{{.Names}}}}' 2>/dev/null "
            f" | grep -E '{PROJECT_ID}.*h5-web|h5-web.*{PROJECT_ID}' | head -1 | awk '{{print $1}}'); "
            f"if [ -z \"$CID\" ]; then "
            f"  CID=$(sudo -n docker ps --format '{{{{.ID}}}} {{{{.Names}}}}' 2>/dev/null | grep -i h5-web | head -1 | awk '{{print $1}}'); "
            f"fi; "
            f"echo \"H5_CID=$CID\"; "
            f"if [ -n \"$CID\" ]; then "
            f"  CNAME=$(sudo -n docker inspect --format '{{{{.Name}}}}' $CID 2>/dev/null | sed 's|^/||'); "
            f"  echo \"CONTAINER_NAME=$CNAME\"; "
            f"  sudo -n docker cp {remote_tmp} $CID:/app/public/{remote_name} 2>&1 && echo '[cp /app/public OK]' || true; "
            f"  sudo -n docker cp {remote_tmp} $CID:/usr/share/nginx/html/{remote_name} 2>&1 && echo '[cp nginx html OK]' || true; "
            f"  sudo -n docker exec $CID ls -la /app/public/{remote_name} 2>/dev/null && echo '[verify /app/public OK]' || true; "
            f"  sudo -n docker exec $CID ls -la /usr/share/nginx/html/{remote_name} 2>/dev/null && echo '[verify nginx html OK]' || true; "
            f"fi; "
            f"rm -f {remote_tmp}; "
            f"ls -la {persist_path}"
        )
        rc, out, err = _ssh_exec(client, remote_cmd, timeout=300)
        if rc != 0:
            log(f"remote command non-zero rc={rc}, output: {out}\nerr: {err}")
    finally:
        client.close()

    download_url = f"{BASE_URL}/{remote_name}"
    log(f"APK should be downloadable at: {download_url}")
    return remote_name, download_url


def verify_url(url: str) -> tuple[int, dict]:
    log(f"=== STEP 8: verify {url} ===")
    # use curl -I, parse status code
    last_status = 0
    headers: dict[str, str] = {}
    for attempt in range(1, 6):
        try:
            proc = run(["curl", "-sIL", "--max-time", "30", url], check=False, timeout=60)
            out = proc.stdout or ""
            # find final status code
            statuses = [int(s.split()[1]) for s in out.splitlines()
                        if s.upper().startswith("HTTP/") and len(s.split()) >= 2 and s.split()[1].isdigit()]
            if statuses:
                last_status = statuses[-1]
            for line in out.splitlines():
                if ":" in line and not line.upper().startswith("HTTP/"):
                    k, _, v = line.partition(":")
                    headers[k.strip().lower()] = v.strip()
            log(f"attempt {attempt}: HTTP {last_status} content-length={headers.get('content-length')}")
            if last_status == 200:
                return last_status, headers
        except Exception as e:  # noqa: BLE001
            log(f"verify attempt {attempt} error: {e}")
        time.sleep(5 * attempt)
    return last_status, headers


# ------------------------------------------------------------------ main


def main() -> int:
    start = time.time()
    LOG_FILE.write_text("", encoding="utf-8")
    log("=== Flutter Android APK build automation (timezone v3) START ===")
    log(f"Repo: {REPO_DIR}")
    log(f"Project URL: {BASE_URL}")

    # Step 1: commit + push
    commit_and_push()

    # Step 2: generate tag
    tag = generate_version_tag()

    # commit the tag file change too (best-effort)
    try:
        proc = run(["git", "status", "--porcelain", ".android_tag.txt"], cwd=REPO_DIR)
        if (proc.stdout or "").strip():
            run(["git", "add", ".android_tag.txt"], cwd=REPO_DIR)
            run(["git", "commit", "-m", f"chore(flutter): android tag {tag}"], cwd=REPO_DIR, check=False)
            run_retry(["git", "push", "origin", "HEAD:master"], cwd=REPO_DIR, max_retries=3, timeout=180)
    except Exception as e:  # noqa: BLE001
        log(f"tag-commit non-fatal error: {e}")

    # Step 3: trigger workflow
    trigger_workflow(tag)

    # find run id (poll a few times because gh may not list new run immediately)
    run_id = None
    for _ in range(20):
        try:
            time.sleep(5)
            run_id = get_latest_run_id()
            log(f"Latest run id = {run_id}")
            break
        except Exception as e:  # noqa: BLE001
            log(f"waiting for run to appear: {e}")
    if run_id is None:
        raise RuntimeError("Could not find triggered workflow run.")

    # Step 5: poll
    attempts_remaining = 2
    while True:
        conclusion = poll_run(run_id, max_minutes=30)
        log(f"Run {run_id} concluded: {conclusion}")
        if conclusion == "success":
            break
        if attempts_remaining <= 0:
            try:
                run(["gh", "run", "view", str(run_id), "--log-failed"], cwd=REPO_DIR, check=False, timeout=120)
            except Exception:
                pass
            raise RuntimeError(f"Workflow failed: {conclusion}")
        log(f"Build failed, dumping failed logs and retrying ({attempts_remaining} retries left)")
        try:
            run(["gh", "run", "view", str(run_id), "--log-failed"], cwd=REPO_DIR, check=False, timeout=120)
        except Exception:
            pass
        attempts_remaining -= 1
        trigger_workflow(tag)
        time.sleep(10)
        run_id = get_latest_run_id()

    # Step 6: download APK
    apk = download_apk(tag)

    # Step 7: upload to server
    remote_name, url = upload_to_server(apk)

    # Step 8: verify
    status, headers = verify_url(url)

    elapsed = time.time() - start
    release_url = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{tag}"

    summary = {
        "tag": tag,
        "apk_local": str(apk),
        "apk_size": apk.stat().st_size,
        "server_filename": remote_name,
        "download_url": url,
        "github_release_url": release_url,
        "http_status": status,
        "content_length": headers.get("content-length"),
        "content_type": headers.get("content-type"),
        "elapsed_sec": round(elapsed, 1),
        "build_success": True,
    }
    (REPO_DIR / "_build_apk_v3_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("=== SUMMARY ===")
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log(f"FATAL: {exc}")
        import traceback
        log(traceback.format_exc())
        sys.exit(2)
