"""验证 health-profile 页面与相关接口在服务器上可访问。"""
import sys
sys.path.insert(0, ".")
from deploy._sshlib import run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
GW = "gateway-nginx"


def step(title, cmd, timeout=120):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print(out[-3000:] if out else "")
    if err:
        print("--- STDERR ---"); print(err[-1500:])
    print(f"[exit={code}]")
    return code, out, err


# 网络成员核实（h5/backend 是否在 network 内）
step("network 成员", (
    f"docker network inspect {DEPLOY_ID}-network --format "
    f"'{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'"
))

# 从 gateway 内部直连 h5 容器
step("gateway 内部直连 h5 容器:3000", (
    f"docker exec {GW} sh -c 'wget -qO- -T5 http://{DEPLOY_ID}-h5:3000/autodev/{DEPLOY_ID}/health-profile 2>&1 | head -c 200' || echo FAIL"
))

# 外部 URL 探测 health-profile 页面
for path in ["/health-profile", "/"]:
    step(f"外部探测 {path}", (
        f"curl -s -o /dev/null -w '%{{http_code}}' -m 15 '{BASE}{path}'"
    ))

print("\n验证完毕。")
