"""[PRD-SLEEP-ALL-HISTORY-FIX-V1 2026-06-02] 部署 H5 睡眠全部历史模板修复。
git fetch+reset 到最新，重建 H5 容器（--no-cache），重连 gateway 网络并验证。
"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway-nginx"


def run(cmd, timeout=1800):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        c.close()


def step(title, cmd, timeout=1800):
    print(f"\n===== {title} =====", flush=True)
    code, out, err = run(cmd, timeout=timeout)
    print(f"EXIT {code}")
    if out:
        print(out[-4000:])
    if err:
        print("STDERR:", err[-2000:])
    return code, out, err


# 1. 拉取最新代码
step("1. Git fetch + reset", (
    f"cd {PROJ} && git fetch origin --depth 50 --no-tags 2>&1 | tail -3 && "
    f"git reset --hard origin/master && git log -1 --oneline && "
    f"echo '--- grep SLEEP-ALL-HISTORY-FIX-V1 in history page ---' && "
    f"grep -c 'SLEEP-ALL-HISTORY-FIX-V1' h5-web/src/app/health-metric/\\[type\\]/history/page.tsx"
), timeout=120)

# 2. 写入 BUILD_COMMIT
step("2. 写入 BUILD_COMMIT", (
    f"cd {PROJ} && BUILD_COMMIT=$(git log -1 --format=%H) && "
    f"grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null; mv .env.tmp .env 2>/dev/null; "
    f"echo \"BUILD_COMMIT=$BUILD_COMMIT\" >> .env && echo \"BUILD_COMMIT=$BUILD_COMMIT\""
), timeout=60)

# 3. 重建 H5 容器（--no-cache）
step("3. 重建 H5 容器 (--no-cache)", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -25"
), timeout=1800)

# 4. 重新启动 H5 容器
step("4. 启动 H5 容器", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10"
), timeout=300)

# 5. 等待并重连网络
time.sleep(8)
step("5. 重连 gateway 网络 + 容器状态", (
    f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>/dev/null; "
    f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}"
), timeout=60)

# 6. reload gateway
step("6. reload gateway", f"docker exec {GATEWAY} nginx -t 2>&1 && docker exec {GATEWAY} nginx -s reload 2>&1 && echo RELOADED", timeout=60)

print("\n部署脚本执行完成", flush=True)
