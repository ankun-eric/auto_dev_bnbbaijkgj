"""
检查 /api/guardian/v13/family/list 502 的原因
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def sh(cmd, t=120):
    print(f"\n$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=t)
    rc = o.channel.recv_exit_status()
    print(o.read().decode("utf-8", "replace"))
    er = e.read().decode("utf-8", "replace")
    if er.strip():
        print("[stderr]", er)
    return rc


# 1) backend 容器日志最新 80 行
sh(f"cd {REMOTE_BASE} && docker compose logs --tail=120 backend")

# 2) 在容器内直接 curl 该接口（绕过 nginx）
sh(
    f"cd {REMOTE_BASE} && docker compose exec -T backend "
    "curl -s -o /tmp/r.txt -w 'HTTP %{http_code}\\n' http://localhost:8000/api/guardian/v13/family/list "
    "&& docker compose exec -T backend cat /tmp/r.txt | head -100"
)

# 3) 再用 token 一类的 hello health 来对比
sh(
    f"cd {REMOTE_BASE} && docker compose exec -T backend "
    "curl -s -o /dev/null -w 'health=%{http_code}\\n' http://localhost:8000/api/health"
)

c.close()
