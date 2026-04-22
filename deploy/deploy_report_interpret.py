"""远程部署脚本：ssh 到服务器，git pull，重建 backend / h5 / admin 容器。

使用：
  设置环境变量 GIT_TOKEN=<your_github_pat>，然后运行本脚本。
"""
import os
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
GIT_USER = "ankun-eric"
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = (
    f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN
    else "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)
# 常规项目在 /home/ubuntu/auto_output/<deploy_id> 或类似
CANDIDATE_DIRS = [
    f"/home/ubuntu/auto_output/{DEPLOY_ID}",
    f"/home/ubuntu/projects/{DEPLOY_ID}",
    f"/home/ubuntu/{DEPLOY_ID}",
    f"/opt/auto_output/{DEPLOY_ID}",
    f"/root/auto_output/{DEPLOY_ID}",
]


def run(ssh, cmd, timeout=300):
    print(f"$ {cmd}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out, flush=True)
    if err.strip():
        print(f"[stderr] {err}", flush=True)
    return rc, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # 1) 查找项目目录
    project_dir = None
    for d in CANDIDATE_DIRS:
        rc, out, _ = run(ssh, f"test -d {d} && echo YES || echo NO")
        if "YES" in out:
            project_dir = d
            break

    if not project_dir:
        # 尝试 find 搜索
        rc, out, _ = run(
            ssh,
            f"find /home /opt /root -maxdepth 4 -name '{DEPLOY_ID}' -type d 2>/dev/null | head -n 3",
            timeout=60,
        )
        lines = [l.strip() for l in out.splitlines() if l.strip() and DEPLOY_ID in l]
        if lines:
            project_dir = lines[0]

    if not project_dir:
        print("[!] 项目目录未找到，尝试克隆")
        project_dir = f"/home/ubuntu/auto_output/{DEPLOY_ID}"
        run(ssh, f"mkdir -p /home/ubuntu/auto_output")
        rc, _, _ = run(
            ssh,
            f"cd /home/ubuntu/auto_output && rm -rf {DEPLOY_ID} && "
            f"git clone {GIT_URL} {DEPLOY_ID}",
            timeout=600,
        )
        if rc != 0:
            print("[!] 克隆失败")
            return 1

    print(f"[+] 使用项目目录：{project_dir}")

    # 2) git pull (允许重试，且使用 token 的 https)
    run(ssh, f"cd {project_dir} && git remote set-url origin {GIT_URL}")
    rc = 1
    for attempt in range(5):
        rc, _, _ = run(
            ssh,
            f"cd {project_dir} && git fetch --all && git reset --hard origin/master",
            timeout=300,
        )
        if rc == 0:
            break
        print(f"[!] git pull 重试 {attempt + 1}/5")
        time.sleep(4)
    if rc != 0:
        print("[!] git pull 最终失败")
        return 1

    # 3) docker compose build & up
    rc, _, _ = run(
        ssh,
        f"cd {project_dir} && docker compose build --no-cache backend h5-web admin-web 2>&1 | tail -n 80",
        timeout=900,
    )
    rc, _, _ = run(
        ssh,
        f"cd {project_dir} && docker compose up -d 2>&1 | tail -n 30",
        timeout=300,
    )

    # 4) 等待启动
    time.sleep(8)
    run(ssh, f"cd {project_dir} && docker compose ps")
    run(
        ssh,
        f"docker logs --tail 60 {DEPLOY_ID}-backend 2>&1 | tail -n 60",
        timeout=60,
    )

    # 5) 简单可达性检查
    run(
        ssh,
        "curl -s -o /dev/null -w 'backend_health=%{http_code}\\n' "
        f"http://localhost/autodev/{DEPLOY_ID}/api/health 2>&1",
        timeout=30,
    )

    ssh.close()
    print("[+] 部署完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
