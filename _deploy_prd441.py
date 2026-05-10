"""
PRD-441 · AI 对话风格设计 Token 体系 · 自动部署脚本

流程：
1) git add + commit + push 到 origin/master
2) SSH 到服务器，cd 到项目目录，git fetch + reset --hard origin/master
3) docker compose -f docker-compose.prod.yml build h5-web
4) docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web
5) 等待容器健康
6) curl 验证服务器上 design-system 4 个交付物可访问
"""
import os
import subprocess
import sys
import time

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def run(cmd, cwd=None, check=True):
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout[:2000])
    if result.stderr:
        print(result.stderr[:1500], file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    return result


def ssh_exec(ssh, cmd, timeout=600, check=False):
    print(f"\n[remote] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out_chunks = []
    for line in iter(stdout.readline, ""):
        if not line:
            break
        line = line.rstrip("\r\n")
        print(f"  | {line}")
        out_chunks.append(line)
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        print(f"  ! stderr: {err[:1500]}", file=sys.stderr)
    if check and rc != 0:
        raise RuntimeError(f"remote command failed (rc={rc}): {cmd}")
    return rc, "\n".join(out_chunks), err


def main():
    print("=" * 70)
    print("PRD-441 部署：AI 对话风格设计 Token 体系")
    print("=" * 70)

    # 1. git 提交并推送
    run("git add h5-web/public/design-system tests/test_prd441_design_tokens.py _deploy_prd441.py .develop_start_commit_441.txt 2>&1")
    # 检查是否有改动
    chk = run("git diff --cached --name-only", check=False)
    if not chk.stdout.strip():
        print("[git] 无暂存改动，跳过 commit")
    else:
        run('git commit -m "feat(prd-441): AI 对话风格设计 Token 体系（宾尼小康 v1.0：design-tokens.css/json + 29 屏 HTML 原型 + PRD 文档）" 2>&1', check=False)

    # push 重试
    for i in range(3):
        r = run("git push origin master 2>&1", check=False)
        if r.returncode == 0:
            break
        print(f"[git push] 第 {i+1} 次失败，10s 后重试...")
        time.sleep(10)
    else:
        print("[git push] 3 次后仍失败，继续执行 SCP 兜底", file=sys.stderr)

    # 2. SSH 连接
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"\n[ssh] connecting to {USER}@{HOST}...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    # 3. 服务器同步代码：先尝试 git，失败则 SFTP 兜底
    rc, _, _ = ssh_exec(ssh, f"cd {REMOTE_DIR} && timeout 60 git fetch origin master && git reset --hard origin/master 2>&1 | tail -5", timeout=90)
    sftp_used = False
    if rc != 0:
        print("[remote git] 失败/超时，使用 SFTP 兜底直传 design-system...")
        sftp = ssh.open_sftp()
        local_dir = os.path.join(os.path.dirname(__file__), "h5-web", "public", "design-system")
        remote_dir = f"{REMOTE_DIR}/h5-web/public/design-system"
        ssh_exec(ssh, f"mkdir -p {remote_dir}")
        for f in os.listdir(local_dir):
            local = os.path.join(local_dir, f)
            remote = f"{remote_dir}/{f}"
            print(f"  SFTP: {f}")
            sftp.put(local, remote)
        sftp.close()
        sftp_used = True

    # 验证服务器上的文件
    ssh_exec(ssh, f"ls -la {REMOTE_DIR}/h5-web/public/design-system/")

    # 4. 重建 h5-web 容器
    rc, _, _ = ssh_exec(
        ssh,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -30",
        timeout=600,
    )
    if rc != 0:
        print("[build] 失败", file=sys.stderr)
        ssh.close()
        return 1

    rc, _, _ = ssh_exec(
        ssh,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1 | tail -10",
        timeout=120,
    )
    if rc != 0:
        print("[up] 失败", file=sys.stderr)
        ssh.close()
        return 1

    # 5. 等待容器
    print("\n[wait] 等待 h5-web 容器就绪...")
    time.sleep(15)
    ssh_exec(ssh, f"docker ps --filter name={DEPLOY_ID}-h5-web --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'", check=False)

    # 6. smoke test：验证 4 个交付物可访问
    print("\n" + "=" * 70)
    print("Smoke Test：验证 design-system 交付物")
    print("=" * 70)

    test_paths = [
        "/design-system/",
        "/design-system/index.html",
        "/design-system/prototype.html",
        "/design-system/design-tokens.css",
        "/design-system/design-tokens.json",
        "/design-system/PRD-441-AI对话风格规范.md",
        "/ai-home",  # 回归：原 AI 主页仍可用
    ]
    fail = 0
    pass_count = 0
    for p in test_paths:
        url = f"{BASE_URL}{p}"
        rc, out, _ = ssh_exec(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" -L "{url}"', timeout=30, check=False)
        code = out.strip().split("\n")[-1] if out else "?"
        status = "✓ PASS" if code in ("200", "301", "302", "307", "308") else "✗ FAIL"
        if code in ("200", "301", "302", "307", "308"):
            pass_count += 1
        else:
            fail += 1
        print(f"  [{status}] {code}  {p}")

    ssh.close()

    print("\n" + "=" * 70)
    print(f"smoke 结果：{pass_count}/{len(test_paths)} 通过，{fail} 失败")
    print("=" * 70)

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
