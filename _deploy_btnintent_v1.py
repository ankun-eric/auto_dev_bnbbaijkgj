"""
[BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525] 部署脚本
通过 paramiko 把本次修复的文件上传到远程服务器，并重启 backend + h5-web 容器。
"""

import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 本次修复涉及的文件清单：(本地路径, 远程路径)
FILES_TO_UPLOAD = [
    # 后端
    ("backend/app/services/button_intent_resolver.py",
     f"{REMOTE_BASE}/backend/app/services/button_intent_resolver.py"),
    ("backend/app/services/drug_identify_engine.py",
     f"{REMOTE_BASE}/backend/app/services/drug_identify_engine.py"),
    ("backend/app/schemas/chat.py",
     f"{REMOTE_BASE}/backend/app/schemas/chat.py"),
    ("backend/app/api/chat.py",
     f"{REMOTE_BASE}/backend/app/api/chat.py"),
    ("backend/tests/test_button_intent_resolver_20260525.py",
     f"{REMOTE_BASE}/backend/tests/test_button_intent_resolver_20260525.py"),
    # H5 前端
    ("h5-web/src/utils/button-intent.ts",
     f"{REMOTE_BASE}/h5-web/src/utils/button-intent.ts"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    # 小程序
    ("miniprogram/utils/buttonIntent.js",
     f"{REMOTE_BASE}/miniprogram/utils/buttonIntent.js"),
    ("miniprogram/pages/chat/index.js",
     f"{REMOTE_BASE}/miniprogram/pages/chat/index.js"),
]


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run(client, cmd, timeout=300, log=True):
    if log:
        print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if log:
        if out.strip():
            print(out)
        if err.strip():
            print(f"[stderr] {err}")
    return exit_status, out, err


def mkdir_p(sftp, path):
    parts = path.replace("\\", "/").split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = cur.rstrip("/") + "/" + p if cur else p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def upload_files(client):
    sftp = client.open_sftp()
    try:
        for local_rel, remote in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local):
                print(f"[SKIP missing] {local}")
                continue
            print(f"[UPLOAD] {local_rel} -> {remote}")
            mkdir_p(sftp, remote)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    print(f"[1/6] SSH 连接到 {HOST} ...")
    client = ssh_connect()

    print(f"[2/6] 检查远程项目目录 {REMOTE_BASE}")
    rc, out, err = run(client, f"ls -la {REMOTE_BASE} | head -30")
    if rc != 0:
        print("远程目录不存在，停止部署")
        sys.exit(1)

    print("[3/6] 上传本次修复涉及的文件 ...")
    upload_files(client)

    print("[4/6] 在远程执行后端 pytest 验证 ...")
    test_cmd = (
        f"cd {REMOTE_BASE} && "
        f"docker compose exec -T backend python -m pytest "
        f"tests/test_button_intent_resolver_20260525.py "
        f"tests/test_report_auto_sync_20260524.py -v 2>&1 | tail -60"
    )
    rc, out, err = run(client, test_cmd, timeout=300)

    print("[5/6] 重新构建并启动 backend + h5-web 容器 ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose build backend h5-web 2>&1 | tail -40",
        timeout=900,
    )
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose up -d backend h5-web 2>&1 | tail -20",
        timeout=300,
    )
    time.sleep(8)

    print("[6/6] 验证容器健康 ...")
    rc, out, err = run(client, f"cd {REMOTE_BASE} && docker compose ps")
    rc, out, err = run(
        client,
        f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/h5/ai-home",
    )
    rc, out, err = run(
        client,
        f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/api/health",
    )

    client.close()
    print("\n=== 部署完成 ===")


if __name__ == "__main__":
    main()
