"""[2026-05-05] H5 端订单详情「预约门店」联系商家弹层 Bug 修复 — H5-only 部署。

策略：
1. 通过 SFTP 上传变更文件 h5-web/src/app/unified-order/[id]/page.tsx
2. 在服务器上 docker compose build h5-web（不使用 --no-cache，加快构建；如缓存导致问题再回退）
3. docker compose up -d h5-web
4. 等待容器健康
5. 用 curl 验证关键 H5 路径
"""
import sys
import time
import os
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
H5_CONTAINER = f'{PROJECT_ID}-h5'
H5_SERVICE = 'h5-web'
GATEWAY = 'gateway-nginx'
COMPOSE_FILE = 'docker-compose.yml'
BASE_URL = f'https://{HOST}/autodev/{PROJECT_ID}'

LOCAL_ROOT = r'C:\auto_output\bnbbaijkgj'
CHANGED_FILES = [
    'h5-web/src/app/unified-order/[id]/page.tsx',
]


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
            data = chan.recv(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"\n[exit={code}]", flush=True)
    if code != 0 and not ignore_error:
        print(f"!! 命令失败: {cmd}")
    return code, ''.join(out_chunks)


def upload_files(ssh):
    sftp = ssh.open_sftp()
    try:
        for rel in CHANGED_FILES:
            local = os.path.join(LOCAL_ROOT, rel.replace('/', os.sep))
            remote = f'{PROJECT_DIR}/{rel}'
            # mkdir -p remote dir
            remote_dir = os.path.dirname(remote)
            run(ssh, f'mkdir -p "{remote_dir}"', ignore_error=True)
            print(f"[SFTP] {local} -> {remote}", flush=True)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    ssh = get_ssh()
    try:
        # 1) 上传变更文件
        upload_files(ssh)

        # 2) 验证文件已上传，并 sanity-check 内容
        run(ssh,
            f'cd {PROJECT_DIR} && '
            f'wc -l "h5-web/src/app/unified-order/[id]/page.tsx" && '
            f'grep -c "联系商家" "h5-web/src/app/unified-order/[id]/page.tsx" || true')

        # 3) 重建 h5-web 镜像
        run(ssh,
            f'cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build {H5_SERVICE}',
            timeout=1200)

        # 4) 启动新容器
        run(ssh,
            f'cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d {H5_SERVICE}',
            timeout=300)

        # 5) 重新挂载 gateway 网络（避免 502）
        run(ssh,
            f'docker network connect {PROJECT_ID}-network {GATEWAY} 2>/dev/null || true',
            ignore_error=True)
        run(ssh, f'docker exec {GATEWAY} nginx -s reload', ignore_error=True)

        # 6) 健康等待（最长 90s）
        ok = False
        for i in range(18):
            code, out = run(ssh,
                f'docker ps --filter name={H5_CONTAINER} --format "{{{{.Status}}}}"',
                timeout=20, ignore_error=True)
            status = out.strip()
            print(f"[wait #{i+1}] container status: {status!r}")
            if status.startswith('Up'):
                # 容器启动后再等几秒等 nginx/next 就绪
                time.sleep(5)
                ok = True
                break
            time.sleep(5)
        if not ok:
            print("!! H5 容器在 90s 内未起来")

        # 7) 验证关键 URL
        print("\n=== HTTP 验证 ===")
        urls = [
            f'{BASE_URL}/',
            f'{BASE_URL}/login',
            f'{BASE_URL}/orders',
            f'{BASE_URL}/api/health',
        ]
        results = {}
        for url in urls:
            code, out = run(ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}" -L --max-time 15 "{url}"',
                timeout=30, ignore_error=True)
            results[url] = out.strip()

        # 8) 容器最终状态
        run(ssh,
            f'docker ps --filter name={H5_CONTAINER} '
            f'--format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"')

        # 9) 总结
        print("\n=========================================")
        print(" 部署结果汇总")
        print("=========================================")
        for url, code in results.items():
            print(f"  {code}  {url}")
        print("=========================================")

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
