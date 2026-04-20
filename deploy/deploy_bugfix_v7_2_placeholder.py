"""Bug 2 回归修复 v7.2：强制把服务器上 `home_search_placeholder` 重置为「搜索您想要的健康服务」。

做法：
1. SSH + git fetch/reset 最新代码（已含 v7_2_normalized 迁移脚本）。
2. docker compose build backend 并 force-recreate backend 容器。
3. 校验 /api/home-config 返回的 search_placeholder 是否为「搜索您想要的健康服务」。
"""
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def ssh_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return rc, out, err


def main() -> int:
    print(f"[1/5] 连接 SSH → {USER}@{HOST}:{PORT}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, PORT, USER, PASSWORD, timeout=30)
    try:
        print(f"[2/5] git pull 最新代码 @ {PROJECT_DIR}")
        rc, out, err = ssh_exec(
            client,
            f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git rev-parse --short HEAD",
            timeout=180,
        )
        print(out.strip() or err.strip())
        if rc != 0:
            print(f"git pull 失败 rc={rc}")
            return rc

        print("[3/5] docker compose build backend + 重建 backend 容器")
        rc, out, err = ssh_exec(
            client,
            f"cd {PROJECT_DIR} && docker compose build backend 2>&1 | tail -40",
            timeout=900,
        )
        print(out.strip())
        if rc != 0:
            print(f"build 失败 rc={rc}: {err.strip()}")
            return rc

        rc, out, err = ssh_exec(
            client,
            f"cd {PROJECT_DIR} && docker compose up -d --force-recreate backend 2>&1 | tail -10",
            timeout=180,
        )
        print(out.strip())

        print("[4/5] 等待 backend 容器就绪 ...")
        for i in range(30):
            time.sleep(3)
            rc, out, _ = ssh_exec(
                client,
                f"docker ps --filter name={BACKEND_CONTAINER} --format '{{{{.Status}}}}'",
            )
            status = out.strip()
            if status and "Up" in status and "starting" not in status.lower():
                print(f"  ✓ backend Up（{status}）")
                break
            print(f"  ... {i+1}/30 {status}")
        else:
            print("backend 未在 90s 内进入 Up 状态")

        print("[5/5] 校验 /api/home-config 的 search_placeholder")
        import urllib.request
        import ssl
        import json

        time.sleep(3)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        for attempt in range(5):
            try:
                with urllib.request.urlopen(
                    f"{BASE_URL}/api/home-config", context=ctx, timeout=20
                ) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sp = data.get("search_placeholder")
                    print(f"  当前 search_placeholder = {sp!r}")
                    if sp == "搜索您想要的健康服务":
                        print("  ✓ 校验通过：Bug 2 已彻底修复")
                        return 0
                    else:
                        print(f"  attempt {attempt+1}/5：尚未更新，再等 5s")
                        time.sleep(5)
            except Exception as e:  # noqa: BLE001
                print(f"  attempt {attempt+1}/5 网络异常：{e}")
                time.sleep(5)
        print("×× 校验失败")
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
