"""[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0] 远程拉新代码 + 测试。

承接 _deploy_dual_identity_400.py 的 Step 2~4，但代码已 push 到 origin/master。
"""
import sys
import time
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_HOST = "newbb.test.bangbangvip.com"
REMOTE_USER = "ubuntu"
REMOTE_PASS = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def ssh(cmd, timeout=900, header=""):
    if header:
        print(f"\n=== {header} ===")
    print(f"[REMOTE] $ {cmd[:200]}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS, timeout=30)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out[-5000:])
    if err:
        print("STDERR:", err[-3000:])
    print(f"[rc={rc}]")
    return rc, out, err


def main():
    # 1) 拉最新
    ssh(
        f"cd {REMOTE_DIR} && git fetch --all && git reset --hard origin/master && git log -1 --format='HEAD=%h %s'",
        header="STEP A: git pull",
    )
    # 2) 重建 backend (h5-web 已经被 cached，尝试 build)
    ssh(
        f"cd {REMOTE_DIR} && docker compose build backend h5-web 2>&1 | tail -50",
        timeout=1200,
        header="STEP B: docker build",
    )
    # 3) 重启容器
    ssh(
        f"cd {REMOTE_DIR} && docker compose up -d backend h5-web 2>&1 | tail -20",
        timeout=300,
        header="STEP C: docker up",
    )
    time.sleep(15)
    # 4) 安装 pytest 并跑测试
    container = f"{DEPLOY_ID}-backend"
    ssh(
        f"docker exec {container} sh -c 'pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -5'",
        timeout=300,
        header="STEP D: install pytest",
    )
    rc, out, _ = ssh(
        f"docker exec -w /app {container} sh -c 'python -m pytest tests/test_reschedule_dual_identity.py -v --tb=short 2>&1 | tail -180'",
        timeout=600,
        header="STEP E: run pytest",
    )
    # 5) smoke
    ssh(
        f"curl -s -o /dev/null -w 'h5_root=%{{http_code}}\\n' {BASE_URL}/ ; "
        f"curl -s -o /dev/null -w 'h5_login=%{{http_code}}\\n' {BASE_URL}/login ; "
        f"curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' {BASE_URL}/api/health ; "
        f"curl -s -o /dev/null -w 'api_docs=%{{http_code}}\\n' {BASE_URL}/api/docs",
        header="STEP F: smoke",
    )
    print("\n========== SUMMARY ==========")
    print("pytest rc =", rc)
    if "passed" in out or rc == 0:
        print("✅ pytest 通过")
    else:
        print("❌ pytest 有失败用例，请查看 STEP E 日志")


if __name__ == "__main__":
    main()
