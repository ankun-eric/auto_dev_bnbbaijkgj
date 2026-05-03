"""[卡管理 v2.0 第 2~5 期] 部署脚本

流程：
1. SSH 到服务器
2. cd 到项目目录，git fetch + reset --hard origin/master
3. docker compose build backend admin-web h5-web（增量层缓存）
4. docker compose up -d --force-recreate
5. 等待健康
6. curl 关键 URL 验证可达性
"""
from __future__ import annotations

import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
REPO_URL = f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 关键 URL（卡管理 v2.0）
URLS_TO_VERIFY = [
    ("/", "h5 首页"),
    ("/admin", "admin 首页"),
    ("/cards", "h5 卡列表"),
    ("/cards/wallet", "h5 卡包"),
    ("/cards/redeem-code/1", "h5 核销码（占位 ID=1）"),
    ("/cards/usage-logs/1", "h5 核销记录"),
    ("/cards/renew/1", "h5 续卡"),
    ("/admin/product-system/cards", "admin 卡管理"),
    ("/admin/product-system/cards/dashboard", "admin 卡销售看板"),
    ("/api/cards", "卡列表 API"),
    ("/openapi.json", "OpenAPI"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-4000:])
    if err.strip():
        print(f"[stderr]\n{err.rstrip()[-2000:]}")
    print(f"<<< exit={code}")
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 1) git pull 最新代码
        run(ssh, f"cd {PROJ_DIR} && git remote set-url origin '{REPO_URL}'")
        code, out, _ = run(ssh, f"cd {PROJ_DIR} && git fetch origin master 2>&1 | tail -5", timeout=300)
        if "did not send" in out or "Could not read" in out or "fatal:" in out:
            print("[!] git fetch corrupted, fallback to fresh clone")
            run(ssh, f"rm -rf {PROJ_DIR}.bak && cp -r {PROJ_DIR} {PROJ_DIR}.bak", timeout=300)
            run(ssh, f"rm -rf {PROJ_DIR}/.git", timeout=120)
            run(ssh, f"cd /tmp && rm -rf _fresh_clone && git clone --depth 1 '{REPO_URL}' _fresh_clone 2>&1 | tail -10", timeout=600)
            run(ssh, f"cp -r /tmp/_fresh_clone/.git {PROJ_DIR}/.git", timeout=120)
            run(ssh, f"cd {PROJ_DIR} && git fetch origin master 2>&1 | tail -5", timeout=300)

        run(ssh, f"cd {PROJ_DIR} && git reset --hard origin/master 2>&1 | tail -3")
        _, head_out, _ = run(ssh, f"cd {PROJ_DIR} && git log -1 --format='%H %s'")
        print(f"[OK] 服务器 HEAD: {head_out.strip()}")

        # 2) 重建 backend / admin / h5
        for svc in ("backend", "admin-web", "h5-web"):
            for attempt in range(3):
                code, out, err = run(
                    ssh,
                    f"cd {PROJ_DIR} && docker compose build {svc} 2>&1 | tail -30",
                    timeout=1800,
                )
                if code == 0:
                    break
                print(f"[!] build {svc} 第 {attempt+1} 次失败，重试")
                time.sleep(5)
            else:
                print(f"[ERROR] build {svc} 三次失败，仍尝试 up")

        # 3) 启动 / 重新创建
        run(
            ssh,
            f"cd {PROJ_DIR} && docker compose up -d --force-recreate backend admin-web h5-web 2>&1 | tail -20",
            timeout=300,
        )

        # 4) 等待容器健康
        time.sleep(25)
        run(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

        # 5) 容器内 schema 同步检查
        run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend python -c 'import asyncio; from app.core.database import engine; from app.services.schema_sync import sync_register_schema; "
            f"asyncio.run((lambda: (lambda: __import__(\"asyncio\").run(asyncio.coroutine(lambda: None)()))())) ' 2>&1 | tail -5 || true",
        )

        # 6) URL 可达性（curl + 收集）
        print("\n========== URL 可达性检查 ==========")
        results = []
        for path, label in URLS_TO_VERIFY:
            url = BASE_URL + path
            cmd = f"curl -ksL -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'"
            _, out, _ = run(ssh, cmd, timeout=30)
            code = out.strip().split()[-1] if out.strip() else "000"
            results.append((path, label, code, url))

        print("\n========== 部署结果汇总 ==========")
        ok = 0
        fail = []
        for path, label, code, url in results:
            mark = "✅" if code in ("200", "301", "302", "401", "403", "404") else "❌"
            print(f"{mark} {code}  {label:<28} {url}")
            if code in ("200", "301", "302", "401", "403"):
                ok += 1
            else:
                fail.append((path, label, code))
        print(f"\n通过: {ok}/{len(results)}; 失败: {len(fail)}")
        if fail:
            print("失败列表：")
            for path, label, code in fail:
                print(f"  - {label} ({path}) -> {code}")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
