"""非UI冒烟：确认新组件标识进入产物 + 相关接口可达。"""
import sys
sys.path.insert(0, ".")
from deploy._sshlib import run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def step(title, cmd, timeout=120):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print(out[-3000:] if out else "")
    if err:
        print("--- ERR ---"); print(err[-1000:])
    print(f"[exit={code}]")
    return code, out, err


# 1. 新组件文件确实编译进 standalone 产物（grep data-testid 标识）
step("1. 产物含 health-info-fields 标识", (
    f"docker exec {DEPLOY_ID}-h5 sh -c "
    f"\"grep -rl 'health-info-fields\\|hif-add-surgery-btn' /app/.next 2>/dev/null | head -3\""
))

# 2. health-profile chunk 含手术史/家族病史关键字
step("2. 产物含 添加手术史/家族病史", (
    f"docker exec {DEPLOY_ID}-h5 sh -c "
    f"\"grep -rl '添加手术史\\|添加家族病史' /app/.next 2>/dev/null | head -3\""
))

# 3. 相关后端接口（未登录预期 401/403/422，只要不是 5xx/404 即说明路由存在）
for ep, name in [
    ("/api/family/members", "家庭成员"),
    ("/api/health/profile/member/1", "成员档案"),
    ("/api/prd469/health-info/1", "扩展健康信息"),
]:
    step(f"3. 接口 {name} {ep}", (
        f"curl -s -o /dev/null -w '%{{http_code}}' -m 12 '{BASE}{ep}'"
    ))

print("\n冒烟完毕。")
