"""[INCIDENT-20260513-01] H5 全量同步 + 重建脚本

目标：把本地 git master HEAD 的 h5-web/ 完整 SFTP 上传到测试服，
覆盖服务器上漂移的旧源码，然后 docker compose --no-cache 重建并启动。

执行步骤：
  ① SFTP 全量同步 h5-web/（递归遍历，排除构建/缓存产物）
  ② docker compose build --no-cache h5-web
  ③ docker compose up -d h5-web
  ④ 简单容器健康检查（docker ps + logs tail）

PRD 锁定参数：
  - 源码：git master HEAD（即本地工作区，已确认无暂存丢失）
  - build：--no-cache
  - 不备份服务器旧源码
"""
from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_H5 = f"{REMOTE_PROJ}/h5-web"
H5_SERVICE = "h5-web"
H5_CONTAINER = f"{DEPLOY_ID}-h5"

LOCAL_ROOT = Path(__file__).resolve().parent.parent
LOCAL_H5 = LOCAL_ROOT / "h5-web"

# 必须严格执行的排除规则（与 PRD 一致）
EXCLUDE_DIRS = {
    ".next", "node_modules", "dist", "build", "out",
    ".git", ".turbo", ".cache", ".src_backup_prd444",
    "__pycache__", ".vscode", ".idea",
}
EXCLUDE_FILES_EXACT = {
    "tsconfig.tsbuildinfo",
    ".DS_Store",
    "Thumbs.db",
}
EXCLUDE_FILES_SUFFIX = (".log", ".tmp")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS or name.startswith(".pytest_cache")


