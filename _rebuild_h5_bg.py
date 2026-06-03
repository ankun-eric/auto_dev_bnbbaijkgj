"""服务器端后台构建 h5-web（nohup + 日志），轮询直到完成，避免 SSH 流中断。"""
import sys, time
sys.path.insert(0, "deploy")
from _sshlib import run, DEPLOY_ID

PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GW = "gateway-nginx"
NET = f"{DEPLOY_ID}-network"
LOG = f"{PROJ}/_h5_invite_build.log"


def step(title, cmd, timeout=120):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print("EXIT", code)
    if out:
        print(out[-3000:])
    if err:
        print("--- STDERR ---", err[-1200:])
    return code, out, err


# 启动后台构建
step("Start background build", (
    f"cd {PROJ} && rm -f _h5_invite_build.log && "
    f"nohup bash -c 'export BUILD_COMMIT=manual-$(date +%s); "
    f"docker compose -f docker-compose.prod.yml build --no-cache h5-web > _h5_invite_build.log 2>&1; "
    f"echo BUILD_EXIT=$? >> _h5_invite_build.log' >/dev/null 2>&1 & echo started pid=$!"
), timeout=60)

# 轮询日志
done = False
for i in range(40):  # 最多 ~20 分钟
    time.sleep(30)
    code, out, err = run(f"tail -3 {LOG} 2>/dev/null", timeout=30)
    tail = (out or "").strip()
    print(f"[poll {i}] {tail[-300:]}")
    if "BUILD_EXIT=" in (out or ""):
        done = True
        print("BUILD FINISHED:", [l for l in out.splitlines() if "BUILD_EXIT" in l])
        break

if not done:
    print("!! build still running after polling window")

# 完整结果尾部
step("Build log tail", f"tail -25 {LOG}", timeout=30)

# Up + reload
step("Up h5-web", (
    f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -8 && "
    f"sleep 8 && docker compose -f docker-compose.prod.yml ps h5-web"
), timeout=300)

step("Reconnect gateway + reload", (
    f"docker network connect {NET} {GW} 2>/dev/null; docker exec {GW} nginx -s reload 2>&1; echo reloaded"
), timeout=60)

print("\n===== DONE =====")
