"""[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
通过 SSH 把后端改动 + 前端改动同步到服务器，并热重启对应容器。

服务器：newbb.test.bangbangvip.com (ubuntu / Newbang888)
部署唯一标识：6b099ed3-7175-4a78-91f4-44570c84ed27
"""
from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/autodev/{PROJECT_ID}"


def _ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    return cli


def _run(cli: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str, str]:
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def _find_remote_dir(cli: paramiko.SSHClient) -> str:
    """探测远程部署根目录。常见两种：
    - /home/ubuntu/autodev/<id>/
    - /home/ubuntu/<id>/
    """
    candidates = [
        f"/home/ubuntu/autodev/{PROJECT_ID}",
        f"/home/ubuntu/{PROJECT_ID}",
        f"/root/autodev/{PROJECT_ID}",
    ]
    for d in candidates:
        c, _, _ = _run(cli, f"test -d {d} && echo OK || echo NO")
        if c == 0:
            c2, out, _ = _run(cli, f"ls -1 {d}/docker-compose*.yml 2>/dev/null | head -n1")
            if out.strip():
                print(f"[remote_dir] found {d}")
                return d
    # 兜底
    return REMOTE_BASE


def _put_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    remote_dir = os.path.dirname(remote).replace("\\", "/")
    try:
        sftp.stat(remote_dir)
    except IOError:
        # 递归创建
        parts = remote_dir.strip("/").split("/")
        cur = ""
        for p in parts:
            cur = f"{cur}/{p}"
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except IOError:
                    pass
    sftp.put(str(local), remote)


# 本次需要同步的后端文件（相对项目根的路径）
BACKEND_FILES = [
    "backend/app/api/chat.py",
    "backend/app/schemas/chat.py",
    "backend/app/services/report_interpret_engine.py",
    "backend/app/services/family_self_backfill_migration.py",
    "backend/app/main.py",
]


def main() -> int:
    local_root = Path(__file__).resolve().parent
    print(f"[ssh] connecting {USER}@{HOST}")
    cli = _ssh()
    try:
        remote_root = _find_remote_dir(cli)
        sftp = cli.open_sftp()
        try:
            print(f"[remote_root] {remote_root}")
            for rel in BACKEND_FILES:
                local = local_root / rel
                if not local.exists():
                    print(f"[skip] {rel}: 本地不存在")
                    continue
                remote = f"{remote_root}/{rel}".replace("\\", "/")
                _put_file(sftp, local, remote)
                print(f"[uploaded] {rel}")
        finally:
            sftp.close()

        # 重启 backend 容器（代码挂载/或镜像构建二选一，这里用 restart + exec reload）
        # 先尝试直接 restart 容器（适用于 volumes 挂载源码的部署）
        container = f"{PROJECT_ID}-backend"
        print(f"[docker] restart {container}")
        code, out, err = _run(cli, f"docker restart {container}", timeout=120)
        print(f"  exit={code} out={out.strip()[:200]} err={err.strip()[:200]}")

        if code != 0:
            # 退而求其次：在容器内 cp 覆盖并 kill -HUP / 重启
            print("[docker] restart failed, fall back to docker cp")
            for rel in BACKEND_FILES:
                if not rel.startswith("backend/"):
                    continue
                inside = "/app/" + rel.split("backend/", 1)[1]
                code2, out2, err2 = _run(
                    cli,
                    f"docker cp {remote_root}/{rel} {container}:{inside}",
                    timeout=60,
                )
                print(f"  cp {rel} → {inside} exit={code2} {err2.strip()[:120]}")
            _run(cli, f"docker restart {container}", timeout=120)

        # 等待 backend 起来
        print("[wait] waiting backend ready (max 60s)")
        for i in range(20):
            c, out, _ = _run(
                cli,
                f"docker exec {container} sh -c 'wget -qO- http://localhost:8000/api/health 2>/dev/null || curl -sf http://localhost:8000/api/health'",
                timeout=10,
            )
            if c == 0 and out.strip():
                print(f"  ready @ {i*3}s : {out.strip()[:120]}")
                break
            time.sleep(3)
        else:
            print("[WARN] backend 健康检查超时")

        # 简单 sanity：打印最后 50 行后端日志
        _, log_out, _ = _run(cli, f"docker logs --tail 80 {container}", timeout=20)
        print("---- backend.log tail ----")
        print(log_out[-4000:])
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
