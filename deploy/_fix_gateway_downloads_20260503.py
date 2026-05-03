"""检查并补充 gateway nginx 的 /downloads/ 静态资源映射。

策略（极保守）：
1. 先看项目自身 nginx（容器内或服务器上 ./deploy/nginx 是否管 downloads）
2. 直接在服务器创建/确认 /home/ubuntu/{DEPLOY_ID}/downloads 软链或共享卷
3. 通过 backend 容器自带的静态文件挂载 /uploads，把 downloads 也由 backend 暴露：
   把 downloads/ 复制进 backend 容器的 /app/uploads/downloads/，再用 BASE/uploads/downloads/...
（这是最快不动 gateway nginx 的办法）
"""
from __future__ import annotations

import paramiko
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run(ssh, cmd, timeout=120):
    print(f">>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out.strip():
        print(out.rstrip()[-2000:])
    if err.strip():
        print(f"[stderr] {err.rstrip()[-1000:]}")
    return stdout.channel.recv_exit_status(), out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        run(ssh, f"ls -lh {PROJ_DIR}/downloads 2>&1 | head -10")
        # 把 downloads/ 拷到 backend 容器的 /app/uploads/downloads/，借用现成 /uploads 静态挂载
        run(ssh, f"docker exec {DEPLOY_ID}-backend mkdir -p /app/uploads/downloads")
        run(
            ssh,
            f"docker cp {PROJ_DIR}/downloads/. {DEPLOY_ID}-backend:/app/uploads/downloads/",
            timeout=300,
        )
        run(ssh, f"docker exec {DEPLOY_ID}-backend ls -lh /app/uploads/downloads/ | head -5")

        # 验证 /uploads/downloads/<file>
        _, ls_out, _ = run(ssh, f"ls -1 {PROJ_DIR}/downloads/ | head -5")
        for f in ls_out.strip().splitlines():
            f = f.strip()
            if not f:
                continue
            url = f"{BASE}/uploads/downloads/{f}"
            cmd = f"curl -ksL -o /dev/null -w '%{{http_code}} %{{size_download}}' --max-time 30 '{url}'"
            _, out, _ = run(ssh, cmd)
            print(f"  {f} -> {out.strip()}")
            print(f"  URL: {url}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
