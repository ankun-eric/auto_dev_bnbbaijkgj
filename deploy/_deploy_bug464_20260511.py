"""[BUG-464] 部署脚本 — H5 端全局 Toast 勾图标与文字垂直错位修复

修复要点：
  1. 在 h5-web/src/app/globals.css 末尾追加全局 antd-mobile Toast 样式覆盖
  2. .adm-toast-mask .adm-toast-main-icon 改为 flex 列向居中
  3. 图标 + 文字 上下两行紧凑居中，gap 8px，整体视觉重心统一
  4. 全局一次性修复：所有 Toast.show({ icon: 'success'/'fail'/'loading', content }) 自动生效

仅改动单文件：
  - h5-web/src/app/globals.css

部署流程：
1. SFTP 上传 globals.css
2. 远端 grep 验证关键标记（BUG-464、adm-toast-main-icon、flex-direction: column）
3. docker compose build h5-web
4. docker compose up -d h5-web
5. 等容器 running
6. curl smoke：H5 首页 + ai-home + unified-orders + 几个常见 Toast 出现页面
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    (
        "h5-web/src/app/globals.css",
        f"{REMOTE_PROJ}/h5-web/src/app/globals.css",
    ),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[REMOTE] $ {cmd[:200]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f"[STDERR] {err[-2000:]}")
    return rc, out, err


def upload_files(cli: paramiko.SSHClient) -> None:
    sftp = cli.open_sftp()
    for local_rel, remote in FILES:
        local_path = LOCAL_ROOT / local_rel
        if not local_path.exists():
            print(f"[SKIP] local missing: {local_path}")
            continue
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}")
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)

        target = f"{REMOTE_PROJ}/h5-web/src/app/globals.css"

        _, out, _ = run(cli, f"grep -c 'BUG-464' {target}")
        print(f"[VERIFY] BUG-464 markers in remote globals.css: {(out or '').strip()}")

        _, out, _ = run(cli, f"grep -c 'adm-toast-main-icon' {target}")
        print(f"[VERIFY] adm-toast-main-icon selector occurrences: {(out or '').strip()}")

        _, out, _ = run(cli, f"grep -c 'flex-direction: column' {target}")
        print(f"[VERIFY] flex-direction: column occurrences: {(out or '').strip()}")

        _, out, _ = run(cli, f"grep -c 'rgba(0, 0, 0, 0.75)' {target}")
        print(f"[VERIFY] toast bg rgba occurrences: {(out or '').strip()}")

        _, out, _ = run(cli, f"grep -c 'border-radius: 12px' {target}")
        print(f"[VERIFY] border-radius 12px occurrences: {(out or '').strip()}")

        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=2400)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        time.sleep(15)

        for _ in range(24):
            rc, out, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE",
            )
            if (out or "").strip() == "running":
                break
            time.sleep(5)

        urls_smoke = [
            f"{BASE_URL}/",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/login",
            f"{BASE_URL}/unified-orders",
            f"{BASE_URL}/my-coupons",
            f"{BASE_URL}/health-profile",
        ]
        bad: list[tuple[str, str, str]] = []
        for u in urls_smoke:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if not (code.startswith("2") or code.startswith("3") or code in {"401", "403"}):
                bad.append((u, code, "GENERAL"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
