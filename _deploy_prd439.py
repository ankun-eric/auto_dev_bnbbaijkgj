"""[PRD-439] H5 健康打卡升级为提醒 — 全自动部署脚本。

实现方式：
1. SSH 连远程
2. 优先 git fetch + reset --hard origin/master 拉新代码
3. 若 git 拉不到本次 commit（GitHub 推送可能滞后），用 SFTP 直传本次新增/修改的关键文件兜底
4. docker compose build backend h5-web
5. docker compose up -d backend h5-web
6. 等待健康检查
7. smoke test 一组关键接口
"""
from __future__ import annotations

import io
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 本次需要确保部署到位的"关键文件"——若 git 没拉到，逐个 SFTP 兜底
KEY_FILES = [
    # 后端
    "backend/app/models/models.py",
    "backend/app/main.py",
    "backend/app/schemas/medication_reminder.py",
    "backend/app/api/medication_reminder.py",
    "backend/tests/test_prd439_medication_reminder.py",
    # H5
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/app/(ai-chat)/medication-plans/page.tsx",
    "h5-web/src/app/health-plan/checkin/page.tsx",
    "h5-web/src/components/ai-chat/ReminderBellButton.tsx",
    "h5-web/src/components/ai-chat/ReminderDrawer.tsx",
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(ssh: paramiko.SSHClient, cmd: str, *, timeout: int = 60, capture: bool = True) -> tuple[int, str]:
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=timeout)
    out_lines: list[str] = []
    if capture:
        for line in iter(stdout.readline, ""):
            line = line.rstrip()
            if line:
                out_lines.append(line)
    rc = stdout.channel.recv_exit_status()
    return rc, "\n".join(out_lines)


def sftp_put_files(ssh: paramiko.SSHClient, files: list[str]) -> None:
    sftp = ssh.open_sftp()
    try:
        for rel in files:
            local_path = rel
            remote_path = f"{PROJECT_DIR}/{rel}"
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                # 确保父目录存在
                parent = "/".join(remote_path.split("/")[:-1])
                _ssh_mkdir_p(ssh, parent)
                with sftp.open(remote_path, "wb") as rf:
                    rf.write(data)
                log(f"  SFTP put {rel} -> {len(data)} bytes")
            except FileNotFoundError:
                log(f"  ⚠️ 本地缺失: {rel}")
            except Exception as e:
                log(f"  ❌ SFTP {rel} 失败: {e}")
    finally:
        sftp.close()


def _ssh_mkdir_p(ssh: paramiko.SSHClient, path: str) -> None:
    run(ssh, f"mkdir -p '{path}'", timeout=10)


def smoke_test(ssh: paramiko.SSHClient) -> bool:
    log("--- Smoke 测试 ---")
    targets = [
        ("/api/health", [200]),
        ("/api/medication-reminder/plans", [401, 403]),
        ("/api/medication-reminder/today", [401, 403]),
        ("/api/medication-reminder/badge", [401, 403]),
        ("/api/medication-reminder/appointments", [401, 403]),
        ("/", [200, 308, 307]),
        ("/ai-home", [200, 308, 307]),
        ("/medication-plans", [200, 308, 307]),
        ("/health-plan/checkin", [200, 308, 307]),
    ]
    all_ok = True
    for path, expected in targets:
        url = f"{BASE_URL}{path}"
        cmd = (
            "curl -s -o /dev/null -w '%{http_code}' --max-time 15 "
            f"--max-redirs 0 '{url}'"
        )
        _, code = run(ssh, cmd, timeout=30)
        code = code.strip().splitlines()[-1] if code.strip() else "000"
        ok = code in [str(c) for c in expected]
        all_ok = all_ok and ok
        log(f"  {'✅' if ok else '❌'} {path} -> {code} (expect {expected})")
    return all_ok


def main() -> int:
    log("=== PRD-439 部署开始 ===")
    log(f"目标服务器: {HOST}, 部署目录: {PROJECT_DIR}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

    # ── Step 1: git pull ──
    log("--- Step 1: git fetch + reset --hard origin/master ---")
    rc, out = run(
        ssh,
        f"cd {PROJECT_DIR} && git fetch origin master 2>&1 && "
        f"git reset --hard origin/master 2>&1 | tail -5",
        timeout=120,
    )
    log(out[-1500:] if out else "(no output)")
    log(f"git rc={rc}")

    # ── Step 2: SFTP 兜底直传关键文件 ──
    log("--- Step 2: SFTP 兜底直传关键文件 ---")
    sftp_put_files(ssh, KEY_FILES)

    # ── Step 3: build ──
    log("--- Step 3: docker compose build backend h5-web ---")
    rc, out = run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -50",
        timeout=900,
    )
    if rc != 0:
        log("❌ build 失败，最后输出：")
        log(out[-2000:])
        ssh.close()
        return 2
    log("build OK，最后几行：")
    log(out[-1000:])

    # ── Step 4: up -d ──
    log("--- Step 4: docker compose up -d backend h5-web ---")
    rc, out = run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1 | tail -30",
        timeout=180,
    )
    log(out[-1500:] if out else "(no output)")

    # ── Step 5: 等待容器就绪 ──
    log("--- Step 5: 等待容器健康 (40s) ---")
    time.sleep(40)

    rc, out = run(
        ssh,
        f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}",
        timeout=15,
    )
    log("当前项目容器状态：")
    log(out)

    # ── Step 6: smoke test ──
    ok = smoke_test(ssh)

    # ── Step 7: 后端日志末段，验证迁移函数执行 ──
    log("--- Step 7: 后端最近日志（含 prd439 标记） ---")
    rc, out = run(
        ssh,
        f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 | grep -E 'prd439|medication|ERROR|Traceback' | tail -30",
        timeout=15,
    )
    log(out or "(无 prd439 / ERROR 日志匹配)")

    ssh.close()

    if ok:
        log("✅ 部署 + smoke 全部通过")
        return 0
    log("❌ smoke 部分失败")
    return 3


if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(rc)
    except Exception as e:
        log(f"💥 部署异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
