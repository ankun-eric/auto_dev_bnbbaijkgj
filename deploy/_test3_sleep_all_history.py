"""在远程宿主机的项目 backend 目录直接跑测试（非容器内），以便访问 h5-web 源码。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"


def run(cmd, timeout=600):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASSWORD, timeout=30)
    try:
        _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        c.close()


# 把 backend tests 文件挂载到 backend 容器进行测试，但通过 -v 把宿主机 h5-web 挂载进容器
# 简单方案：直接在容器内创建 h5-web 软链或 cp，或者用 docker exec 时挂载
# 最简单：从宿主机 cat 把源码读出来，复制到容器内 /app/h5-web
print("=== 1. 把 h5-web 源码 cp 到 backend 容器中 ===")
backend = f"{DEPLOY_ID}-backend"
cmd = (
    f"docker exec {backend} sh -c 'mkdir -p /app/h5-web && rm -rf /app/h5-web/src 2>/dev/null; "
    f"mkdir -p /app/miniprogram/pages/health-metric' 2>&1 && "
    f"docker cp {PROJ}/h5-web/src {backend}:/app/h5-web/ 2>&1 && "
    f"docker cp {PROJ}/miniprogram/pages/health-metric {backend}:/app/miniprogram/pages/ 2>&1 && "
    f"echo COPIED"
)
code, out, err = run(cmd, timeout=120)
print(f"EXIT {code}")
print(out[-2000:])
if err:
    print("STDERR:", err[-500:])

print("\n=== 2. 跑两个测试文件 ===")
cmd = (
    f"docker exec {backend} sh -c 'cd /app && python -m pytest "
    "tests/test_sleep_all_history_fix_v1_20260602.py "
    "tests/test_metric_history_row_noaction_v1_20260602.py "
    "-v --tb=short --color=no 2>&1' "
)
code, out, err = run(cmd, timeout=600)
print(f"EXIT {code}")
print(out[-6000:])
if err:
    print("STDERR:", err[-500:])
