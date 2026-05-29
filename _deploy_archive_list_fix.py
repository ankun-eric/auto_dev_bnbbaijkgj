"""[PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 部署 H5 修复

把 5 个修改的源文件传到远程，重建 h5-web 容器，然后做冒烟测试。
仅 H5 端有变更，后端/admin/db 不动。
"""
import io
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 5 个修改的源文件（路径相对项目根）
FILES = [
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/app/health-profile/i-guard/page.tsx",
    "h5-web/src/app/health-profile/archive-list/page.tsx",
    "h5-web/src/app/member-center/page.tsx",
    "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
]


def get_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(client, cmd, timeout=600):
    print(f"$ {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out, end="", flush=True)
    if err:
        print(f"[stderr] {err}", end="", flush=True)
    print(f"[rc={rc}]", flush=True)
    return rc, out, err


def upload(client, local_rel):
    local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
    remote = f"{REMOTE_ROOT}/{local_rel}"
    sftp = client.open_sftp()
    try:
        # ensure remote dir exists
        d = os.path.dirname(remote)
        rc, _, _ = run(client, f"mkdir -p {d}")
        sftp.put(local, remote)
        print(f"  uploaded {local_rel} ({os.path.getsize(local)} bytes)", flush=True)
    finally:
        sftp.close()


def main():
    c = get_client()
    try:
        # 1) upload 5 files
        for f in FILES:
            upload(c, f)

        # 2) rebuild h5-web container
        print("\n=== Rebuilding h5-web container ===", flush=True)
        rc, out, err = run(
            c,
            f"cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -50",
            timeout=900,
        )
        if rc != 0:
            print("h5 build failed", flush=True)
            sys.exit(rc)

        # 3) restart h5-web
        print("\n=== Restarting h5-web ===", flush=True)
        rc, _, _ = run(
            c,
            f"cd {REMOTE_ROOT} && docker compose up -d h5-web 2>&1 | tail -20",
            timeout=180,
        )
        if rc != 0:
            sys.exit(rc)

        # 4) wait for healthy
        print("\n=== Waiting for h5 to be ready ===", flush=True)
        for i in range(30):
            time.sleep(2)
            rc, out, _ = run(
                c,
                f"docker exec {DEPLOY_ID}-h5 wget -q -O- http://localhost:3000/autodev/{DEPLOY_ID}/ 2>&1 | head -1 || echo NOT_READY",
                timeout=15,
            )
            if "NOT_READY" not in out and ("html" in out.lower() or "DOCTYPE" in out.upper()):
                print("h5 is ready", flush=True)
                break
        else:
            print("WARNING: h5 not ready after 60s", flush=True)

        print("\n=== Deploy complete ===", flush=True)
    finally:
        c.close()


if __name__ == "__main__":
    main()
