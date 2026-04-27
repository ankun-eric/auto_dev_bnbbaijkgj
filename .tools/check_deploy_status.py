"""快速检查服务器当前部署状态：
- git HEAD commit
- 容器运行状态
- 关键 URL 可达性
- 后端是否含 4 角色统一治理代码（/api/merchant/profile 唯一性 + ROLE_NAME_MAP）
"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c


def run(c, cmd, timeout=120):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print("stderr:", err[-1500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def main():
    c = ssh()
    try:
        run(c, f"cd {PROJECT_DIR} && git log -3 --oneline 2>&1 || echo NO_GIT")
        run(c, f"cd {PROJECT_DIR} && git rev-parse HEAD 2>&1 || echo NO_GIT")
        run(c, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID} || echo NO_CONTAINERS")
        run(c, f"docker exec {DEPLOY_ID}-backend grep -n ROLE_NAME_MAP /app/app/api/account_security.py 2>&1 | head -5 || echo BACKEND_OLD")
        run(c, f"docker exec {DEPLOY_ID}-backend grep -n '4 角色统一' /app/app/api/admin_merchant.py 2>&1 | head -5 || echo BACKEND_OLD")
        run(c, f"docker exec {DEPLOY_ID}-backend grep -n '老 GET /api/merchant/profile' /app/app/api/merchant.py 2>&1 | head -5 || echo OLD_PROFILE_STILL_THERE")
        for path in ["/", "/admin/", "/merchant", "/merchant/staff", "/api/health"]:
            run(c, f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 '{BASE_URL}{path}' && echo")
    finally:
        c.close()


if __name__ == "__main__":
    main()
