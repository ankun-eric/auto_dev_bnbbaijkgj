#!/usr/bin/env python3
"""[BUGFIX-MY-GUARDIAN-CARD-2-20260528] 5 项优化部署 + 服务器测试

步骤：
1) SSH 上传修改后的后端 + 测试 + 脏数据脚本 + H5 前端文件
2) docker cp 热替后端源码 + restart
3) 容器内跑脏数据清理脚本
4) 容器内跑 pytest 新测试
5) 重建 H5 容器（含前端改动）
6) 健康检查
"""
import os
import sys
import time

import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{DEPLOY_ID}'
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
        ('backend/tests/test_my_guardian_card_bugfix2_20260528.py',
         f'{PROJECT_DIR}/backend/tests/test_my_guardian_card_bugfix2_20260528.py'),
        ('backend/scripts/cleanup_guardian_dirty_data_20260528.py',
         f'{PROJECT_DIR}/backend/scripts/cleanup_guardian_dirty_data_20260528.py'),
        ('h5-web/src/app/health-profile/i-guard/page.tsx',
         f'{PROJECT_DIR}/h5-web/src/app/health-profile/i-guard/page.tsx'),
    ]
    for local_rel, remote in files:
        local_full = os.path.join(LOCAL_ROOT, local_rel.replace('/', os.sep))
        if not os.path.exists(local_full):
            raise FileNotFoundError(local_full)
        upload_file(sftp, local_full, remote)

    print("\n========== 2) 热部署后端 ==========")
    run(ssh, f'docker cp {PROJECT_DIR}/backend/app/api/guardian_system_v13.py {DEPLOY_ID}-backend:/app/app/api/guardian_system_v13.py', check=True)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/tests/test_my_guardian_card_bugfix2_20260528.py {DEPLOY_ID}-backend:/app/tests/test_my_guardian_card_bugfix2_20260528.py', check=True)
    # 脏数据脚本放进容器 /app/scripts/
    run(ssh, f'docker exec {DEPLOY_ID}-backend mkdir -p /app/scripts', check=False)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/scripts/cleanup_guardian_dirty_data_20260528.py {DEPLOY_ID}-backend:/app/scripts/cleanup_guardian_dirty_data_20260528.py', check=True)
    run(ssh, f'docker restart {DEPLOY_ID}-backend', check=True)

    print("\n========== 3) 等待 backend 启动 ==========")
    for i in range(30):
        out, _, _ = run(ssh, f'docker logs --tail 5 {DEPLOY_ID}-backend 2>&1 | tail -5')
        if 'Application startup complete' in out or 'Uvicorn running' in out:
            break
        time.sleep(2)

    print("\n========== 4) 跑脏数据清理脚本 ==========")
    run(ssh, f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && python scripts/cleanup_guardian_dirty_data_20260528.py 2>&1 | tail -40"', timeout=180)

    print("\n========== 5) 容器内跑 pytest ==========")
    out, err, code = run(
        ssh,
        f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && python -m pytest tests/test_my_guardian_card_bugfix2_20260528.py -v --tb=short 2>&1 | tail -150"',
        timeout=420,
    )
    pytest_passed = (code == 0 and ' passed' in out and ' failed' not in out)

    print("\n========== 6) 重建 H5 容器 ==========")
    run(ssh, f'cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -40', timeout=1200)
    run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10')

    print("\n========== 7) 健康检查 ==========")
    time.sleep(5)
    run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" http://localhost/autodev/{DEPLOY_ID}/api/guardian/v13/family/list')
    run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" http://localhost/autodev/{DEPLOY_ID}/health-profile/i-guard')

    ssh.close()

    print("\n========== 部署结果 ==========")
    print(f"pytest passed: {pytest_passed}")
    if not pytest_passed:
        print("⚠️ pytest 未全部通过，请查看上方输出")
        sys.exit(1)


if __name__ == '__main__':
    main()
