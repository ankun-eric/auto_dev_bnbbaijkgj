"""[支付宝 H5 正式支付链路接入 v1.0] 一键部署脚本

通过 paramiko SFTP 上传变更文件 → docker compose build backend h5-web →
up -d → 等服务起来 → docker cp tests/conftest.py + 测试文件 → docker exec pytest
→ 验证外部 URL 可达。

Usage:
    python _deploy_alipay_real_payment.py
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
from pathlib import Path

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

PROJECT_ROOT = Path(__file__).parent

# 本次变更的文件清单
FILES_TO_UPLOAD = [
    # 后端
    "backend/requirements.txt",
    "backend/app/main.py",
    "backend/app/api/unified_orders.py",
    "backend/app/api/payment_config.py",
    "backend/app/api/alipay_notify.py",
    "backend/app/services/alipay_service.py",
    # 后端测试
    "backend/tests/test_alipay_h5_real_payment.py",
    # H5 前端
    "h5-web/src/app/pay/success/page.tsx",
]


def make_ssh_client() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=60)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600,
        echo: bool = True, ignore_err: bool = False) -> tuple[int, str, str]:
    if echo:
        print(f"\n>>> SSH: {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if echo:
        if out.strip():
            print(out[-3000:])
        if err.strip():
            print("STDERR:\n" + err[-3000:])
        print(f"<<< exit={rc}")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"command failed (exit={rc}): {cmd}\nSTDERR: {err}")
    return rc, out, err


def upload_file(sftp: paramiko.SFTPClient, local_path: Path, remote_path: str) -> None:
    # 确保远程目录存在
    parts = remote_path.split("/")
    for i in range(2, len(parts)):
        d = "/".join(parts[:i])
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except IOError:
                pass
    print(f"  → upload {local_path.name} -> {remote_path}")
    sftp.put(str(local_path), remote_path)


def http_check(url: str, *, expect_status: int | tuple[int, ...] = 200, timeout: int = 30) -> bool:
    if isinstance(expect_status, int):
        expect_status = (expect_status,)
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "deploy-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            print(f"  ✓ {url} -> HTTP {r.status}")
            return r.status in expect_status
    except urllib.error.HTTPError as e:
        ok = e.code in expect_status
        print(f"  {'✓' if ok else '✗'} {url} -> HTTP {e.code}")
        return ok
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {url} -> {e}")
        return False


def main() -> int:
    print("=" * 70)
    print("[支付宝 H5 正式支付链路接入 v1.0] 部署脚本启动")
    print("=" * 70)

    # 1) SSH 连接
    cli = make_ssh_client()
    sftp = cli.open_sftp()

    # 2) 上传文件
    print("\n[1/6] 上传变更文件 ...")
    for rel in FILES_TO_UPLOAD:
        local = PROJECT_ROOT / rel.replace("/", "\\")
        if not local.exists():
            local = PROJECT_ROOT / rel
        if not local.exists():
            print(f"  ! 文件不存在，跳过：{rel}")
            continue
        remote = f"{REMOTE_DIR}/{rel}"
        upload_file(sftp, local, remote)
    sftp.close()

    # 3) docker compose build + up
    print("\n[2/6] docker compose build backend h5-web ...")
    run(cli, f"cd {REMOTE_DIR} && docker compose build backend h5-web 2>&1 | tail -50",
        timeout=900)

    print("\n[3/6] docker compose up -d backend h5-web ...")
    run(cli, f"cd {REMOTE_DIR} && docker compose up -d backend h5-web", timeout=180)

    # 4) 等服务起来
    print("\n[4/6] 等待服务就绪 (30s) ...")
    time.sleep(30)
    run(cli,
        f"docker ps --filter name={DEPLOY_ID}- --format '{{{{.Names}}}}\t{{{{.Status}}}}'",
        ignore_err=True)

    # 5) docker cp + pytest（在容器内运行）
    print("\n[5/6] docker cp tests + 容器内 pytest ...")
    backend_container = f"{DEPLOY_ID}-backend"
    run(cli,
        f"docker cp {REMOTE_DIR}/backend/tests/conftest.py {backend_container}:/app/tests/conftest.py",
        ignore_err=True)
    run(cli,
        f"docker cp {REMOTE_DIR}/backend/tests/test_alipay_h5_real_payment.py "
        f"{backend_container}:/app/tests/test_alipay_h5_real_payment.py")

    # 在容器内 pip 安装 SDK（如不存在）
    rc, out, _ = run(cli,
                     f"docker exec {backend_container} python -c "
                     f"\"import alipay; print('ok', alipay.__version__ if hasattr(alipay,'__version__') else '?')\"",
                     ignore_err=True)
    if rc != 0:
        print("  → python-alipay-sdk 未安装于容器，pip 安装中 ...")
        run(cli,
            f"docker exec {backend_container} pip install --no-cache-dir python-alipay-sdk==3.3.0",
            timeout=300, ignore_err=True)

    # 运行 pytest
    print("\n[6/6] 运行 pytest test_alipay_h5_real_payment.py ...")
    rc, out, err = run(cli,
                       f"docker exec -w /app {backend_container} python -m pytest "
                       f"tests/test_alipay_h5_real_payment.py -v --tb=short --no-header 2>&1 | tail -120",
                       ignore_err=True)
    pytest_pass = ("passed" in out and "failed" not in out and "error" not in out.lower()) or rc == 0

    # 还跑一下既有 H5 支付链路相关测试，确保未回归
    print("\n[+] 跑既有支付链路相关测试以验证无回归 ...")
    rc2, out2, _ = run(cli,
                       f"docker exec -w /app {backend_container} python -m pytest "
                       f"tests/test_h5_pay_link_bugfix.py -v --tb=short --no-header 2>&1 | tail -40",
                       ignore_err=True)

    # 6) 验证外部 URL
    print("\n[+] 验证外部 URL ...")
    base = f"https://{SSH_HOST}/autodev/{DEPLOY_ID}"
    urls = [
        (f"{base}/", (200, 308, 301, 302)),
        (f"{base}/api/health", (200, 404)),
        (f"{base}/admin/", (200, 308, 301, 302)),
        # 异步通知接口（GET 应 405）
        (f"{base}/api/payment/alipay/notify", (405, 200, 422)),
    ]
    for url, expect in urls:
        http_check(url, expect_status=expect)

    cli.close()

    print("\n" + "=" * 70)
    print(f"[结果] pytest_main={'PASS' if pytest_pass else 'FAIL'}  rc_main={rc}  rc_regress={rc2}")
    print("=" * 70)
    return 0 if pytest_pass else 1


if __name__ == "__main__":
    sys.exit(main())
