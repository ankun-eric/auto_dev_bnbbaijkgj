#!/usr/bin/env python3
"""检查线上后端运行的代码版本"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
BACKEND_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)
    print("[OK] SSH 连接成功\n")

    # 检查线上 family_management.py 中合并预览部分的代码
    out, err = run(f"docker exec {BACKEND_CONTAINER} sh -c \"sed -n '366,398p' /app/app/api/family_management.py\" 2>&1")
    print("=== 线上 family_management.py 第366-398行 ===")
    print(out)
    if err:
        print(f"stderr: {err}")

    # 也看看 scalar_one_or_none 是否还在用
    out, err = run(f"docker exec {BACKEND_CONTAINER} sh -c \"grep -n 'scalar_one_or_none\|scalars().first()' /app/app/api/family_management.py\" 2>&1")
    print("=== 线上 scalar_one_or_none / scalars().first() 使用情况 ===")
    print(out)

finally:
    client.close()
    print("[OK] SSH 已断开")
