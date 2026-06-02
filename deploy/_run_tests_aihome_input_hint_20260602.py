"""[PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02] 在后端容器内运行 AI 首页输入区优化的源码断言测试。

由于测试需读取 h5-web/miniprogram/flutter_app 源码，而后端容器内无这些源码，
本脚本先将服务器项目目录中的三端源码 docker cp 进后端容器的 /app 下对应位置，
再运行 pytest。最后清理拷入的源码目录，避免污染容器。
"""
import sys
sys.path.insert(0, ".")
from deploy._sshlib import run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
C = f"{DEPLOY_ID}-backend"


def step(title, cmd, timeout=600):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    if out:
        print(out[-9000:])
    if err:
        print("--- STDERR ---")
        print(err[-2500:])
    print(f"[exit={code}]")
    return code, out, err


# 1. 将三端源码拷入后端容器 /app 下（测试通过 parents[1]=/app 解析）
step("1. 拷入前端三端源码到容器 /app", (
    f"docker exec {C} rm -rf /app/h5-web /app/miniprogram /app/flutter_app 2>/dev/null; "
    f"docker cp {PROJ}/h5-web/src {C}:/app/h5-web_src_tmp 2>&1 | tail -1; "
    # 仅拷贝必要的源码子集，减小体积；保持目录结构与测试解析一致
    f"docker exec {C} mkdir -p /app/h5-web/src && "
    f"docker cp {PROJ}/h5-web/src/app {C}:/app/h5-web/src/app 2>&1 | tail -1; "
    f"docker cp {PROJ}/h5-web/src/components {C}:/app/h5-web/src/components 2>&1 | tail -1; "
    f"docker cp {PROJ}/miniprogram {C}:/app/miniprogram 2>&1 | tail -1; "
    f"docker cp {PROJ}/flutter_app/lib {C}:/app/flutter_app_lib_tmp 2>&1 | tail -1; "
    f"docker exec {C} mkdir -p /app/flutter_app/lib && "
    f"docker cp {PROJ}/flutter_app/lib/screens {C}:/app/flutter_app/lib/screens 2>&1 | tail -1; "
    f"docker exec {C} sh -lc 'ls /app/h5-web/src/app/\"(ai-chat)\"/ai-home/page.tsx && "
    f"ls /app/miniprogram/pages/chat/index.js && ls /app/flutter_app/lib/screens/ai/chat_screen.dart' 2>&1 | tail -5"
), timeout=300)

# 1b. 将本次测试文件从服务器项目目录拷入容器 /app/tests（容器镜像内为旧版测试）
step("1b. 拷入本次测试文件", (
    f"docker cp {PROJ}/backend/tests/test_aihome_input_hint_optim_20260602.py "
    f"{C}:/app/tests/test_aihome_input_hint_optim_20260602.py 2>&1 | tail -1; "
    f"docker cp {PROJ}/backend/tests/test_ai_home_optim_final_v2_20260519.py "
    f"{C}:/app/tests/test_ai_home_optim_final_v2_20260519.py 2>&1 | tail -1; "
    f"docker exec {C} ls -l /app/tests/test_aihome_input_hint_optim_20260602.py "
    f"/app/tests/test_ai_home_optim_final_v2_20260519.py 2>&1 | tail -3"
), timeout=120)

# 2. 确保 pytest + 异步插件可用（conftest.py 依赖 pytest_asyncio / aiosqlite）
step("2. 检查测试依赖", (
    f"docker exec {C} sh -lc \"cd /app && "
    f"python -c 'import pytest_asyncio' 2>/dev/null || "
    f"pip install -q pytest pytest-asyncio aiosqlite >/dev/null 2>&1; "
    f"python -c 'import pytest,pytest_asyncio,aiosqlite; print(\\\"deps ok\\\", pytest.__version__)'\""
), timeout=400)

# 3. 运行本次新增 + 更新的测试
step("3. 运行 AI 首页输入区优化测试", (
    f"docker exec {C} sh -lc \"cd /app && python -m pytest "
    f"tests/test_aihome_input_hint_optim_20260602.py "
    f"tests/test_ai_home_optim_final_v2_20260519.py "
    f"-v -p no:cacheprovider 2>&1 | tail -70\""
), timeout=600)

# 4. 清理拷入的源码
step("4. 清理容器内临时源码", (
    f"docker exec {C} rm -rf /app/h5-web /app/h5-web_src_tmp /app/miniprogram "
    f"/app/flutter_app /app/flutter_app_lib_tmp 2>/dev/null; echo CLEANED"
), timeout=120)

print("\nDONE")
