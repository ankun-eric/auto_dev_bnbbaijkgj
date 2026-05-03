"""强制清空服务器 git 缓存并重新拉取最新代码。"""
from __future__ import annotations
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJ_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_TAG = "6b099ed3-7175-4a78-91f4-44570c84ed27"
import os
_TOKEN = os.environ.get("GIT_TOKEN", "")
REPO_URL = (
    f"https://ankun-eric:{_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if _TOKEN
    else "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


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


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 修复 git：强制重设 origin remote 并 fetch；用 --force-with-lease 模式
        run(ssh, f"cd {PROJ_DIR} && git remote set-url origin '{REPO_URL}'")
        run(ssh, f"cd {PROJ_DIR} && rm -rf .git/objects/pack/*.tmp 2>/dev/null; git gc --prune=now 2>&1 | tail -5", timeout=300)
        # 试 fetch
        code, out, _ = run(ssh, f"cd {PROJ_DIR} && git fetch origin master 2>&1 | tail -10", timeout=300)
        if "did not send" in out or "Could not read" in out:
            print("[!] git fetch corrupted, fallback to fresh clone")
            run(ssh, f"rm -rf {PROJ_DIR}.bak && cp -r {PROJ_DIR} {PROJ_DIR}.bak", timeout=300)
            run(ssh, f"rm -rf {PROJ_DIR}/.git", timeout=120)
            run(ssh, f"cd /tmp && rm -rf _fresh_clone && git clone --depth 1 '{REPO_URL}' _fresh_clone 2>&1 | tail -10", timeout=600)
            run(ssh, f"cp -r /tmp/_fresh_clone/.git {PROJ_DIR}/.git", timeout=120)
            run(ssh, f"cd {PROJ_DIR} && git fetch origin master 2>&1 | tail -10", timeout=300)

        run(ssh, f"cd {PROJ_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        code, out, _ = run(ssh, f"cd {PROJ_DIR} && git log -1 --format='%H %s'")
        print(f"远程 HEAD: {out.strip()}")
        if "e00c223" not in out:
            print("[!] 服务器代码 HEAD 不是预期的 e00c223，但仍尝试构建")

        # 重建 + 启动
        for svc in ("backend", "admin-web", "h5-web"):
            run(ssh, f"cd {PROJ_DIR} && docker compose build --no-cache {svc} 2>&1 | tail -20", timeout=1500)
        run(ssh, f"cd {PROJ_DIR} && docker compose up -d --force-recreate backend admin-web h5-web 2>&1 | tail -15", timeout=300)

        time.sleep(20)
        run(ssh, f"docker ps --filter name={PROJECT_TAG} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

        # 简单可达性测试
        base = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_TAG}"
        for path in ["/api/cards", "/admin", "/cards", "/cards/wallet"]:
            run(ssh, f"curl -ksL -o /dev/null -w 'GET {path} -> %{{http_code}}\\n' {base}{path}")

        # 检查 face_style 字段是否生效
        run(ssh, f"curl -ks {base}/api/cards | head -c 600")

        # 检查容器内代码 HEAD 与 git HEAD 是否一致（比对 schemas/cards.py 中是否有 face_style）
        run(ssh, f"docker exec {PROJECT_TAG}-backend grep -c face_style /app/app/schemas/cards.py 2>&1 || true")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
