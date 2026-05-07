"""[BUG_FIX_预约看板_20260507] 商家 PC 端预约看板菜单缺失 + 旧路径重复入口修复部署脚本

不依赖 git fetch（远程到 GitHub 太慢），改用 SFTP 上传 + ssh 删除目录。

流程：
1. SSH 连接服务器
2. SFTP 上传修改的文件（lib.ts、m/dashboard/page.tsx）
3. 通过 ssh rm -rf 删除 merchant/calendar、merchant/m/calendar 目录
4. docker compose build h5-web
5. docker compose up -d --force-recreate h5-web
6. gateway nginx reload
7. HTTPS smoke：
   - /merchant/order-dashboard/ 应 200
   - /merchant/calendar/ 应 404
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

# 本次修改的文件（SFTP 上传）
FILES = [
    "h5-web/src/app/merchant/lib.ts",
    "h5-web/src/app/merchant/m/dashboard/page.tsx",
]

# 本次需要删除的目录
DIRS_TO_REMOVE = [
    "h5-web/src/app/merchant/calendar",
    "h5-web/src/app/merchant/m/calendar",
]


def exec_cmd(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[exec] {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err and code != 0:
        print("[stderr]", err[-2000:])
    return code, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    client.connect(
        HOST, port=22, username=USER, password=PASSWORD,
        timeout=30, banner_timeout=30, auth_timeout=30,
    )
    sftp = client.open_sftp()

    # 1) 上传修改文件
    repo_root = Path(__file__).resolve().parent
    print(f"\n=== SFTP 上传修改文件 ===  repo={repo_root}")
    for rel in FILES:
        local = repo_root / rel
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        if not local.exists():
            print(f"  - SKIP missing: {local}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        exec_cmd(client, f"mkdir -p '{remote_dir}'")
        print(f"  ↑ {rel}  ({local.stat().st_size} bytes)")
        sftp.put(str(local), remote)
    sftp.close()

    # 2) 删除旧 calendar 目录
    print("\n=== 删除旧 calendar 目录 ===")
    for d in DIRS_TO_REMOVE:
        rd = f"{PROJECT_DIR}/{d}"
        exec_cmd(client, f"rm -rf '{rd}' && echo removed: {d}", timeout=30)
        exec_cmd(client, f"ls '{rd}' 2>&1 || echo 'confirmed gone: {d}'", timeout=10)

    # 2.5) 标记 git 为干净状态（避免 git status 干扰运维）
    exec_cmd(
        client,
        f"cd {PROJECT_DIR} && git status --short | head -20 || true",
        timeout=20,
    )

    # 3) 构建 h5-web
    print("\n=== docker compose build h5-web ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -200",
        timeout=900,
    )
    if rc != 0:
        print("[fail] h5-web build 失败")
        client.close()
        return 1

    # 4) up -d
    print("\n=== docker compose up -d --force-recreate h5-web ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose up -d --force-recreate h5-web 2>&1 | tail -60",
        timeout=240,
    )
    if rc != 0:
        print("[warn] up -d 退出非零，继续后续验证")

    time.sleep(10)

    # 5) gateway reload
    print("\n=== gateway nginx reload ===")
    exec_cmd(client, "docker exec gateway nginx -t 2>&1 | tail -10", timeout=30)
    exec_cmd(client, "docker exec gateway nginx -s reload 2>&1 | tail -10", timeout=30)

    # 6) HTTPS smoke
    print("\n=== HTTPS smoke ===")
    urls = [
        (f"{BASE_URL}/merchant/login/", "200|3"),
        (f"{BASE_URL}/merchant/dashboard/", "200|3"),
        (f"{BASE_URL}/merchant/order-dashboard/", "200|3"),
        (f"{BASE_URL}/merchant/calendar/", "404"),
        (f"{BASE_URL}/merchant/m/calendar/", "404"),
        (f"{BASE_URL}/merchant/m/dashboard/", "200|3"),
        (f"{BASE_URL}/api/openapi.json", "200"),
    ]
    smoke_pass = True
    fails = []
    for u, expected in urls:
        rc, out, err = exec_cmd(
            client, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{u}'", timeout=20,
        )
        code = (out or "").strip()
        if expected == "404":
            ok = code == "404"
        elif expected == "200":
            ok = code == "200"
        elif expected == "200|3":
            ok = code in ("200", "301", "302", "303", "307", "308")
        else:
            ok = False
        marker = "OK  " if ok else "FAIL"
        print(f"  [{marker}] {u} -> {code} (expect {expected})")
        if not ok:
            smoke_pass = False
            fails.append((u, code, expected))

    # 7) 容器内确认 Next.js 路由产物
    print("\n=== 容器内 Next.js 路由产物检查 ===")
    container = f"{DEPLOY_ID}-h5-web"
    exec_cmd(
        client,
        f"docker exec {container} sh -lc 'ls /app/.next/server/app/merchant/ 2>/dev/null | head -40 || echo no_dir'",
        timeout=30,
    )
    exec_cmd(
        client,
        f"docker exec {container} sh -lc 'ls /app/.next/server/app/merchant/m/ 2>/dev/null | head -40 || echo no_dir'",
        timeout=30,
    )
    # 关键：确认 calendar 目录已不在产物中
    exec_cmd(
        client,
        f"docker exec {container} sh -lc 'find /app/.next/server/app/merchant -type d -name calendar 2>/dev/null; echo done'",
        timeout=30,
    )

    client.close()
    print("\n=== 部署完成 ===")
    print(f"smoke_pass={smoke_pass}")
    if fails:
        print("FAILED URLS:")
        for u, c, e in fails:
            print(f"  {u}  got={c} expect={e}")
    return 0 if smoke_pass else 2


if __name__ == "__main__":
    sys.exit(main())
