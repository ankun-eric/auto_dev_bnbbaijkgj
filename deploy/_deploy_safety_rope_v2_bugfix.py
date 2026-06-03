"""[BUGFIX-SAFETY-ROPE-V1 2026-06-03] 数字安全绳 v2 锁死版部署脚本

本次仅改动：
- 后端：safety_rope_v1.py + 测试用例
- H5：care-safety-rope/page.tsx + care-home/page.tsx + care-ai-home/sos/page.tsx

部署流程：
1) SFTP 上传 5 个文件
2) docker compose build/up backend + h5-web
3) reload nginx
4) HTTPS 烟雾测试
5) 远程跑 pytest（如 backend 容器内 pytest 可用）
"""
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    ("backend/app/api/safety_rope_v1.py", "backend/app/api/safety_rope_v1.py"),
    ("backend/tests/test_safety_rope_v1_20260603.py", "backend/tests/test_safety_rope_v1_20260603.py"),
    ("h5-web/src/app/care-safety-rope/page.tsx", "h5-web/src/app/care-safety-rope/page.tsx"),
    ("h5-web/src/app/care-home/page.tsx", "h5-web/src/app/care-home/page.tsx"),
    ("h5-web/src/app/care-ai-home/sos/page.tsx", "h5-web/src/app/care-ai-home/sos/page.tsx"),
]


def sh(client, cmd, timeout=180, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    if out and not quiet:
        print(out[-3000:])
    if err and not quiet:
        print("STDERR:", err[-1500:])
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[1/6] Connect ssh://{USER}@{HOST}")
    client.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = client.open_sftp()
    print(f"[2/6] SFTP upload {len(FILES)} files → {PROJ}")
    for local_rel, remote_rel in FILES:
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", local_rel)
        local = os.path.normpath(local)
        remote = f"{PROJ}/{remote_rel}".replace("\\", "/")
        if not os.path.exists(local):
            print(f"  ! missing local: {local}")
            continue
        d = os.path.dirname(remote)
        sh(client, f"mkdir -p {d}", timeout=20, quiet=True)
        sftp.put(local, remote)
        print(f"  ✓ {local_rel}")
    sftp.close()

    print("\n[3/6] Build & up backend container")
    rc, out, _ = sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -30", timeout=600)
    if rc != 0:
        print("  ! backend build failed")
        sys.exit(1)
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps backend", timeout=180)

    print("\n[4/6] Build & up h5-web container (异步等待)")
    sh(client,
       f"bash -c 'cd {PROJ} && nohup docker compose -f docker-compose.prod.yml build --no-cache h5-web </dev/null > /tmp/h5_build_bugfix.log 2>&1 & disown' && echo STARTED",
       timeout=20)
    for i in range(60):
        time.sleep(15)
        rc, out, _ = sh(client, "tail -3 /tmp/h5_build_bugfix.log 2>/dev/null; pgrep -f 'docker compose.*build.*h5-web' >/dev/null && echo BUILDING || echo BUILD_DONE",
                        timeout=20, quiet=True)
        if "BUILD_DONE" in out:
            print(f"  H5 build done after {(i+1)*15}s")
            break
        if i % 4 == 0:
            print(f"  ...waiting H5 build, {(i+1)*15}s")
    else:
        print("  WARN: H5 build still running after 15min, continue anyway")
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate h5-web", timeout=180)

    print("\n[5/6] Reload nginx")
    time.sleep(8)
    sh(client, "docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload || true", timeout=30)

    print("\n[6/6] Smoke test")
    sh(client, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' {BASE_URL}/api/health")
    sh(client, f"curl -sk -o /dev/null -w 'sr_status_unauth=%{{http_code}}\\n' {BASE_URL}/api/safety-rope/status")
    sh(client, f"curl -sk -o /dev/null -w 'sr_check_phone_unauth=%{{http_code}}\\n' '{BASE_URL}/api/safety-rope/contacts/check-phone?phone=13700001111'")
    sh(client, f"curl -sk -o /dev/null -w 'h5_safety_rope=%{{http_code}}\\n' {BASE_URL}/care-safety-rope")
    sh(client, f"curl -sk -o /dev/null -w 'h5_care_home=%{{http_code}}\\n' {BASE_URL}/care-home")
    sh(client, f"curl -sk -o /dev/null -w 'h5_care_sos=%{{http_code}}\\n' {BASE_URL}/care-ai-home/sos")

    print("\n部署完成。")
    client.close()


if __name__ == "__main__":
    main()
