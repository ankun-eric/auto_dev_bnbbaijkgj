import sys
sys.path.insert(0, ".")
from deploy._sshlib import run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
GW = "gateway-nginx"


def step(title, cmd, timeout=120):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print(out[-3500:] if out else "")
    if err:
        print("--- ERR ---"); print(err[-1200:])
    print(f"[exit={code}]")
    return code, out, err


# h5 容器实际所在网络
step("h5 容器网络", (
    f"docker inspect {DEPLOY_ID}-h5 --format "
    f"'{{{{range $k,$v := .NetworkSettings.Networks}}}}{{{{$k}}}}={{{{$v.IPAddress}}}} {{{{end}}}}'"
))

# gateway 关于本项目的 location 配置
step("gateway location 配置", (
    f"docker exec {GW} sh -c \"grep -rl {DEPLOY_ID} /etc/nginx/ 2>/dev/null\""
))

# 跟随重定向探测 health-profile 页面，确认含关键标识
step("外部探测 health-profile/（跟随重定向）", (
    f"curl -sL -m 20 '{BASE}/health-profile/' | grep -o 'health-profile\\|健康档案\\|__next' | head -5; "
    f"echo '---code---'; curl -sL -o /dev/null -w '%{{http_code}}' -m 20 '{BASE}/health-profile/'"
))

print("\n完毕。")
