"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] H5 重新构建 + 验证可访问性"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PD = f"/home/ubuntu/{DEPLOY_ID}"
BE = f"{DEPLOY_ID}-backend"


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=60,
            look_for_keys=False, allow_agent=False)


def run(cmd, sudo=False, timeout=600):
    full = cmd
    if sudo:
        full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}"
    print(f"\n$ {cmd[:240]}")
    _, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:])
    if err.strip():
        print(f"[err] {err[-1500:]}")
    print(f"[rc={rc}]")
    return rc, out, err


# 1. 检查 docker-compose 文件
run(f"ls {PD}/docker-compose*.yml")

# 2. 找 h5 容器
run(f"docker ps --format '{{{{.Names}}}}' | grep h5 || true")

# 3. h5-web 重新构建
run(f"cd {PD} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -25", timeout=1500)

# 4. 启动
run(f"cd {PD} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

# 5. backend 上次可能被重启，再次检查 + 重传
time.sleep(3)
LOCAL_BACKEND_FILES = [
    ("/app/app/api/guardian_bugfix_v1.py", f"{PD}/backend/app/api/guardian_bugfix_v1.py"),
    ("/app/app/api/family_management.py", f"{PD}/backend/app/api/family_management.py"),
    ("/app/app/api/family.py", f"{PD}/backend/app/api/family.py"),
    ("/app/app/api/guardian_system_v13.py", f"{PD}/backend/app/api/guardian_system_v13.py"),
    ("/app/app/services/schema_sync.py", f"{PD}/backend/app/services/schema_sync.py"),
    ("/app/app/main.py", f"{PD}/backend/app/main.py"),
    ("/app/app/models/models.py", f"{PD}/backend/app/models/models.py"),
]
for ct, host in LOCAL_BACKEND_FILES:
    run(f"docker cp {host} {BE}:{ct}", timeout=60)
run(f"docker restart {BE}")
time.sleep(8)

# 等待 backend ready
for i in range(20):
    rc, out, _ = cli.exec_command(
        f"docker exec {BE} python -c \"import urllib.request;"
        f"r=urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2);print(r.read())\""
        , timeout=10)[1].channel, "", ""
    # Use proper exec
    _, stdout, _ = cli.exec_command(
        f"docker exec {BE} python -c \"import urllib.request;"
        f"r=urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2);print(r.read())\"",
        timeout=10)
    o = stdout.read().decode(errors="replace")
    if "ok" in o:
        print(f"[+] backend ready: {o[:120]}")
        break
    print(f"[poll {i}] {o[:60]}")
    time.sleep(2)

# 6. 简单 smoke 测试
base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
print("\n=== smoke ===")
for path, label in [
    ("/api/health", "be health"),
    ("/health-profile/i-guard/", "H5 我守护的人"),
    ("/api/family/members", "API family members (期望 401)"),
    ("/api/guardian/v13/family/list", "API family list v13 (期望 401)"),
]:
    run(f"curl -sk -o /dev/null -w '{label} {path} -> %{{http_code}}\\n' --max-time 15 {base}{path}",
        timeout=30)

cli.close()
print("\n=== H5 REBUILD DONE ===")
