"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1 2026-05-31] 部署脚本。

操作步骤：
1. 通过 SFTP 上传以下文件到服务器：
   - backend/app/api/health_metric_card_v1.py
   - backend/app/main.py (注册路由)
   - h5-web/src/app/health-metric/[type]/history/page.tsx (新增)
   - h5-web/src/app/health-metric/[type]/page.tsx (调整)
2. docker cp 到对应容器（backend & h5）
3. 重启 backend；重新构建 h5（可选 - 本次先 docker cp 走最快通道）
4. 验证 /api/health-metric-v1/meta 返回 200
"""
import os
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_BASE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

LOCAL_FILES_TO_PUSH = [
    # (本地路径, 服务器路径)
    ("backend/app/api/health_metric_card_v1.py",
     f"{REMOTE_BASE}/backend/app/api/health_metric_card_v1.py"),
    ("backend/app/main.py",
     f"{REMOTE_BASE}/backend/app/main.py"),
    ("backend/tests/test_health_metric_card_unify_v1_20260531.py",
     f"{REMOTE_BASE}/backend/tests/test_health_metric_card_unify_v1_20260531.py"),
    ("h5-web/src/app/health-metric/[type]/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/health-metric/[type]/page.tsx"),
    ("h5-web/src/app/health-metric/[type]/history/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/health-metric/[type]/history/page.tsx"),
]


def get_client():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    return cli


def upload_files(cli):
    sftp = cli.open_sftp()
    for local, remote in LOCAL_FILES_TO_PUSH:
        local_abs = os.path.abspath(local)
        if not os.path.exists(local_abs):
            print(f"[WARN] 本地文件不存在: {local_abs}")
            continue
        # 确保远端目录存在
        remote_dir = os.path.dirname(remote)
        cli.exec_command(f"mkdir -p '{remote_dir}'")
        time.sleep(0.2)
        print(f"[upload] {local} -> {remote}")
        sftp.put(local_abs, remote)
    sftp.close()


def run(cli, cmd, timeout=300):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main():
    print("[1/5] 连接服务器...")
    cli = get_client()
    print("[2/5] 上传新文件...")
    upload_files(cli)

    print("[3/5] docker cp 到 backend 容器...")
    cmds = [
        # backend 容器名
        "BC=$(docker ps -qf 'name=6b099ed3.*backend'); echo BC=$BC",
        f"BC=$(docker ps -qf 'name=6b099ed3.*backend'); "
        f"docker cp {REMOTE_BASE}/backend/app/api/health_metric_card_v1.py $BC:/app/app/api/health_metric_card_v1.py",
        f"BC=$(docker ps -qf 'name=6b099ed3.*backend'); "
        f"docker cp {REMOTE_BASE}/backend/app/main.py $BC:/app/app/main.py",
        # 重启 backend
        "BC=$(docker ps -qf 'name=6b099ed3.*backend'); docker restart $BC",
    ]
    for c in cmds:
        code, out, err = run(cli, c, timeout=120)
        print(f"[$ {c[:80]}...] code={code}")
        if out.strip():
            print("  stdout:", out.strip()[:300])
        if err.strip():
            print("  stderr:", err.strip()[:300])

    print("[4/5] 等 15s 服务启动...")
    time.sleep(15)

    print("[5/5] 验证 /api/health-metric-v1/meta...")
    for _ in range(4):
        code, out, err = run(
            cli,
            f"curl -sS -o /dev/null -w 'HTTP:%{{http_code}}' '{PROJECT_BASE_URL}/api/health-metric-v1/meta'",
            timeout=30,
        )
        print("verify ->", out.strip(), err.strip())
        if "HTTP:200" in out or "HTTP:401" in out:
            # 200=未鉴权也能返回 meta；或者 401=路由存在但需要鉴权
            break
        time.sleep(5)

    # 检查 backend 启动日志是否有报错
    print("\n[diag] backend 最近日志：")
    code, out, err = run(
        cli, "BC=$(docker ps -qf 'name=6b099ed3.*backend'); docker logs --tail 80 $BC 2>&1",
        timeout=30,
    )
    print(out[-2000:])

    cli.close()
    print("\n[DONE]")


if __name__ == "__main__":
    main()
