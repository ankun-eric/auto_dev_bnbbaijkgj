"""
[PRD-440] 部署脚本：远程服务器 git pull + 重建 H5 前端容器

仅部署 H5（影响 ai-home 与 chat 详情页）。后端无变更，无需重建。
小程序和 Flutter 不通过服务器部署，由打包阶段处理。
"""
import paramiko
import sys
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'

def exec_ssh(ssh, cmd, timeout=900):
    print(f"$ {cmd[:140]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    tail_out = "\n".join(out.splitlines()[-25:])
    tail_err = "\n".join(err.splitlines()[-25:])
    if tail_out.strip():
        print(f"  out:\n{tail_out}", flush=True)
    if tail_err.strip():
        print(f"  err:\n{tail_err}", flush=True)
    print(f"  exit={exit_code}", flush=True)
    return exit_code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # 1) 检查项目目录
    rc, out, _ = exec_ssh(ssh, f'ls -la {REMOTE_DIR} | head -30')
    if rc != 0:
        print("项目目录不存在，无法继续", flush=True)
        sys.exit(1)

    # 2) 查看当前的容器
    exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose ps 2>/dev/null || docker-compose ps')

    # 3) git fetch + reset 到远程最新
    rc, out, err = exec_ssh(
        ssh,
        f'cd {REMOTE_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline',
        timeout=120,
    )
    if rc != 0:
        print("git pull 失败", flush=True)
        sys.exit(2)

    # 4) 仅重建 frontend (h5-web) 容器（admin-web 在管理后台未涉及；backend 未改动）
    # 部署架构使用 docker-compose.prod.yml
    compose_file = 'docker-compose.prod.yml'
    rc, out, _ = exec_ssh(ssh, f'cd {REMOTE_DIR} && test -f {compose_file} && echo OK || echo MISSING')
    if 'MISSING' in out:
        compose_file = 'docker-compose.yml'

    # 5) 在 h5-web 容器中触发热重建（如果生产是 SSR Next.js），需要重建镜像
    # 找出包含 h5-web/frontend 字样的 service 名
    rc, out, _ = exec_ssh(ssh, f'cd {REMOTE_DIR} && grep -E "container_name|service" {compose_file} | head -40')
    print("compose services：", out[:500], flush=True)

    # 6) 重新 build & up h5-web (frontend) 服务
    # 兼容性：尝试两种 service 名 (frontend / h5-web / next / web)
    for svc in ['h5-web', 'frontend', 'web']:
        rc, out, err = exec_ssh(
            ssh,
            f'cd {REMOTE_DIR} && docker compose -f {compose_file} build {svc} 2>&1 | tail -30',
            timeout=900,
        )
        if rc == 0:
            print(f"build OK：{svc}", flush=True)
            exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose -f {compose_file} up -d --force-recreate {svc} 2>&1 | tail -20', timeout=300)
            break

    # 7) 等待容器启动
    time.sleep(10)

    # 8) 验证可达
    rc, out, _ = exec_ssh(
        ssh,
        f'curl -s -o /dev/null -w "%{{http_code}}" -m 15 http://localhost/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/',
    )
    print(f"\nlocal http_code: {out.strip()}", flush=True)

    ssh.close()


if __name__ == '__main__':
    main()
