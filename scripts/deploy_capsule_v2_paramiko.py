#!/usr/bin/env python3
"""[PRD-AICHAT-CAPSULE-V2] 通过 paramiko SSH 部署到远程服务器并验证。"""
import sys
import time
import urllib.request
import ssl

import paramiko


HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
# 服务器上的项目路径，需要从远程现场探测
PROJECT_PATHS_TO_TRY = [
    f"/home/ubuntu/projects/{DEPLOY_ID}",
    f"/home/ubuntu/auto_dev/{DEPLOY_ID}",
    f"/home/ubuntu/{DEPLOY_ID}",
    f"/opt/projects/{DEPLOY_ID}",
    f"/home/ubuntu/auto_dev_bnbbaijkgj",
]


def ssh_connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def find_project_path(client: paramiko.SSHClient) -> str | None:
    for p in PROJECT_PATHS_TO_TRY:
        rc, _, _ = run(client, f"test -d {p}/.git")
        if rc == 0:
            return p
    # fallback: 用 find 搜
    rc, out, _ = run(
        client,
        "find /home/ubuntu -maxdepth 4 -type d -name '" + DEPLOY_ID + "*' 2>/dev/null | head -3",
    )
    for line in out.strip().splitlines():
        if line.strip():
            return line.strip()
    return None


def http_status(url: str, expect: tuple[int, ...] = (200, 301, 302), timeout: int = 30) -> tuple[bool, int]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "deploy-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = resp.status
            return code in expect, code
    except urllib.error.HTTPError as e:
        return e.code in expect, e.code
    except Exception:
        return False, 0


def main():
    print(f"[deploy] Connecting to {HOST} ...")
    client = ssh_connect()
    try:
        print(f"[deploy] Finding project path ...")
        project_path = find_project_path(client)
        if not project_path:
            print("[deploy] FATAL: 找不到项目目录")
            return 2
        print(f"[deploy] Project path = {project_path}")

        # 1) 拉取最新代码
        print(f"[deploy] step 1: git pull")
        rc, out, err = run(
            client,
            f"cd {project_path} && git fetch --all -p && git reset --hard origin/master && git log -1 --oneline",
            timeout=300,
        )
        print(out[-2000:])
        if err.strip():
            print("STDERR:", err[-500:])
        if rc != 0:
            print(f"[deploy] step1 failed rc={rc}")
            return 2

        # 2) 拉构建
        print(f"[deploy] step 2: docker compose up -d --build backend admin-web h5-web ...")
        rc, out, err = run(
            client,
            f"cd {project_path} && docker compose up -d --build backend admin-web h5-web 2>&1 | tail -300",
            timeout=2400,
        )
        print(out[-4000:])
        if rc != 0:
            print(f"[deploy] step2 failed rc={rc}")
            return 2

        # 3) 等容器健康
        print("[deploy] step 3: wait 30s for backend startup migration ...")
        time.sleep(30)

        # 4) 验证容器日志中能看到迁移完成
        print(f"[deploy] step 4: check backend container has migration log ...")
        rc, out, _ = run(
            client,
            f"docker logs --tail 300 {DEPLOY_ID}-backend 2>&1 | grep -E 'PRD-CAPSULE-V2|prd_capsule_v2|startup' | tail -20",
            timeout=60,
        )
        print(out)

        # 5) HTTP 健康检查
        print(f"[deploy] step 5: HTTP probe")
        paths = [
            ("/api/docs", (200, 301, 302)),
            ("/api/function-buttons", (200,)),
            ("/admin/", (200, 301, 302)),
            ("/ai-home", (200, 301, 302)),
        ]
        all_ok = True
        for p, codes in paths:
            ok, code = http_status(BASE_URL + p, codes)
            mark = "OK" if ok else "FAIL"
            print(f"  {p:32s} HTTP {code:3d}  {mark}")
            if not ok:
                all_ok = False
        if not all_ok:
            print("[deploy] FAIL: some checks failed")
            return 3
        print("[deploy] ALL OK")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
