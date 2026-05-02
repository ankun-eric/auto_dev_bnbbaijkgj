# -*- coding: utf-8 -*-
"""[2026-05-02 H5 下单流程优化 PRD v1.0] 远程部署 + URL 健康检查脚本

流程：
1. SSH 到服务器
2. 进入 /home/ubuntu/auto_dev_bnbbaijkgj（不存在则 git clone）
3. git fetch + reset 到最新 master
4. docker compose build / up -d backend admin-web h5-web
5. 等待启动后 curl 关键 URL，必须全部 200/302
"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
import os

GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
REPO_URL = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
PROJECT_DIR = f"/home/ubuntu/projects/{PROJECT_ID}"
BASE = f"https://{HOST}/autodev/{PROJECT_ID}"


def run(client: paramiko.SSHClient, cmd: str, *, timeout: int = 600, get_pty: bool = True) -> tuple[int, str]:
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    data = []
    for line in iter(stdout.readline, ""):
        if not line:
            break
        print(line.rstrip(), flush=True)
        data.append(line)
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="ignore")
    if err.strip():
        print("[stderr]", err, flush=True)
    return rc, "".join(data) + err


def main() -> int:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting {HOST}@{USER} ...", flush=True)
    cli.connect(HOST, username=USER, password=PASS, timeout=60, banner_timeout=60)

    # 1. 克隆/更新代码
    rc, _ = run(cli, f"test -d {PROJECT_DIR}/.git && echo OK || echo NO", timeout=30)
    rc, out = run(cli, f"ls {PROJECT_DIR} 2>/dev/null && echo HAS || echo NO", timeout=30)
    has_git = "OK" in out or " .git" in out

    if not has_git:
        run(cli, f"mkdir -p $(dirname {PROJECT_DIR})", timeout=30)
        run(cli, f"rm -rf {PROJECT_DIR}", timeout=60)
        run(cli, f"git clone {REPO_URL} {PROJECT_DIR}", timeout=600)
    else:
        run(cli, f"cd {PROJECT_DIR} && git fetch --all --prune", timeout=300)
        run(cli, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=120)

    # 2. 构建 + 启动
    rc, _ = run(cli,
        f"cd {PROJECT_DIR} && docker compose build backend admin-web h5-web",
        timeout=1800)
    if rc != 0:
        print("BUILD FAIL", flush=True)
        return rc

    rc, _ = run(cli,
        f"cd {PROJECT_DIR} && docker compose up -d db backend admin-web h5-web",
        timeout=600)
    if rc != 0:
        print("UP FAIL", flush=True)
        return rc

    # 3. 等待 backend 起来
    print("\nWaiting for backend to be ready...", flush=True)
    for i in range(60):
        rc, out = run(
            cli,
            f"docker exec {PROJECT_ID}-backend curl -sf -o /dev/null -w '%{{http_code}}' http://localhost:8000/health || echo FAIL",
            timeout=15,
        )
        if "200" in out:
            print(f"Backend ready at attempt {i+1}", flush=True)
            break
        time.sleep(3)
    else:
        run(cli, f"docker logs --tail 200 {PROJECT_ID}-backend", timeout=30)
        return 1

    # 4. 关键 URL 检查
    targets = [
        f"{BASE}/api/health",
        f"{BASE}/h5/login",
        f"{BASE}/admin/login",
        f"{BASE}/api/products?status=active&page=1&size=5",
    ]
    fail = []
    print("\n=== URL Health Check ===", flush=True)
    for u in targets:
        cmd = f"curl -ks -o /dev/null -w '%{{http_code}}' '{u}'"
        rc, out = run(cli, cmd, timeout=30)
        code = (out.strip().split()[-1] if out else "000")
        ok = code in {"200", "204", "301", "302", "307"}
        print(f"  [{code}] {u}  {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            fail.append((u, code))

    cli.close()
    if fail:
        print("\nFAILURES:", fail, flush=True)
        return 2
    print("\nALL OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
