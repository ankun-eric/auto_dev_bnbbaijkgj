"""[PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02] 部署 AI 首页输入区优化。

本次变更：H5(ai-home) + 小程序(pages/chat) + Flutter(chat_screen) + 后端测试。
仅 H5 走 Docker 重建（小程序/Flutter 不走容器）。后端无业务代码改动，仅新增/更新测试文件，
需在服务器项目目录拉取最新代码以供源码断言测试读取。

流程：服务器 git fetch+reset → 强制无缓存重建 h5-web → 重连 gateway 网络 → reload。
"""
import sys
sys.path.insert(0, ".")
from deploy._sshlib import run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GW = "gateway-nginx"


def step(title, cmd, timeout=900):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print(out[-4000:] if out else "")
    if err:
        print("--- STDERR ---")
        print(err[-2000:])
    print(f"[exit={code}]")
    return code, out, err


# 1. 拉取最新代码
step("1. Git 拉取最新代码", (
    f"cd {PROJ} && git fetch origin --depth 1 --no-tags 2>&1 | tail -3 && "
    f"git reset --hard origin/master && git clean -fd -e .env -e .env.production -e .env.build && "
    f"git log -1 --oneline"
), timeout=120)

# 2. 强制无缓存重建 h5-web
step("2. 重建 h5-web 容器（--no-cache）", (
    f"cd {PROJ} && BUILD_COMMIT=$(git log -1 --format=%H) && export BUILD_COMMIT && "
    f"echo BUILD_COMMIT=$BUILD_COMMIT && "
    f"docker compose build --no-cache h5-web 2>&1 | tail -25"
), timeout=1800)

# 3. 启动 h5-web
step("3. 启动 h5-web", (
    f"cd {PROJ} && docker compose up -d h5-web 2>&1 | tail -10"
), timeout=300)

# 4. 等待并查看状态
step("4. 容器状态", (
    f"sleep 8 && docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}"
), timeout=60)

# 5. 重连 gateway 到项目网络
step("5. gateway 重连项目网络", (
    f"docker network connect {DEPLOY_ID}-network {GW} 2>/dev/null; "
    f"docker network inspect {DEPLOY_ID}-network --format "
    f"'{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'"
), timeout=60)

# 6. reload gateway
step("6. gateway reload", (
    f"docker exec {GW} nginx -t 2>&1 && docker exec {GW} nginx -s reload 2>&1 && echo RELOAD_OK"
), timeout=60)

print("\n部署脚本执行完毕。")
