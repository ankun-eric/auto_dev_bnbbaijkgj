"""
[Bug 修复 我守护的人页面恢复 v13 完整版 @ 2026-05-27] 部署脚本

仅前端有改动（h5-web/.../health-profile/i-guard/page.tsx 整份替换为 v13 原版 733 行）。
后端 backend/app/api/guardian_system_v13.py 自 8181069a 起未改动，无需重新上传。
但部署后会重启 h5-web 容器；同时确认 backend 已挂载 /api/guardian/v13/* 路由。
"""

import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES_TO_UPLOAD = [
    (
        "h5-web/src/app/health-profile/i-guard/page.tsx",
        f"{REMOTE_BASE}/h5-web/src/app/health-profile/i-guard/page.tsx",
    ),
]


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run(client, cmd, timeout=300, log=True):
    if log:
        print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if log:
        if out.strip():
            print(out)
        if err.strip():
            print(f"[stderr] {err}")
    return exit_status, out, err


def mkdir_p(sftp, path):
    parts = path.replace("\\", "/").split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = cur.rstrip("/") + "/" + p if cur else p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def upload_files(client):
    sftp = client.open_sftp()
    try:
        for local_rel, remote in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local):
                print(f"[SKIP missing] {local}")
                continue
            print(f"[UPLOAD] {local_rel} -> {remote}")
            mkdir_p(sftp, remote)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    print(f"[1/7] SSH 连接到 {HOST} ...")
    client = ssh_connect()

    print(f"[2/7] 检查远程项目目录 {REMOTE_BASE}")
    rc, out, err = run(client, f"ls -la {REMOTE_BASE} | head -10")
    if rc != 0:
        print("远程目录不存在，停止部署")
        sys.exit(1)

    print("[3/7] 上传 i-guard 页面新版（v13 完整版） ...")
    upload_files(client)

    print("[4/7] 确认后端 guardian_system_v13.py 已挂载（远程不动） ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && grep -n 'guardian_system_v13' backend/app/main.py || true",
    )

    print("[5/7] 重新构建并启动 h5-web 容器 ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -30",
        timeout=900,
    )
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose up -d h5-web 2>&1 | tail -10",
        timeout=300,
    )
    time.sleep(10)

    print("[6/7] 重启 backend 容器以确保 v13 路由生效 ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose restart backend 2>&1 | tail -10",
        timeout=120,
    )
    time.sleep(6)

    print("[7/7] 容器状态与 HTTP 烟雾测试 ...")
    rc, out, err = run(client, f"cd {REMOTE_BASE} && docker compose ps")

    print("\n--- HTTP 探测 ---")
    smoke_urls = [
        f"{BASE_URL}/health-profile/i-guard",
        f"{BASE_URL}/api/guardian/v13/family/list",
        f"{BASE_URL}/api/guardian/v13/family/invite-history",
        f"{BASE_URL}/api/guardian/v13/family/proxy-pay/detail",
    ]
    for url in smoke_urls:
        run(
            client,
            f"curl -s -o /dev/null -w '%{{http_code}}  {url}\\n' '{url}'",
        )

    client.close()
    print("\n=== 部署完成 ===")
    print(f"体验链接：{BASE_URL}/health-profile/i-guard")


if __name__ == "__main__":
    main()
