"""[BUGFIX-MED-CROSS-PROFILE 2026-06-02] 拉取最新代码并重建后端容器。"""
import sys
import _sshlib as ssh

import os

DID = ssh.DEPLOY_ID
PROJ = f"/home/ubuntu/{DID}"
# Token 从环境变量读取，避免将密钥硬编码进仓库（GitHub Push Protection）。
_GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
_GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = f"https://{_GIT_USER}:{_GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def step(title, cmd, timeout=600):
    print(f"\n===== {title} =====")
    code, out, err = ssh.run(cmd, timeout=timeout)
    print("EXIT", code)
    if out:
        print(out[-4000:])
    if err:
        print("--- STDERR ---")
        print(err[-2000:])
    return code, out, err


# 1. 拉取最新代码
step("Git fetch + reset", (
    f"cd {PROJ} && git remote set-url origin {GIT_URL} && "
    f"timeout 60 git fetch origin master --no-tags && "
    f"git reset --hard origin/master && git log -1 --oneline"
), timeout=120)

# 2. 确认改动已到位
step("Verify code present", (
    f"cd {PROJ} && grep -n 'BUGFIX-MED-CROSS-PROFILE' backend/app/services/health_dashboard_service.py | head"
))

# 3. 重建并重启后端容器
step("Rebuild backend", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache backend"
), timeout=900)

step("Restart backend", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d backend && sleep 8 && "
    f"docker compose -f docker-compose.prod.yml ps"
), timeout=180)

# 4. gateway 重新连网络（保险）
step("Reconnect gateway network", (
    f"GW=$(docker ps --format '{{{{.Names}}}}' | grep -i gateway | head -1); "
    f"echo gateway=$GW; "
    f"docker network connect {DID}-network $GW 2>/dev/null || true"
))

print("\nDONE")