def should_skip_file(name: str) -> bool:
    if name in EXCLUDE_FILES_EXACT:
        return True
    if name.endswith(EXCLUDE_FILES_SUFFIX):
        return True
    return False


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run_ssh(cli: paramiko.SSHClient, cmd: str, timeout: int = 600, log_cmd: bool = True) -> tuple[int, str, str]:
    if log_cmd:
        short = cmd if len(cmd) <= 220 else cmd[:220] + "..."
        log(f"$ {short}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str, cache: set) -> None:
    if remote_dir in cache or remote_dir in ("", "/"):
        return
    parent = remote_dir.rsplit("/", 1)[0]
    if parent and parent not in cache:
        sftp_mkdirs(sftp, parent, cache)
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
    cache.add(remote_dir)


def collect_local_files() -> list[tuple[Path, str]]:
    """返回 [(本地绝对路径, 远端相对 h5-web/ 的子路径), ...]"""
    items: list[tuple[Path, str]] = []
    for root, dirs, files in os.walk(LOCAL_H5):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for f in files:
            if should_skip_file(f):
                continue
            local_abs = Path(root) / f
            rel = local_abs.relative_to(LOCAL_H5).as_posix()
            items.append((local_abs, rel))
    return items


def upload_all(cli: paramiko.SSHClient, items: list[tuple[Path, str]]) -> int:
    log(f"=== Step 1: SFTP 全量上传 {len(items)} 个文件到 {REMOTE_H5}/ ===")
    sftp = cli.open_sftp()
    sftp.get_channel().settimeout(60)
    mkdir_cache: set = set()
    sftp_mkdirs(sftp, REMOTE_H5, mkdir_cache)
    uploaded = 0
    failed: list[str] = []
    t0 = time.time()
    for local_abs, rel in items:
        remote_path = f"{REMOTE_H5}/{rel}"
        remote_dir = remote_path.rsplit("/", 1)[0]
        sftp_mkdirs(sftp, remote_dir, mkdir_cache)
        for attempt in range(3):
            try:
                sftp.put(str(local_abs), remote_path)
                uploaded += 1
                if uploaded % 50 == 0:
                    elapsed = time.time() - t0
                    log(f"  ... 已上传 {uploaded}/{len(items)} ({elapsed:.1f}s)")
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    log(f"  [FAIL] {rel}: {e}")
                    failed.append(rel)
                else:
                    time.sleep(1.5)
    sftp.close()
    log(f"=== Step 1 完成：成功 {uploaded}/{len(items)}，失败 {len(failed)}，耗时 {time.time()-t0:.1f}s ===")
    if failed:
        log("失败文件列表：")
        for f in failed[:30]:
            log(f"  - {f}")
        return 1
    return 0


def cleanup_stale_dirs(cli: paramiko.SSHClient) -> None:
    """清理服务器上排除规则中的缓存目录，避免污染 build。"""
    log("=== Step 1.5: 清理服务器构建缓存与历史备份目录 ===")
    targets = [
        ".next", "node_modules", "dist", "build", "out",
        ".turbo", ".cache", ".src_backup_prd444",
        "tsconfig.tsbuildinfo",
    ]
    for t in targets:
        run_ssh(cli, f"rm -rf {REMOTE_H5}/{t}", log_cmd=True)


def docker_no_cache_build(cli: paramiko.SSHClient) -> int:
    log("=== Step 2: docker compose build --no-cache h5-web（5-10 分钟）===")
    log_file = f"/tmp/h5-web-build-{time.strftime('%Y%m%d_%H%M%S')}.log"
    cmd = (
        f"cd {REMOTE_PROJ} && "
        f"sudo docker compose build --no-cache {H5_SERVICE} 2>&1 | tee {log_file} | tail -200"
    )
    rc, out, err = run_ssh(cli, cmd, timeout=1500)
    print(out)
    if err.strip():
        print(f"STDERR: {err}")
    log(f"build 日志位于服务器 {log_file}")
    if rc != 0:
        log(f"[ERROR] build 失败 rc={rc}")
        return 1
    return 0


def docker_up(cli: paramiko.SSHClient) -> int:
    log("=== Step 3: docker compose up -d h5-web ===")
    rc, out, err = run_ssh(
        cli,
        f"cd {REMOTE_PROJ} && sudo docker compose up -d {H5_SERVICE}",
        timeout=300,
    )
    print(out)
    if err.strip():
        print(f"STDERR: {err}")
    if rc != 0:
        log("[ERROR] docker compose up 失败")
        return 1
    log("等待容器就绪 20 秒...")
    time.sleep(20)
    run_ssh(cli, f"sudo docker ps --filter name={H5_CONTAINER} --format '{{{{.Names}}}}\\t{{{{.Status}}}}'")
    run_ssh(cli, f"sudo docker logs --tail 80 {H5_CONTAINER} 2>&1 | tail -80", log_cmd=False)
    return 0


def main() -> int:
    log("INCIDENT-20260513-01 H5 全量同步 + --no-cache 重建")
    log(f"本地源：{LOCAL_H5}")
    log(f"远端目标：{HOST}:{REMOTE_H5}")
    if not LOCAL_H5.exists():
        log(f"[ABORT] 本地 h5-web 目录不存在")
        return 1

    items = collect_local_files()
    log(f"本地待上传文件数：{len(items)}（已按排除规则过滤）")

    cli = ssh_connect()
    try:
        cleanup_stale_dirs(cli)
        rc = upload_all(cli, items)
        if rc != 0:
            return rc

        # 上传后再次清掉服务器上的构建缓存（上传过程不应带入这些，但兜底）
        run_ssh(cli, f"rm -rf {REMOTE_H5}/.next {REMOTE_H5}/node_modules {REMOTE_H5}/tsconfig.tsbuildinfo")

        rc = docker_no_cache_build(cli)
        if rc != 0:
            log("[STOP] build 失败，老容器仍在运行，不切流量。请人工查看日志后修复重跑。")
            return rc

        rc = docker_up(cli)
        if rc != 0:
            return rc

        log("=== 同步与重建完成。进入 smoke test 阶段（请运行 _verify_h5web_ai_chat_20260513.py）===")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
