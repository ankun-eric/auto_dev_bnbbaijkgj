"""[PRD-FAMILY-INVITE-QRCODE-UNIFY] 部署 H5：git 拉取最新 + 仅重建 h5-web 容器。"""
import sys
sys.path.insert(0, "deploy")
from _sshlib import run, DEPLOY_ID

PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GW = "gateway-nginx"
NET = f"{DEPLOY_ID}-network"


def step(title, cmd, timeout=1200):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print("EXIT", code)
    if out:
        print(out[-4000:])
    if err:
        print("--- STDERR ---")
        print(err[-2000:])
    return code, out, err


# 1. Git 拉取最新代码
step("Git fetch + reset", (
    f"cd {PROJ} && git fetch origin master --no-tags 2>&1 | tail -5 && "
    f"git reset --hard origin/master 2>&1 | tail -3 && git log -1 --oneline"
), timeout=180)

# 2. 仅重建 h5-web 容器（--no-cache 防静默部署）
step("Build h5-web --no-cache", (
    f"cd {PROJ} && BUILD_COMMIT=$(git log -1 --format=%H) && export BUILD_COMMIT && "
    f"docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -25"
), timeout=1800)

# 3. 重启 h5-web 容器
step("Up h5-web", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10"
), timeout=300)

# 4. 等待容器就绪
step("Wait & status", (
    f"cd {PROJ} && sleep 8 && docker compose -f docker-compose.prod.yml ps h5-web"
), timeout=60)

# 5. 重新连接 gateway 到项目网络（双保险）
step("Reconnect gateway network", (
    f"docker network connect {NET} {GW} 2>/dev/null; "
    f"docker exec {GW} nginx -s reload 2>&1; echo reloaded"
), timeout=60)

print("\n===== DONE =====")
