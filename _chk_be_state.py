"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] 检查后端容器状态和可用工具"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{DEPLOY_ID}-backend"


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, sudo=False, timeout=60):
    full = cmd
    if sudo:
        full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}"
    print(f"\n$ {cmd[:200]}")
    _, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f"[err] {err[-1000:]}")
    print(f"[rc={rc}]")
    return rc, out, err


cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=60,
            look_for_keys=False, allow_agent=False)

# 容器内文件检查
run(cli, f"docker exec {BE} sh -c 'ls -la /app/app/api/guardian_bugfix_v1.py /app/tests/test_guardian_bugfix_v1_20260529.py 2>&1'")

# 启动状态
run(cli, f"docker logs --tail 80 {BE}")

# 容器内可用工具
run(cli, f"docker exec {BE} sh -c 'which curl wget python pip; pip list 2>&1 | grep -i -E \"pytest|httpx|sqlalchemy\"'")

# 用 python 检查 health
run(cli, f"docker exec {BE} python -c \"import urllib.request,sys;"
        f"r=urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3);"
        f"print(r.status, r.read()[:300])\"")

# 直接挂载主机文件试运行 import
run(cli, f"docker exec {BE} python -c 'from app.api import guardian_bugfix_v1; print(guardian_bugfix_v1.router.routes[:3])'")

cli.close()
