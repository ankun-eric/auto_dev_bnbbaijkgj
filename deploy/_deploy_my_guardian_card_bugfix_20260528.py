#!/usr/bin/env python3
"""[BUGFIX-MY-GUARDIAN-CARD-20260528] 部署 + 服务器测试

步骤：
1) SSH 连接服务器
2) 上传修改后的后端文件 + 测试文件 + H5 前端文件
3) 重建 backend 与 h5 容器
4) 在 backend 容器内运行 pytest 测试新增的 bug 修复用例
5) 验证 /api/guardian/v13/family/list 返回字段（健康检查）
"""
import os
import sys
import time
from io import BytesIO

import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
LOCAL_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))


def get_ssh():
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return s


def run(ssh, cmd, timeout=600, check=False):
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print(f"STDERR: {err[-2000:]}")
    print(f"[exit={code}]")
    if check and code != 0:
        raise RuntimeError(f"command failed: {cmd}\n{err}")
    return out, err, code


def upload_file(sftp, local_path, remote_path):
    print(f"  upload {local_path} -> {remote_path}")
    remote_dir = remote_path.rsplit('/', 1)[0]
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        # 不递归创建，逐级
        parts = remote_dir.strip('/').split('/')
        cur = ''
        for p in parts:
            cur += '/' + p
            try:
                sftp.stat(cur)
            except FileNotFoundError:
                sftp.mkdir(cur)
    sftp.put(local_path, remote_path)


def main():
    ssh = get_ssh()
    sftp = ssh.open_sftp()

    print("\n========== 1) 上传修改后的文件 ==========")
    files = [
        ('backend/app/api/guardian_system_v13.py',
         f'{PROJECT_DIR}/backend/app/api/guardian_system_v13.py'),
        ('backend/tests/test_my_guardian_card_bugfix_20260528.py',
         f'{PROJECT_DIR}/backend/tests/test_my_guardian_card_bugfix_20260528.py'),
        ('h5-web/src/app/health-profile/page.tsx',
         f'{PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx'),
    ]
    for local_rel, remote in files:
        local_full = os.path.join(LOCAL_ROOT, local_rel.replace('/', os.sep))
        if not os.path.exists(local_full):
            raise FileNotFoundError(local_full)
        upload_file(sftp, local_full, remote)

    print("\n========== 2) 重建 backend 容器（仅复制源码热加载） ==========")
    # 先看后端容器是用 volume mount 源码还是 COPY
    run(ssh, f'docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format "{{{{json .Mounts}}}}" | head -c 1000')

    # 一次性热部署：把代码文件 cp 到容器内 + restart
    run(ssh, f'docker cp {PROJECT_DIR}/backend/app/api/guardian_system_v13.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/app/api/guardian_system_v13.py', check=True)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/tests/test_my_guardian_card_bugfix_20260528.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/tests/test_my_guardian_card_bugfix_20260528.py', check=True)
    run(ssh, 'docker restart 6b099ed3-7175-4a78-91f4-44570c84ed27-backend', check=True)

    print("\n========== 3) 等待 backend 启动 ==========")
    for i in range(30):
        out, _, _ = run(ssh, 'docker logs --tail 5 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -5')
        if 'Application startup complete' in out or 'Uvicorn running' in out:
            break
        time.sleep(2)

    print("\n========== 4) 在 backend 容器内跑 pytest ==========")
    out, err, code = run(
        ssh,
        'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "cd /app && python -m pytest tests/test_my_guardian_card_bugfix_20260528.py -v -x --tb=short 2>&1 | tail -120"',
        timeout=420,
    )
    pytest_passed = (code == 0 and ' passed' in out and 'failed' not in out.lower().replace('0 failed', ''))

    print("\n========== 5) 重建 H5 容器（前端） ==========")
    # 先把 page.tsx 上传到 host，然后通过 docker compose 重建 h5
    run(ssh, f'cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -40', timeout=900)
    run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10')

    print("\n========== 6) 健康检查 ==========")
    time.sleep(5)
    # 探测后端 /family/list（需要鉴权但路径存在）
    run(ssh, 'curl -s -o /dev/null -w "%{http_code}\\n" http://localhost/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/guardian/v13/family/list')
    # H5 健康
    run(ssh, 'curl -s -o /dev/null -w "%{http_code}\\n" http://localhost/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile')

    ssh.close()

    print("\n========== 部署结果 ==========")
    print(f"pytest passed: {pytest_passed}")
    if not pytest_passed:
        print("⚠️ pytest 未全部通过，请查看上方输出")
        sys.exit(1)


if __name__ == '__main__':
    main()
