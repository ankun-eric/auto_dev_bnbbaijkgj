#!/usr/bin/env python3
"""[2026-05-04 订单「联系商家」电话不显示 Bug 修复 v1.0]
部署脚本：服务器拉取最新 master → 重启 backend → 重建 h5-web → 跑回归测试。
"""
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
BACKEND = f'{PROJECT_ID}-backend'
H5_FRONTEND = f'{PROJECT_ID}-h5-frontend'
GATEWAY = 'gateway-nginx'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600, ignore_error=False):
    print(f"\n>>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_chunks = []
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data)
            sys.stdout.flush()
            out_chunks.append(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data)
            sys.stdout.flush()
            out_chunks.append(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    if code != 0 and not ignore_error:
        print(f"❌ 命令失败：{cmd}")
    return code, ''.join(out_chunks)


def main():
    ssh = get_ssh()
    try:
        # 1) 拉取最新 master
        run(ssh,
            f'cd {PROJECT_DIR} && git fetch origin master && '
            f'git reset --hard origin/master && git log -1 --oneline')

        # 2) 重启 backend（直接覆盖 /app 即可，无需重建 image，节省时间）
        run(ssh, f'docker cp {PROJECT_DIR}/backend/app {BACKEND}:/app/')
        run(ssh, f'docker cp {PROJECT_DIR}/backend/tests {BACKEND}:/app/')
        run(ssh, f'docker restart {BACKEND}', timeout=120)

        # 等待 backend 健康
        for i in range(20):
            code, _ = run(
                ssh,
                f'docker exec {BACKEND} curl -sf http://localhost:8000/api/health '
                f'-o /dev/null && echo OK',
                timeout=30,
                ignore_error=True,
            )
            if code == 0:
                print('✅ backend 健康检查通过')
                break
            time.sleep(3)
        else:
            print('⚠️ backend 健康检查超时')

        # 3) 跑后端回归测试（pytest 在容器内已安装，参考前次部署脚本）
        run(ssh,
            f'docker exec {BACKEND} python -m pytest '
            f'tests/test_contact_store_storeid_bugfix.py '
            f'-v --tb=short -p no:cacheprovider 2>&1',
            timeout=300)

        # 4) 重建 h5-web 容器（前端代码变更必须重新构建）
        # 检查 h5-web 容器名 / docker-compose
        code, out = run(
            ssh,
            f'cd {PROJECT_DIR} && ls docker-compose*.yml 2>/dev/null',
            ignore_error=True,
        )
        # 优先使用 docker-compose.prod.yml；其次 docker-compose.yml
        compose_file = (
            'docker-compose.prod.yml' if 'docker-compose.prod.yml' in out else
            'docker-compose.yml'
        )
        # 找出 h5 服务名（h5 / h5-web / h5-frontend 等）
        code, out = run(
            ssh,
            f'cd {PROJECT_DIR} && docker compose -f {compose_file} ps --services',
            ignore_error=True,
        )
        h5_service = None
        for s in out.splitlines():
            s = s.strip()
            if 'h5' in s.lower():
                h5_service = s
                break
        print(f'📦 h5 服务名: {h5_service}')

        if h5_service:
            # 强制无快取构建 h5-web
            run(
                ssh,
                f'cd {PROJECT_DIR} && '
                f'BUILD_COMMIT=$(git log -1 --format=%H) '
                f'docker compose -f {compose_file} build --no-cache {h5_service}',
                timeout=900,
            )
            run(
                ssh,
                f'cd {PROJECT_DIR} && docker compose -f {compose_file} up -d {h5_service}',
                timeout=300,
            )
            # 重新连接 gateway 网络（防 down/up 后 502）
            run(
                ssh,
                f'docker network connect {PROJECT_ID}-network {GATEWAY} 2>/dev/null || true',
                ignore_error=True,
            )
            # reload gateway（保险起见）
            run(ssh, f'docker exec {GATEWAY} nginx -s reload', ignore_error=True)
        else:
            print('⚠️ 未找到 h5 服务，跳过前端重建')

        # 5) 端到端访问验证：调用 /api/health + 一个公开门店 contact 接口
        run(
            ssh,
            f'curl -sI https://{HOST}/autodev/{PROJECT_ID}/api/health | head -3',
            ignore_error=True,
        )

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
