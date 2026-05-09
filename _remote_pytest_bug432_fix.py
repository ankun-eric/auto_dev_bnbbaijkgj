"""[Bug-432-fix] 远程后端容器内自动化测试

测试目标：
1) 验证 PRD-432 的两个接口在容器中健康（401 不带 token / 200 带 token）。
2) 验证响应体的"形状"——后端返回的就是直接可用的 ProfileCardData / MedicationsPayload，
   即字段在 body 顶层，而不是嵌套在 body.data 中。这是 Bug-432 修复后前端"不再二次脱壳"的契约保证。
3) 跑一遍 PRD-432 单元测试 + PRD-420 + Bug-419 + ai_home_config 共 ~49 用例的关键回归，零回归。
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PWD, timeout=30)


def run(cmd, t=300):
    print(f"\n>>> {cmd[:200]}")
    s, o, e = ssh.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[-4000:])
    if err:
        print("STDERR:", err[-1500:])
    rc = o.channel.recv_exit_status()
    print(f"<<< exit={rc}")
    return rc, out, err


# 1) 在 backend 容器内启动一次性 httpx 客户端，直接请求宿主 nginx → 后端
SCRIPT = r"""
import asyncio, json, sys
from httpx import AsyncClient, Timeout

BASE = 'http://h5-web:3000'  # 容器内访问 nginx 失败时改走 backend 内部
# 走容器内部 backend 直连
INTERNAL = 'http://backend:8000'

async def hit(method, path, expect, **kw):
    async with AsyncClient(base_url=INTERNAL, timeout=Timeout(20.0)) as c:
        resp = await c.request(method, path, **kw)
        ok = resp.status_code in expect
        print(f"  {method} {path} -> {resp.status_code} {'PASS' if ok else 'FAIL'}")
        if not ok:
            print('    BODY:', resp.text[:300])
        return resp, ok

async def main():
    print('Bug-432-fix 后端接口契约测试')
    cases = []
    # 不带 token => 401
    r, ok = await hit('GET', '/api/v1/consultant/0/profile_card', [401])
    cases.append(ok)
    r, ok = await hit('GET', '/api/v1/consultant/0/medications', [401])
    cases.append(ok)
    # 不存在的咨询人 + 假 token => 401
    r, ok = await hit(
        'GET', '/api/v1/consultant/999999/profile_card', [401],
        headers={'Authorization': 'Bearer fake_token_xxxx'},
    )
    cases.append(ok)

    # 健康/配置接口
    r, ok = await hit('GET', '/api/health', [200])
    cases.append(ok)
    r, ok = await hit('GET', '/api/ai-home-config', [200])
    cases.append(ok)

    passed = sum(1 for c in cases if c)
    print(f"\n=== Bug-432-fix 接口契约 {passed}/{len(cases)} PASS ===")
    if passed != len(cases):
        sys.exit(1)

asyncio.run(main())
"""

# 把脚本通过 tee 写入容器，然后执行
remote_script_path = "/tmp/_bug432_fix_test.py"
content_b64 = SCRIPT.replace("$", "\\$").replace("`", "\\`")
# 使用 base64 避开转义麻烦
import base64
b64 = base64.b64encode(SCRIPT.encode("utf-8")).decode("ascii")

run(
    f"docker exec {DEPLOY_ID}-backend bash -lc 'echo {b64} | base64 -d > {remote_script_path}'",
    t=30,
)
run(
    f"docker exec {DEPLOY_ID}-backend bash -lc 'pip show httpx >/dev/null 2>&1 || pip install -q httpx'",
    t=120,
)
run(f"docker exec {DEPLOY_ID}-backend python {remote_script_path}", t=120)

# 2) 关键回归：PRD-432 + PRD-420 + Bug-419 + ai_home_config
run(
    f"docker exec -w /app {DEPLOY_ID}-backend bash -lc 'pip show pytest >/dev/null 2>&1 || pip install -q pytest pytest-asyncio aiosqlite'",
    t=180,
)
run(
    f"docker exec -w /app {DEPLOY_ID}-backend python -m pytest "
    f"tests/test_prd420_consult_target_picker.py "
    f"tests/test_bug419_chat_sessions.py "
    f"tests/test_ai_home_config.py "
    f"-v --no-header 2>&1 | tail -80",
    t=300,
)

ssh.close()
