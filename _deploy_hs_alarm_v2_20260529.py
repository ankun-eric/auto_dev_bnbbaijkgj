#!/usr/bin/env python3
"""[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-V2 2026-05-29]
部署 + 服务器端测试脚本

涉及文件：
- backend/app/api/home_safety_v1.py（新增 PATCH /alarms/{id}/resolve）
- backend/tests/test_home_safety_alarm_resolve_v2_20260529.py（新增测试）
- h5-web/src/components/family/FamilyMemberTabs.tsx（Bug 3 重构）
- h5-web/src/app/home-safety/components/AlarmList.tsx（Bug 4 重构）
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
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


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
                try:
                    sftp.mkdir(cur)
                except Exception:
                    pass
    sftp.put(local_path, remote_path)


def main():
    ssh = get_ssh()
    sftp = ssh.open_sftp()

    print("\n========== 1) 上传修改与新增文件 ==========")
    files = [
        ('backend/app/api/home_safety_v1.py',
         f'{PROJECT_DIR}/backend/app/api/home_safety_v1.py'),
        ('backend/tests/test_home_safety_alarm_resolve_v2_20260529.py',
         f'{PROJECT_DIR}/backend/tests/test_home_safety_alarm_resolve_v2_20260529.py'),
        ('h5-web/src/components/family/FamilyMemberTabs.tsx',
         f'{PROJECT_DIR}/h5-web/src/components/family/FamilyMemberTabs.tsx'),
        ('h5-web/src/app/home-safety/components/AlarmList.tsx',
         f'{PROJECT_DIR}/h5-web/src/app/home-safety/components/AlarmList.tsx'),
    ]
    for local_rel, remote in files:
        local_full = os.path.join(LOCAL_ROOT, local_rel.replace('/', os.sep))
        if not os.path.exists(local_full):
            raise FileNotFoundError(local_full)
        upload_file(sftp, local_full, remote)

    print("\n========== 2) 热部署后端代码 ==========")
    run(ssh, f'docker cp {PROJECT_DIR}/backend/app/api/home_safety_v1.py '
             f'{DEPLOY_ID}-backend:/app/app/api/home_safety_v1.py', check=True)
    run(ssh, f'docker cp {PROJECT_DIR}/backend/tests/test_home_safety_alarm_resolve_v2_20260529.py '
             f'{DEPLOY_ID}-backend:/app/tests/test_home_safety_alarm_resolve_v2_20260529.py',
        check=False)
    run(ssh, f'docker restart {DEPLOY_ID}-backend', check=True)

    print("\n========== 3) 等待 backend 启动 ==========")
    for i in range(40):
        out, _, _ = run(ssh, f'docker logs --tail 10 {DEPLOY_ID}-backend 2>&1 | tail -10')
        if 'Application startup complete' in out or 'Uvicorn running' in out:
            print('backend 启动完毕')
            break
        time.sleep(2)

    print("\n========== 4) 服务器侧 pytest 自动化测试（非 UI） ==========")
    cmd = (
        f'docker exec {DEPLOY_ID}-backend bash -lc '
        f'"cd /app && python -m pytest -x -q '
        f'tests/test_home_safety_alarm_resolve_v2_20260529.py '
        f'tests/test_home_safety_remark_alarms_v1_20260529.py '
        f'--maxfail=5 --timeout=60 2>&1 | tail -120"'
    )
    out, err, code = run(ssh, cmd, timeout=600)
    test_ok = (code == 0) and 'passed' in out

    print("\n========== 5) 热替换 h5-web 静态产物（rebuild） ==========")
    # 在远端项目根目录里 docker compose 重新 build h5-web 然后 up -d
    # 由于 Next.js 是构建期注入 NEXT_PUBLIC_*，必须重新 build h5-web
    run(ssh, f'cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -50', timeout=1500)
    run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web', check=False)

    print("\n========== 6) 健康检查 ==========")
    run(ssh, f'docker ps --filter name={DEPLOY_ID} --format "table {{{{.Names}}}}\\t{{{{.Status}}}}"')

    print("\n========== 7) 烟雾测试：访问关键 URL ==========")
    base = f'http://newbb.test.bangbangvip.com'
    prefix = f'/autodev/{DEPLOY_ID}'
    smoke_urls = [
        f'{base}{prefix}/api/health',
        f'{base}{prefix}/home-safety',
    ]
    for u in smoke_urls:
        run(ssh, f'curl -k -s -o /dev/null -w "%{{http_code}} {u}\\n" "{u}"')

    print("\n========== 测试结果 ==========")
    print(f"backend pytest exit_code={code}  passed_marker={'YES' if test_ok else 'NO'}")
    return 0 if test_ok else 1


if __name__ == '__main__':
    sys.exit(main())
