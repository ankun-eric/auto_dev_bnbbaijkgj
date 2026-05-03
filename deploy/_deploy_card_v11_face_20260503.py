"""
[2026-05-03 卡管理 PRD v1.1 优化] 部署脚本
- SSH 到 newbb.test.bangbangvip.com
- 拉取最新代码（git pull）
- 重新构建并启动 backend / admin-web / h5-web 三个 Docker 容器
- 重启后等待健康
- 简单访问性检查
"""
from __future__ import annotations

import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"

# 服务器上的项目目录（按现有部署惯例查找）
CANDIDATE_DIRS = [
    "/home/ubuntu/auto_dev_bnbbaijkgj",
    "/home/ubuntu/projects/auto_dev_bnbbaijkgj",
    "/home/ubuntu/bnbbaijkgj",
]

PROJECT_TAG = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-4000:])
    if err.strip():
        print(f"[stderr]\n{err.rstrip()[-2000:]}")
    print(f"<<< exit={code}")
    return code, out, err


def find_project_dir(ssh: paramiko.SSHClient) -> str:
    for d in CANDIDATE_DIRS:
        code, _, _ = run(ssh, f"test -d {d} && echo OK || echo NO")
        # 通过返回值判断
        ok = (
            code == 0
            and "OK" in (run(ssh, f"test -d {d} && echo HIT")[1])
        )
        if ok:
            return d
    # 兜底：通过 docker container 的标签找到工作目录
    code, out, _ = run(ssh, f"docker inspect {PROJECT_TAG}-backend --format '{{{{.Config.Labels}}}}' 2>/dev/null || true")
    # 再试一种：通过 docker compose 项目目录
    code, out, _ = run(ssh, f"docker inspect {PROJECT_TAG}-backend --format '{{{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}}}' 2>/dev/null || true")
    line = (out or "").strip().splitlines()[-1] if out and out.strip() else ""
    if line and line.startswith("/"):
        return line
    raise RuntimeError("无法在远程服务器上定位项目目录")


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {USER}@{HOST} ...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        proj_dir = find_project_dir(ssh)
        print(f"远程项目目录：{proj_dir}")

        # 1. 同步代码
        run(ssh, f"cd {proj_dir} && git fetch --all 2>&1 | tail -20")
        run(ssh, f"cd {proj_dir} && git reset --hard origin/master 2>&1 | tail -5")
        code, out, _ = run(ssh, f"cd {proj_dir} && git log -1 --format='%H %s'")
        print(f"远程 HEAD: {out.strip()}")

        # 2. 重新构建 + 启动
        # 强制重建 backend / admin-web / h5-web，不动 db
        for svc in ("backend", "admin-web", "h5-web"):
            run(
                ssh,
                f"cd {proj_dir} && docker compose build --no-cache {svc} 2>&1 | tail -40",
                timeout=1500,
            )

        run(
            ssh,
            f"cd {proj_dir} && docker compose up -d --force-recreate backend admin-web h5-web 2>&1 | tail -20",
            timeout=300,
        )

        # 3. 等待容器健康
        time.sleep(10)
        run(ssh, f"docker ps --filter name={PROJECT_TAG} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

        # 4. 简单可达性测试（80 端口走 nginx 反代）
        base = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_TAG}"
        time.sleep(20)
        for path in [
            "/api/cards",
            "/admin",
            "/cards",
        ]:
            run(ssh, f"curl -ksL -o /dev/null -w 'GET {path} -> %{{http_code}}\\n' {base}{path}")

        # 5. 检查后端日志中是否完成 schema_sync
        run(ssh, f"docker logs --tail 80 {PROJECT_TAG}-backend 2>&1 | tail -80")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
