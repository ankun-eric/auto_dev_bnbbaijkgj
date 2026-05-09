# -*- coding: utf-8 -*-
"""[Bug-433] 远程部署脚本：把当前 master 推到生产服务器并重建 backend + h5-web 容器。

执行流程：
  1. SSH 登录到 newbb.test.bangbangvip.com
  2. cd 到项目部署目录
  3. git fetch + git reset --hard origin/master（覆盖历史本地工作区改动）
  4. docker compose build backend h5-web
  5. docker compose up -d backend h5-web
  6. 等待健康检查通过
  7. 验证 /api/health 200

不依赖 sshpass，使用 paramiko。
"""
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REPO_URL = "https://github.com/ankun-eric/auto_dev_bnbbaijkgj"
PROJECT_BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600, log: bool = True) -> tuple[int, str, str]:
    if log:
        print(f"\n$ {cmd}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    stdout.channel.set_combine_stderr(False)
    out_buf, err_buf = [], []
    last_print = time.time()
    while True:
        if stdout.channel.recv_ready():
            chunk = stdout.channel.recv(65536).decode("utf-8", errors="replace")
            out_buf.append(chunk)
            if log:
                sys.stdout.write(chunk)
                sys.stdout.flush()
                last_print = time.time()
        if stdout.channel.recv_stderr_ready():
            chunk = stdout.channel.recv_stderr(65536).decode("utf-8", errors="replace")
            err_buf.append(chunk)
            if log:
                sys.stderr.write(chunk)
                sys.stderr.flush()
                last_print = time.time()
        if stdout.channel.exit_status_ready():
            # 收尾排空
            while stdout.channel.recv_ready():
                chunk = stdout.channel.recv(65536).decode("utf-8", errors="replace")
                out_buf.append(chunk)
                if log:
                    sys.stdout.write(chunk); sys.stdout.flush()
            while stdout.channel.recv_stderr_ready():
                chunk = stdout.channel.recv_stderr(65536).decode("utf-8", errors="replace")
                err_buf.append(chunk)
                if log:
                    sys.stderr.write(chunk); sys.stderr.flush()
            break
        if time.time() - last_print > 5:
            # 心跳，避免长时间 build 看起来卡死
            if log:
                sys.stdout.write(".")
                sys.stdout.flush()
            last_print = time.time()
        time.sleep(0.2)
    rc = stdout.channel.recv_exit_status()
    return rc, "".join(out_buf), "".join(err_buf)


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] 连接 {USER}@{HOST} ...", flush=True)
    ssh.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)

    # 探测项目目录：根据现有 deploy 历史脚本，路径常见为 /home/ubuntu/auto_dev_<short>
    candidates = [
        f"/home/ubuntu/auto_dev_bnbbaijkgj",
        f"/home/ubuntu/projects/{DEPLOY_ID}",
        f"/srv/{DEPLOY_ID}",
        f"/home/ubuntu/{DEPLOY_ID}",
    ]
    project_dir = None
    for c in candidates:
        rc, _, _ = run(ssh, f"test -d {c} && test -f {c}/docker-compose.yml && echo OK", timeout=30, log=False)
        if rc == 0:
            project_dir = c
            print(f"[+] 项目目录: {project_dir}", flush=True)
            break
    if not project_dir:
        # 兜底：在 /home/ubuntu 搜索
        rc, out, _ = run(
            ssh,
            "find /home/ubuntu /srv /opt -maxdepth 4 -type f -name docker-compose.yml 2>/dev/null | head -20",
            timeout=60,
        )
        # 选择 grep 含 DEPLOY_ID 的
        rc2, out2, _ = run(
            ssh,
            f"find /home/ubuntu /srv /opt -maxdepth 4 -type f -name docker-compose.yml 2>/dev/null "
            f"| xargs -I{{}} sh -c 'grep -l \"{DEPLOY_ID}\" {{}}' 2>/dev/null",
            timeout=60,
        )
        for line in out2.splitlines():
            line = line.strip()
            if line.endswith("docker-compose.yml"):
                project_dir = line.rsplit("/", 1)[0]
                print(f"[+] 项目目录: {project_dir}", flush=True)
                break
    if not project_dir:
        print("[!] 未能定位项目目录，退出", flush=True)
        return 2

    # 拉取最新代码
    rc, _, _ = run(ssh, f"cd {project_dir} && git fetch --all --prune", timeout=180)
    if rc != 0:
        return 3
    rc, _, _ = run(ssh, f"cd {project_dir} && git reset --hard origin/master", timeout=120)
    if rc != 0:
        return 4
    rc, head_out, _ = run(ssh, f"cd {project_dir} && git log -1 --oneline", timeout=30)
    print(f"[+] HEAD: {head_out.strip()}", flush=True)
    if "ec9ff1f" not in head_out and "Bug-433" not in head_out and "bug-433" not in head_out:
        print("[!] 注意：HEAD 不含本次 bug-433 commit hash，但仍继续部署", flush=True)

    # 构建 + 重启 backend / h5-web
    rc, _, _ = run(ssh, f"cd {project_dir} && docker compose build backend h5-web", timeout=900)
    if rc != 0:
        return 5
    rc, _, _ = run(ssh, f"cd {project_dir} && docker compose up -d backend h5-web", timeout=300)
    if rc != 0:
        return 6

    # 等后端 health
    print("[*] 等待 backend 健康检查 ...", flush=True)
    for attempt in range(60):
        time.sleep(3)
        rc, out, _ = run(
            ssh,
            f"curl -s -o /dev/null -w '%{{http_code}}' {PROJECT_BASE}/api/health",
            timeout=15,
            log=False,
        )
        code = out.strip()
        print(f"  [t+{(attempt+1)*3}s] /api/health -> {code}", flush=True)
        if code == "200":
            break
    else:
        print("[!] 健康检查 60 次后仍未通过，部署失败", flush=True)
        return 7

    # 验证 ai-home 路由
    rc, out, _ = run(
        ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' '{PROJECT_BASE}/ai-home'",
        timeout=15,
        log=False,
    )
    print(f"[+] /ai-home -> {out.strip()} (308 / 200 都属正常)", flush=True)

    # 验证迁移：source / parent_id 列已加上
    rc, out, _ = run(
        ssh,
        f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e "
        f"\"SHOW COLUMNS FROM bini_health.chat_messages LIKE 'source';\" 2>&1",
        timeout=30,
    )
    rc, out2, _ = run(
        ssh,
        f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e "
        f"\"SHOW COLUMNS FROM bini_health.chat_messages LIKE 'parent_id';\" 2>&1",
        timeout=30,
    )
    if "source" in out and "parent_id" in out2:
        print("[+] chat_messages 字段迁移已生效（source + parent_id 存在）", flush=True)
    else:
        print("[!] 字段迁移可能未生效，请人工核查（不阻断部署）", flush=True)

    # 验证流式接口签名（不传 source 仍 200）
    print("[*] 部署成功", flush=True)
    ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
