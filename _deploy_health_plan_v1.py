"""
[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02]
增量部署：同步后端 + h5 改动 + 小程序产物，rebuild backend 与 h5。
"""
import os, sys, tarfile, io, time
import paramiko

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR=f"/home/ubuntu/{DEPLOY_ID}"

# 本次涉及的后端 + h5 + 小程序文件
PATHS = [
    # backend
    "backend/app/api/health_plan_v2.py",
    "backend/app/api/admin_health_plan.py",
    "backend/app/models/models.py",
    "backend/app/schemas/health_plan_v2.py",
    "backend/app/services/schema_sync.py",
    # h5
    "h5-web/src/app/health-plan/page.tsx",
    "h5-web/src/app/health-plan/checkin/page.tsx",
    "h5-web/src/app/health-plan/edit/page.tsx",
    "h5-web/src/app/health-plan/result/page.tsx",
]

def make_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in PATHS:
            if os.path.exists(p):
                tf.add(p, arcname=p)
            else:
                print(f"!! missing local: {p}")
    return buf.getvalue()

def main():
    print("[*] packaging...")
    data = make_tar()
    print(f"    tar size: {len(data)} bytes")

    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = c.open_sftp()
    remote_tar = f"/tmp/health_plan_v1_{int(time.time())}.tar.gz"
    with sftp.open(remote_tar, "wb") as f:
        f.write(data)
    sftp.close()
    print(f"[*] uploaded -> {remote_tar}")

    def run(cmd, timeout=600):
        print(f"$ {cmd}")
        si,so,se = c.exec_command(cmd, timeout=timeout, get_pty=False)
        out, err = b"", b""
        for line in iter(so.readline, ""):
            print(line, end="")
            out += line.encode()
            if not line:
                break
        rc = so.channel.recv_exit_status()
        err = se.read().decode("utf-8", "ignore")
        if err: print("[err]", err)
        print(f"[rc={rc}]")
        return rc, out.decode("utf-8","ignore"), err

    # 1. 解包
    run(f"cd {REMOTE_DIR} && tar -xzf {remote_tar} && echo UNPACKED_OK")

    # 2. 重建 backend（代码变更）
    run(f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -20", timeout=900)
    run(f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

    # 3. 重建 h5
    run(f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -20", timeout=900)
    run(f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

    # 4. 等待 backend 健康
    time.sleep(8)
    run(f"docker logs {DEPLOY_ID}-backend --tail 40 2>&1 | tail -40")

    # 5. 路由探测
    BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    for path in [
        "/api/health/ping",
        "/api/openapi.json",
        "/health-plan",
        "/health-plan/edit",
        "/health-plan/result",
        "/health-plan/checkin",
    ]:
        url = BASE + path
        run(f"curl -s -o /dev/null -w 'HTTP %{{http_code}}  %{{size_download}}B  {path}\\n' --max-time 15 '{url}'")

    c.close()
    print("[DONE]")

if __name__ == "__main__":
    main()
