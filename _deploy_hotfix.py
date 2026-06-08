#!/usr/bin/env python3
"""热修复部署：替换 family_management.py 并重启后端"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)
    print("[OK] SSH 连接成功\n")

    # Step 1: 把修复后的文件传到服务器
    print("[1/4] 上传修复后的 family_management.py 到服务器...")
    sftp = client.open_sftp()
    sftp.put(
        "backend/app/api/family_management.py",
        f"{PROJECT_DIR}/backend/app/api/family_management.py"
    )
    sftp.close()
    print("  [OK] 文件已上传")

    # Step 2: 验证文件内容
    print("\n[2/4] 验证上传的文件...")
    out, err = run(f"grep -n 'scalars().first()' {PROJECT_DIR}/backend/app/api/family_management.py")
    print(f"  scalars().first() 出现位置:\n{out}")

    # Step 3: 把文件复制到容器内
    print("[3/4] 复制文件到容器并重启...")
    out, err = run(f"docker cp {PROJECT_DIR}/backend/app/api/family_management.py {BACKEND_CONTAINER}:/app/app/api/family_management.py")
    print(f"  docker cp: {out.strip() or 'OK'}")
    if err:
        print(f"  stderr: {err}")

    # Step 4: 重启后端容器
    out, err = run(f"docker restart {BACKEND_CONTAINER}")
    print(f"  docker restart: {out.strip() or 'OK'}")

    # 等待后端健康
    print("  等待后端启动...")
    for i in range(30):
        time.sleep(2)
        out, err = run(f"docker inspect {BACKEND_CONTAINER} --format '{{{{.State.Health.Status}}}}' 2>&1")
        status = out.strip()
        if status == "healthy":
            print(f"  [{i+1}] Backend: healthy!")
            break
        if i % 5 == 0:
            print(f"  [{i+1}] Backend: {status}")
    else:
        print("  WARNING: 后端健康检查超时")

    # 验证修复
    print("\n[4/4] 验证修复效果...")
    out, err = run(f"docker exec {BACKEND_CONTAINER} sh -c \"grep -n 'scalar_one_or_none\|scalars().first()' /app/app/api/family_management.py | grep -E ':(376|384|534|542):'\"")
    print(f"  关键行修复状态:\n{out}")

    # 测试接口
    print("\n  测试邀请接口...")
    out, err = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/api/family/invitation/695e3db0ab80 2>&1")
    print(f"  不带token: HTTP {out.strip()}")

    print("\n" + "=" * 60)
    print("热修复部署完成!")
    print("=" * 60)

finally:
    client.close()
    print("[OK] SSH 已断开")
