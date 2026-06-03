"""仅重建 h5-web 容器（不动 git，因为代码已通过 SFTP 直接上传）。"""
import sys
sys.path.insert(0, "deploy")
from _sshlib import run, DEPLOY_ID

PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GW = "gateway-nginx"
NET = f"{DEPLOY_ID}-network"


def step(title, cmd, timeout=1800):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print("EXIT", code)
    if out:
        print(out[-3500:])
    if err:
        print("--- STDERR ---")
        print(err[-1500:])
    return code, out, err


step("Build h5-web --no-cache", (
    f"cd {PROJ} && BUILD_COMMIT=manual-$(date +%Y%m%d%H%M%S) && export BUILD_COMMIT && "
    f"docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -20"
), timeout=1800)

step("Up h5-web", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -8"
), timeout=300)

step("Wait & status", (
    f"cd {PROJ} && sleep 8 && docker compose -f docker-compose.prod.yml ps h5-web"
), timeout=60)

step("Reconnect gateway + reload", (
    f"docker network connect {NET} {GW} 2>/dev/null; "
    f"docker exec {GW} nginx -s reload 2>&1; echo reloaded"
), timeout=60)

print("\n===== DONE =====")
