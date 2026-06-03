"""[BUGFIX-HEALTH-PROFILE-CLIENT-CRASH 2026-05-29] 部署健康档案 TDZ 修复"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def get_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(cmd, timeout=600):
    c = get_client()
    try:
        print(f"$ {cmd[:200]}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        tail = "\n".join((out + ("\n[err]\n" + err if err.strip() else "")).splitlines()[-60:])
        print(tail)
        print(f"exit={rc}")
        return rc, out
    finally:
        c.close()


def put(local, remote):
    c = get_client()
    try:
        sftp = c.open_sftp()
        sftp.put(local, remote)
        sftp.close()
        print(f"  uploaded: {local} -> {remote}")
    finally:
        c.close()


print("\n[1] 上传修复后的 page.tsx")
put(
    "h5-web/src/app/health-profile/page.tsx",
    f"{REMOTE_PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx",
)

print("\n[2] 远程确认文件大小")
run(f"wc -c {REMOTE_PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx")

print("\n[3] 重建 h5 镜像")
# 找 docker-compose 真实服务名
rc, out = run(
    f"cd {REMOTE_PROJECT_DIR} && (test -f docker-compose.yml && docker compose config --services || ls *.yml)"
)
print(f"services: {out}")

print("\n[4] docker compose build h5")
# 由 docker ps 看，容器名是 6b099ed3-7175-4a78-91f4-44570c84ed27-h5，对应 service 是 h5
rc, _ = run(
    f"cd {REMOTE_PROJECT_DIR} && docker compose build h5 2>&1 | tail -50",
    timeout=1800,
)
if rc != 0:
    print("build failed — 尝试 service 'h5-web'")
    rc, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -50",
        timeout=1800,
    )

print("\n[5] 启动 h5")
run(
    f"cd {REMOTE_PROJECT_DIR} && (docker compose up -d h5 2>&1 || docker compose up -d h5-web 2>&1) | tail -20",
    timeout=180,
)

print("\n[6] 等待 h5 启动 (Next standalone)")
for i in range(30):
    time.sleep(3)
    rc, out = run(f"docker logs --tail=20 {DEPLOY_ID}-h5 2>&1", timeout=15)
    if "Ready in" in out or "Local:" in out or "ready started server" in out or "started server on" in out:
        print(f"    h5 ready @ {(i + 1) * 3}s")
        break

print("\n[7] 验证页面")
run(
    f"curl -sk -o /tmp/r.html -w 'health-profile → %{{http_code}}\\n' "
    f"'https://{HOST}/autodev/{DEPLOY_ID}/health-profile/'"
)
print("\n[8] 抓取新 page chunk 文件名")
run(
    f"curl -sk 'https://{HOST}/autodev/{DEPLOY_ID}/health-profile/' "
    f"| grep -oE '/_next/static/chunks/app/health-profile/page-[a-f0-9]+\\.js' | head -1"
)
