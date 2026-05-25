"""[Bug 修复 v1.2] 部署后验证：含 admin 登录的真实 UTF-8 + 新接口 + pytest"""
from __future__ import annotations
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def ssh_run(client, cmd, timeout=600, silent=False):
    if not silent:
        print(f"[ssh] $ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    if not silent:
        tail = "\n".join(combined.splitlines()[-80:])
        print(tail)
        print(f"[ssh] exit={rc}")
    return rc, combined


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        print("\n[1] admin 登录获取 token")
        rc, out = ssh_run(
            client,
            f"curl -sk -X POST '{BASE_URL}/api/admin/login' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"phone\":\"13800138000\",\"password\":\"admin123\"}}'",
            timeout=20,
        )

        print("\n[2] 提取 token 后调用 emergency-sources 验证 UTF-8 + 中文")
        ssh_run(
            client,
            f"TOKEN=$(curl -sk -X POST '{BASE_URL}/api/admin/login' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"phone\":\"13800138000\",\"password\":\"admin123\"}}' "
            f"| python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get(\"token\") or d.get(\"access_token\") or \"\")'); "
            f"echo \"token=$(echo $TOKEN | head -c 30)...\"; "
            f"echo '--- emergency-sources headers ---'; "
            f"curl -sk -i -H \"Authorization: Bearer $TOKEN\" -H 'Client-Type: admin-web' "
            f"'{BASE_URL}/api/admin/emergency-sources' | head -10; "
            f"echo '--- emergency-sources body (含中文校验) ---'; "
            f"curl -sk -H \"Authorization: Bearer $TOKEN\" -H 'Client-Type: admin-web' "
            f"'{BASE_URL}/api/admin/emergency-sources' | head -c 600; echo; "
            f"echo '--- family-management headers ---'; "
            f"curl -sk -i -H \"Authorization: Bearer $TOKEN\" -H 'Client-Type: admin-web' "
            f"'{BASE_URL}/api/admin/family-management' | head -10; "
            f"echo '--- family-management body ---'; "
            f"curl -sk -H \"Authorization: Bearer $TOKEN\" -H 'Client-Type: admin-web' "
            f"'{BASE_URL}/api/admin/family-management' | head -c 600; echo",
            timeout=30,
        )

        print("\n[3] 安装 pytest + 跑测试")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5",
            timeout=180,
        )
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_guardian_system_v12.py -v --tb=short 2>&1 | tail -80'",
            timeout=400,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
