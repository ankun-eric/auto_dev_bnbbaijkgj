"""在新构建的后端容器内运行回归测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd, timeout=300):
    print(f"$ {cmd}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    rc = out.channel.recv_exit_status()
    so = out.read().decode("utf-8", errors="replace")
    se = err.read().decode("utf-8", errors="replace")
    if so.strip():
        print(so)
    if se.strip():
        print(f"[stderr] {se}")
    return rc


# 检查容器内是否能看到新测试文件
print("--- 1) 检查容器内代码 ---")
run(
    f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    f"ls tests/test_button_intent_resolver_20260525.py 2>&1 || echo 'NOT FOUND'"
)

# 直接拷贝文件进容器
print("--- 2) 拷贝测试文件 + 已修改的业务文件进容器 ---")
run(
    f"docker cp {REMOTE_BASE}/backend/tests/test_button_intent_resolver_20260525.py "
    f"6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/tests/"
)
run(
    f"docker cp {REMOTE_BASE}/backend/app/services/button_intent_resolver.py "
    f"6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/app/services/"
)

# 运行回归
print("--- 3) 运行 pytest 回归 ---")
rc = run(
    f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    f"python -m pytest tests/test_button_intent_resolver_20260525.py "
    f"tests/test_report_auto_sync_20260524.py -v 2>&1 | tail -50",
    timeout=180,
)

# 完整健康验证
print("--- 4) 健康验证 ---")
run(
    f"curl -s 'https://{HOST}/autodev/{DEPLOY_ID}/api/health' | head -3"
)
run(
    f"curl -s -o /dev/null -w 'h5-home HTTP %{{http_code}}\\n' "
    f"'https://{HOST}/autodev/{DEPLOY_ID}/h5/ai-home/'"
)
run(
    f"curl -s -o /dev/null -w 'api-docs HTTP %{{http_code}}\\n' "
    f"'https://{HOST}/autodev/{DEPLOY_ID}/api/docs'"
)

c.close()
