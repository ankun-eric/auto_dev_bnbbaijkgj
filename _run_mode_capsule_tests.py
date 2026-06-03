"""[PRD-MODE-CAPSULE-V1] 远程运行验收测试：
A) 后端 API 回归测试 —— 在 backend 容器内运行（仅 API 用例）
B) 前端源码静态断言 —— 在 host 上用临时 python 容器挂载项目目录运行（文件读取断言）
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
TESTFILE = "backend/tests/test_ai_home_mode_capsule_v1_20260531.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)


def run(cmd, timeout=900):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


# ---- A: 后端 API 回归（容器内，只跑 API 用例） ----
print("===== A) backend API regression (in container) =====")
# 把最新测试文件拷进容器
run(f"docker cp {PROJ}/{TESTFILE} {DEPLOY_ID}-backend:/app/tests/test_ai_home_mode_capsule_v1_20260531.py")
inner_a = (
    "cd /app && pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -3 && "
    "python -m pytest tests/test_ai_home_mode_capsule_v1_20260531.py "
    "-k 'mode_preference_api_still_works' -v --tb=short 2>&1 | tail -40"
)
cmd_a = f'docker exec {DEPLOY_ID}-backend bash -lc {inner_a!r}'
rc_a, out_a, err_a = run(cmd_a)
print(out_a)
if err_a.strip():
    print("STDERR:", err_a[-2000:])
print("RC_A=", rc_a)

# ---- B: 前端源码静态断言（host 临时容器挂载项目目录） ----
print("\n===== B) frontend source assertions (host temp container) =====")
inner_b = (
    "pip install -q pytest 2>&1 | tail -2 && "
    "cd /proj && python -m pytest backend/tests/test_ai_home_mode_capsule_v1_20260531.py "
    "-k 'not mode_preference_api_still_works' -v --tb=short 2>&1 | tail -60"
)
cmd_b = (
    f"docker run --rm -v {PROJ}:/proj -w /proj python:3.12-slim "
    f"bash -lc {inner_b!r}"
)
rc_b, out_b, err_b = run(cmd_b)
print(out_b)
if err_b.strip():
    print("STDERR:", err_b[-2000:])
print("RC_B=", rc_b)

c.close()
print("\nSUMMARY: RC_A=", rc_a, "RC_B=", rc_b)
