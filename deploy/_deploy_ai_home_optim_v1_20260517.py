"""[PRD-AIHOME-OPTIM-V1 2026-05-17] 部署脚本：ai-home 顶部 UI 三项优化。

涉及变更（仅前端 H5）：
- h5-web/src/components/ai-chat/ReminderBellButton.tsx
    去掉底色 / 背景框 / 数字徽标，铃铛仅保留 emoji 图标本身；
    初始 top 由父组件传入；位置不再持久化（每次进入页面复位）
- h5-web/src/app/(ai-chat)/ai-home/page.tsx
    R1: 计算 banner 健康贴士卡的垂直中线作为铃铛初始 top
    R2: 汉堡 ☰ 改为 SVG 三横线（第3条50%、等粗、间距等比、高度=小康字号17px）
    R3: 汉堡图标右上角外侧 8px 红色实心圆；
        显示条件 = 未读系统消息数 > 0 OR 待使用订单数 > 0；
        进入页面一次性拉取（增加 /api/orders/unified/counts 请求）

后端无任何代码改动，因此本次只重建 h5-web 镜像。
"""
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"
GIT_BRANCH = "master"


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:])
    if show and err.strip():
        print("STDERR:", err[-1500:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")
    try:
        # git fetch with retry
        for attempt in range(1, 5):
            rc, _, _ = run(
                client,
                f"cd {PROJ_DIR} && timeout 180 git fetch origin {GIT_BRANCH} --depth 5 --no-tags 2>&1 | tail -10",
                timeout=240, ignore_err=True,
            )
            if rc == 0:
                print(f"git fetch ok (attempt {attempt})")
                break
            print(f"git fetch failed (attempt {attempt}), retrying...")
            time.sleep(10 * attempt)
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        h5_container = f"{DEPLOY_ID}-h5-web"

        # 重建 h5-web（后端未改，跳过 backend 重建以加速）
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (may take 3-6 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80", timeout=1500)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

        # 等待 h5-web 健康
        print("\n--- Waiting for h5-web container ---")
        for i in range(40):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            status = out.strip()
            print(f"  [{(i+1)*5}s] h5-web: {status}")
            running = status.startswith("running|")
            health = status.split("|", 1)[1] if "|" in status else ""
            if running and (health == "" or health == "healthy"):
                print("  h5-web ready.")
                break
            time.sleep(5)

        # gateway 接入网络 + reload
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 状态
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 公开路由探活
        print("\n--- Probe public URLs via gateway ---")
        base = f"http://localhost/autodev/{DEPLOY_ID}"
        probes = [
            f"{base}/",
            f"{base}/ai-home",
            f"{base}/api/v1/notifications/unread-count",
            f"{base}/api/orders/unified/counts",
        ]
        probe_cmd = " ; ".join(
            f"curl -s -o /dev/null -w '%{{http_code}}  {u}\\n' '{u}'"
            for u in probes
        )
        run(client, probe_cmd, ignore_err=True)

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
