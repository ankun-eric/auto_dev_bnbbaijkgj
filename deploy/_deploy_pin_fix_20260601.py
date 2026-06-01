#!/usr/bin/env python3
"""部署：历史记录置顶切换页面后丢失修复（仅 H5 前端代码变更）。

策略：优先 git fetch+reset（重试 3 次）；失败则降级 scp 同步 h5-web/src。
然后强制无缓存重建 h5-web 容器 → 重连 gateway 网络 → reload → 验证。
"""
import os
import re
import sys
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_git_url():
    """从 deploy/deploy_msg.txt 读取 Git 仓库与 token，避免在源码中硬编码密钥。"""
    msg = os.path.join(LOCAL_ROOT, 'deploy', 'deploy_msg.txt')
    repo = user = token = ''
    with open(msg, encoding='utf-8') as f:
        for line in f:
            if '仓库链接' in line:
                repo = line.split(':', 1)[1].strip()
            elif '用户名' in line and 'Git' in line:
                user = line.split(':', 1)[1].strip()
            elif 'token' in line.lower():
                token = line.split(':', 1)[1].strip()
    host_path = re.sub(r'^https?://', '', repo)
    return f'https://{user}:{token}@{host_path}'


GIT_URL = _read_git_url()


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, timeout=1800):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = ''
    for line in iter(stdout.readline, ''):
        print(line, end='', flush=True)
        out += line
    code = stdout.channel.recv_exit_status()
    print(f"[exit_code: {code}]", flush=True)
    return out, code


def git_sync(ssh):
    run(ssh, f'cd {PROJECT_DIR} && git remote set-url origin {GIT_URL} 2>/dev/null; true')
    for attempt in range(1, 4):
        out, code = run(ssh,
            f'cd {PROJECT_DIR} && timeout 90 git fetch origin master --no-tags 2>&1 && '
            f'git reset --hard origin/master && git clean -fd -e .env -e .env.production -e .env.build && '
            f'git log -1 --oneline', timeout=150)
        if code == 0 and '9225478' in out:
            print(f"git 同步成功（第 {attempt} 次）")
            return True
        print(f"git fetch 第 {attempt} 次失败/未到目标 commit")
    return False


def scp_sync(ssh):
    """降级：用 sftp 上传修改的关键文件（Sidebar.tsx）。"""
    print("降级为 scp/sftp 同步关键文件")
    sftp = ssh.open_sftp()
    rel = 'h5-web/src/components/ai-chat/Sidebar.tsx'
    local = os.path.join(LOCAL_ROOT, rel.replace('/', os.sep))
    remote = f'{PROJECT_DIR}/{rel}'
    print(f"上传 {local} -> {remote}")
    sftp.put(local, remote)
    sftp.close()
    return True


def main():
    ssh = get_ssh()

    if not git_sync(ssh):
        scp_sync(ssh)

    run(ssh, f'cd {PROJECT_DIR} && BC=$(git log -1 --format=%H 2>/dev/null || echo unknown) && '
             f'(grep -q "^BUILD_COMMIT=" .env 2>/dev/null && sed -i "s|^BUILD_COMMIT=.*|BUILD_COMMIT=$BC|" .env || echo "BUILD_COMMIT=$BC" >> .env); '
             f'echo "BUILD_COMMIT=$BC"')

    out, code = run(ssh, f'cd {PROJECT_DIR} && docker compose build --no-cache h5-web 2>&1 | tail -25', timeout=2400)
    if code != 0:
        print("!!! h5-web 构建失败")
        ssh.close()
        sys.exit(1)

    run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web')
    run(ssh, f'sleep 8 && docker ps --filter name={DEPLOY_ID}-h5 --format "{{{{.Names}}}} {{{{.Status}}}}"')

    out, _ = run(ssh, 'docker ps --filter name=gateway --format "{{.Names}}"')
    gw = next((l.strip() for l in out.splitlines() if 'gateway' in l and 'exit_code' not in l), None)
    print(f"gateway 容器: {gw}")
    if gw:
        run(ssh, f'docker network connect {DEPLOY_ID}-network {gw} 2>/dev/null || true')
        run(ssh, f'docker exec {gw} nginx -t && docker exec {gw} nginx -s reload')
        run(ssh, f'docker exec {gw} curl -Is http://{DEPLOY_ID}-h5:3001/ 2>&1 | head -3')

    ssh.close()
    print("\n=== 部署完成 ===")


if __name__ == '__main__':
    main()
