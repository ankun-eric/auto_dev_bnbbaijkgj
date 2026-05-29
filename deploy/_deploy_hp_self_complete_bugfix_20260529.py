#!/usr/bin/env python3
"""[BUG_FIX 2026-05-29] 健康档案·本人资料完善弹窗误弹 与 旧用户兼容 部署脚本

涉及文件：
- backend/app/api/health_profile_self.py（新增 _compute_missing_fields_v2 / _serialize_profile_v2，GET/PUT 改用 v2）
- backend/migrations/20260529_backfill_self_profile.py（新增；旧用户数据回填）
- backend/tests/test_health_profile_self_complete_v1.py（新增 8 条 BUG_FIX 测试）
- h5-web/src/app/health-profile/page.tsx（sessionStorage 防重弹 + 24h snooze + 完善成功立即关闭）
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


def run(ssh, cmd, timeout=900, check=False):
    print(f"\n>>> {cmd[:240]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-6000:])
    if err:
        print(f"STDERR: {err[-3000:]}")
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

    print("\n========== 1) 上传修改与新增文件 ==========")
    files = [
        ('backend/app/api/health_profile_self.py',
         f'{PROJECT_DIR}/backend/app/api/health_profile_self.py'),
        ('backend/migrations/20260529_backfill_self_profile.py',
         f'{PROJECT_DIR}/backend/migrations/20260529_backfill_self_profile.py'),
        ('backend/tests/test_health_profile_self_complete_v1.py',
         f'{PROJECT_DIR}/backend/tests/test_health_profile_self_complete_v1.py'),
        ('h5-web/src/app/health-profile/page.tsx',
         f'{PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx'),
    ]
    for local_rel, remote in files:
        local_full = os.path.join(LOCAL_ROOT, local_rel.replace('/', os.sep))
        if not os.path.exists(local_full):
            raise FileNotFoundError(local_full)
        upload_file(sftp, local_full, remote)

    print("\n========== 2) 热部署后端代码 ==========")
    run(ssh, f'docker cp {PROJECT_DIR}/backend/app/api/health_profile_self.py '
             f'{DEPLOY_ID}-backend:/app/app/api/health_profile_self.py', check=True)
    run(ssh, f'docker exec {DEPLOY_ID}-backend mkdir -p /app/migrations', check=False)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/migrations/20260529_backfill_self_profile.py '
             f'{DEPLOY_ID}-backend:/app/migrations/20260529_backfill_self_profile.py', check=True)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/tests/test_health_profile_self_complete_v1.py '
             f'{DEPLOY_ID}-backend:/app/tests/test_health_profile_self_complete_v1.py', check=False)
    run(ssh, f'docker restart {DEPLOY_ID}-backend', check=True)

    print("\n========== 3) 等待 backend 启动 ==========")
    for i in range(30):
        out, _, _ = run(ssh, f'docker logs --tail 8 {DEPLOY_ID}-backend 2>&1 | tail -8')
        if 'Application startup complete' in out or 'Uvicorn running' in out:
            break
        time.sleep(2)

    print("\n========== 4) 执行旧用户数据回填迁移（幂等） ==========")
    run(ssh, f'docker exec {DEPLOY_ID}-backend python /app/migrations/20260529_backfill_self_profile.py 2>&1 | tail -20')

    print("\n========== 5) 重建 H5 容器（使用最新 page.tsx） ==========")
    run(ssh, f'cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -50', timeout=1800)
    run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10')

    print("\n========== 6) 健康检查 ==========")
    time.sleep(8)
    base = f'http://localhost/autodev/{DEPLOY_ID}'
    run(ssh, f'curl -s -o /dev/null -w "/health-profile -> %{{http_code}}\\n" {base}/health-profile')
    run(ssh, f'curl -s -o /dev/null -w "/api/health-profile/self -> %{{http_code}}\\n" {base}/api/health-profile/self')

    print("\n========== 7) 在容器内运行 BUG_FIX 测试 ==========")
    test_cmd = (
        f'docker exec {DEPLOY_ID}-backend bash -lc '
        f'"cd /app && python -m pytest tests/test_health_profile_self_complete_v1.py -v --tb=short 2>&1 | tail -120"'
    )
    out, err, code = run(ssh, test_cmd, timeout=600)
    print(f"\n[pytest exit={code}]")

    ssh.close()


if __name__ == '__main__':
    main()
