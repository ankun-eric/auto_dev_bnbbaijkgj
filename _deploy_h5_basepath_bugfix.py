"""[2026-05-04 H5 支付链路 BasePath 修复 v1.0] 部署脚本.

执行步骤：
1) SFTP 把变更的 6 个文件上传到服务器项目目录
2) 远程 docker compose build h5-web backend
3) 远程 docker compose up -d
4) 等服务启动 25s
5) docker cp test_h5_basepath_pay_url_bugfix.py 到 backend 容器
6) docker exec backend pytest 测试该用例
7) curl 验证关键 URL：
   - /  -> 200/308
   - /sandbox-pay -> 200 (需要 query 参数也行)
   - /api/health -> 200

注意：
- 不要重启 db 容器，避免数据丢失
"""

from __future__ import annotations

import os
import sys
import time
import posixpath

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 本次需要上传的文件（相对仓库根目录）
FILES_TO_UPLOAD = [
    "h5-web/src/lib/basePath.ts",
    "h5-web/src/lib/auth.ts",
    "h5-web/src/app/checkout/page.tsx",
    "h5-web/src/app/unified-order/[id]/page.tsx",
    "backend/app/api/unified_orders.py",
    "backend/tests/test_h5_basepath_pay_url_bugfix.py",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".env.example",
]


def log(msg: str) -> None:
    print(f"[deploy_h5_basepath] {msg}", flush=True)


def make_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    log(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        # 截断显示，避免输出过长
        snippet = out if len(out) < 4000 else out[:2000] + "\n...[truncated]...\n" + out[-2000:]
        log(f"stdout:\n{snippet}")
    if err:
        snippet = err if len(err) < 4000 else err[:2000] + "\n...[truncated]...\n" + err[-2000:]
        log(f"stderr:\n{snippet}")
    log(f"exit code: {code}")
    return code, out, err


def sftp_upload(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    parts = remote.split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = posixpath.join(cur, p) if cur else "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
    sftp.put(local, remote)
    log(f"uploaded: {local} -> {remote}")


def main() -> int:
    ssh = make_ssh()
    try:
        sftp = ssh.open_sftp()
        try:
            log("== Step 1: SFTP upload changed files ==")
            for rel in FILES_TO_UPLOAD:
                local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
                if not os.path.exists(local):
                    log(f"WARN: local file missing: {local}")
                    continue
                remote = posixpath.join(REMOTE_DIR, rel)
                sftp_upload(sftp, local, remote)
        finally:
            sftp.close()

        log("== Step 2: docker compose build h5-web backend ==")
        # 用 docker compose（v2）；--pull 可能拉取较慢，使用本地缓存即可
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose build backend h5-web 2>&1 | tail -200",
            timeout=1800,
        )
        if rc != 0:
            log("ERROR: docker compose build failed")
            return 1

        log("== Step 3: docker compose up -d ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose up -d backend h5-web 2>&1 | tail -50",
            timeout=600,
        )
        if rc != 0:
            log("ERROR: docker compose up failed")
            return 1

        log("== Step 4: wait services to be ready (25s) ==")
        time.sleep(25)

        log("== Step 5: copy and run pytest in backend container ==")
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/test_h5_basepath_pay_url_bugfix.py "
            f"{DEPLOY_ID}-backend:/app/tests/test_h5_basepath_pay_url_bugfix.py",
        )
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'cd /app && PROJECT_BASE_URL={PROJECT_BASE_URL} python -m pytest "
            f"tests/test_h5_basepath_pay_url_bugfix.py -v --tb=short 2>&1 | tail -120'",
            timeout=300,
        )
        if rc != 0:
            log("ERROR: pytest failed")
            return 2

        log("== Step 6: external URL checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            (f"{PROJECT_BASE_URL}/checkout", "200|308"),
            (f"{PROJECT_BASE_URL}/sandbox-pay?order_no=TEST&channel=alipay_h5", "200"),
            (f"{PROJECT_BASE_URL}/pay/success?orderId=1", "200|307|308"),
            (f"{PROJECT_BASE_URL}/login", "200|308"),
        ]
        all_ok = True
        for url, expect in url_checks:
            rc, out, err = run(
                ssh,
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'",
                timeout=30,
            )
            code_str = (out or "").strip()
            if code_str in expect.split("|"):
                log(f"OK  {code_str:>4}  {url}")
            else:
                log(f"FAIL {code_str:>4} (expect {expect})  {url}")
                all_ok = False

        log("== Step 7: regression check — pay_url 不再丢 basePath ==")
        # 用容器内 python 单元粒度复跑 _build_sandbox_pay_url（不依赖 DB）
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"\"cd /app && PROJECT_BASE_URL={PROJECT_BASE_URL} python -c \\\"from app.api.unified_orders import _build_sandbox_pay_url; "
            f"u=_build_sandbox_pay_url('TESTORDER','alipay_h5'); "
            f"print('PAY_URL=' + str(u)); "
            f"assert u and 'autodev/{DEPLOY_ID}/sandbox-pay' in u, 'BasePath missing in pay_url: '+str(u); "
            f"print('REGRESSION OK')\\\"\"",
            timeout=60,
        )
        if rc != 0 or "REGRESSION OK" not in out:
            log("ERROR: regression check failed — pay_url 未带 basePath")
            return 3

        if not all_ok:
            log("WARN: some URL checks failed (see above), but core regression passed")

        log("== Deploy DONE ==")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
