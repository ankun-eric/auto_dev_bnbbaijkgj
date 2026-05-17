"""[BUG_FIX_TIMEZONE_GLOBAL_20260517] 全系统时区根治 - 部署脚本

只需要同步：
- backend/app/core/price_formatter.py（全局 datetime 拦截）
- backend/tests/test_timezone_global_20260517.py（单元测试，可选）
- h5-web/src/lib/datetime.ts、admin-web/src/lib/datetime.ts（前端新工具）

然后 restart backend 容器；前端工具是新文件、未被其他组件 import，不影响运行时。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def _ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    return cli


def _run(cli, cmd, timeout=180):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def _find_remote_dir(cli):
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
    return f"/home/ubuntu/autodev/{PROJECT_ID}"


def _put_file(sftp, local: Path, remote: str):
    remote_dir = os.path.dirname(remote).replace("\\", "/")
    try:
        sftp.stat(remote_dir)
    except IOError:
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


FILES = [
    # 后端核心
    "backend/app/core/price_formatter.py",
    "backend/tests/test_timezone_global_20260517.py",
    # 前端工具（新增；不会被 import 影响运行时）
    "h5-web/src/lib/datetime.ts",
    "admin-web/src/lib/datetime.ts",
    # 小程序工具（仅用于 zip 打包，运行时不需要）
    "miniprogram/utils/datetime.js",
    # Flutter
    "flutter_app/lib/utils/datetime_utils.dart",
]


def main():
    local_root = Path(__file__).resolve().parent
    print(f"[ssh] connecting {USER}@{HOST}")
    cli = _ssh()
    try:
        remote_root = _find_remote_dir(cli)
        sftp = cli.open_sftp()
        try:
            print(f"[remote_root] {remote_root}")
            for rel in FILES:
                local = local_root / rel
                if not local.exists():
                    print(f"[skip] {rel}: 本地不存在")
                    continue
                remote = f"{remote_root}/{rel}".replace("\\", "/")
                _put_file(sftp, local, remote)
                print(f"[uploaded] {rel}")
        finally:
            sftp.close()

        container = f"{PROJECT_ID}-backend"
        print(f"[docker] cp price_formatter.py into container {container}")
        # 同时把文件 docker cp 进容器（防止 volume 没挂载源码的场景）
        c, _, e = _run(
            cli,
            f"docker cp {remote_root}/backend/app/core/price_formatter.py {container}:/app/app/core/price_formatter.py",
            timeout=60,
        )
        print(f"  cp exit={c} err={e.strip()[:200]}")

        print(f"[docker] restart {container}")
        c, out, err = _run(cli, f"docker restart {container}", timeout=120)
        print(f"  exit={c} out={out.strip()[:200]} err={err.strip()[:200]}")

        print("[wait] backend ready (max 60s)")
        ok = False
        for i in range(20):
            c, out, _ = _run(
                cli,
                f"docker exec {container} sh -c 'curl -sf http://localhost:8000/api/health 2>/dev/null || wget -qO- http://localhost:8000/api/health'",
                timeout=10,
            )
            if c == 0 and out.strip():
                print(f"  ready @ {i*3}s : {out.strip()[:120]}")
                ok = True
                break
            time.sleep(3)
        if not ok:
            print("[WARN] backend 健康检查超时")

        _, log_out, _ = _run(cli, f"docker logs --tail 50 {container}", timeout=20)
        print("---- backend.log tail ----")
        print(log_out[-3000:])
        return 0 if ok else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
