"""阶段 2-3 第二轮：先把最新代码部署进容器，再 pytest。

由于服务器 git fetch 失败（国内访问 GitHub 抽风），改用：
  1) 通过 SCP 把本地修复后的 backend/app/utils/rsa_key.py、payment_config.py、
     测试文件 rsync/scp 到服务器项目目录
  2) docker cp 文件到 backend 容器
  3) 容器内 pytest 测试 + restart 后端

实际上服务器上 rsa_key.py 已经包含 _wrap_pkcs1_pem，可能上一次部署就已生效；
本次先验证容器内文件是否与本地一致 + 跑 pytest（用绝对路径）。
"""
from __future__ import annotations

import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
CONTAINER = f"{DEPLOY_ID}-backend"


def ssh_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()

    # 1) 上传修复后的关键文件到服务器
    print("[1/4] 上传最新修复文件到服务器...")
    files = [
        ("backend/app/utils/rsa_key.py", "backend/app/utils/rsa_key.py"),
        ("backend/app/api/payment_config.py", "backend/app/api/payment_config.py"),
        ("backend/tests/test_alipay_private_key_format.py", "backend/tests/test_alipay_private_key_format.py"),
        ("backend/tests/test_payment_config_alipay_save_validation.py", "backend/tests/test_payment_config_alipay_save_validation.py"),
        ("backend/tests/test_payment_config_test_connection_error_message.py", "backend/tests/test_payment_config_test_connection_error_message.py"),
        ("admin-web/src/app/(admin)/payment-config/page.tsx", "admin-web/src/app/(admin)/payment-config/page.tsx"),
    ]
    for local_rel, remote_rel in files:
        remote_path = f"{PROJECT_DIR}/{remote_rel}"
        # 确保目录存在
        ssh_exec(client, f"mkdir -p $(dirname {remote_path})")
        try:
            sftp.put(local_rel, remote_path)
            print(f"   put {local_rel} -> {remote_path}")
        except Exception as e:
            print(f"   ERR put {local_rel}: {e}")

    # 2) 拷贝到容器内
    print("[2/4] 把代码拷贝到 backend 容器内...")
    container_files = [
        ("backend/app/utils/rsa_key.py", "/app/app/utils/rsa_key.py"),
        ("backend/app/api/payment_config.py", "/app/app/api/payment_config.py"),
        ("backend/tests/test_alipay_private_key_format.py", "/app/tests/test_alipay_private_key_format.py"),
        ("backend/tests/test_payment_config_alipay_save_validation.py", "/app/tests/test_payment_config_alipay_save_validation.py"),
        ("backend/tests/test_payment_config_test_connection_error_message.py", "/app/tests/test_payment_config_test_connection_error_message.py"),
    ]
    for host_rel, container_path in container_files:
        host_abs = f"{PROJECT_DIR}/{host_rel}"
        code, out, err = ssh_exec(
            client, f"docker cp {host_abs} {CONTAINER}:{container_path}"
        )
        print(f"   {'OK' if code == 0 else 'ERR'} docker cp {host_abs} -> {CONTAINER}:{container_path}")
        if err:
            print(f"      err: {err.strip()}")

    # 3) 重启后端容器以热加载
    print("[3/4] 重启 backend 容器...")
    code, out, err = ssh_exec(client, f"docker restart {CONTAINER}", timeout=60)
    print(f"   restart: rc={code}, out={out.strip()}")

    # 等待几秒让 Uvicorn 起来
    ssh_exec(client, "sleep 6")

    # 4) 容器内 pytest（先排查 tests 目录在哪里）
    print("[4/4] 容器内 pytest 验证...")
    _, out, _ = ssh_exec(
        client,
        f"docker exec {CONTAINER} bash -c 'ls /app && echo --- && ls /app/tests 2>/dev/null | head'",
    )
    print(f"   /app 内容：\n{out}")

    pytest_cmd = (
        f"docker exec {CONTAINER} bash -lc "
        f"'cd /app && python -m pytest -x "
        f"tests/test_alipay_private_key_format.py "
        f"tests/test_payment_config_alipay_save_validation.py "
        f"tests/test_payment_config_test_connection_error_message.py "
        f"-v 2>&1 | tail -80'"
    )
    code, out, err = ssh_exec(client, pytest_cmd, timeout=300)
    print(f"   pytest rc={code}")
    print(out)
    if err:
        print("STDERR:", err)

    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
