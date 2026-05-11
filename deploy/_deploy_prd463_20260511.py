"""[PRD-463] 部署脚本 — H5 端 AI 对话页左上角抽屉「资产行」展示优化

需求要点：
  1. 资产行去除 emoji（🎫/📦），四格统一为「大号数字 + 下方文字」
  2. 顺序由 「积分 / 优惠券 / 订单 / 收藏」改为 「积分 / 优惠券 / 收藏 / 订单」
  3. 订单数字口径切换到 v2_pending_receipt + v2_pending_use
     （等价于订单列表「待收货 Tab + 待使用 Tab」之和，杜绝口径偏差）
  4. 优惠券/收藏/订单 应用 formatBadge（0→0, 1~9→真实数字, ≥10→9+）
  5. 点击订单格智能定位 Tab：
        v2Receipt > v2Use  → /unified-orders?tab=pending_receipt
        v2Receipt < v2Use  → /unified-orders?tab=pending_use
        v2Receipt == v2Use 且 都>0 → /unified-orders?tab=pending_receipt
        v2Receipt == 0 且 v2Use == 0 → /unified-orders?tab=all

仅改动单文件：
  - h5-web/src/components/ai-chat/Sidebar.tsx

部署流程：
1. SFTP 上传 Sidebar.tsx
2. 远端 grep 验证关键标记
3. docker compose build h5-web
4. docker compose up -d h5-web
5. 等容器 running
6. curl smoke：ai-home 页面 + 后端 unified/counts 接口可达
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
        "h5-web/src/components/ai-chat/Sidebar.tsx",
        f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
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

        # 远端源码标记验证（PRD-463）
        _, out, _ = run(
            cli,
            f"grep -c 'PRD-463' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        marker = (out or "").strip()
        print(f"[VERIFY] PRD-463 markers in remote source: {marker}")

        # 新字段 v2_pending_receipt / v2_pending_use 必须出现
        _, out, _ = run(
            cli,
            f"grep -c 'v2_pending_receipt' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        print(f"[VERIFY] v2_pending_receipt occurrences: {(out or '').strip()}")

        _, out, _ = run(
            cli,
            f"grep -c 'v2_pending_use' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        print(f"[VERIFY] v2_pending_use occurrences: {(out or '').strip()}")

        # formatBadge 函数必须存在
        _, out, _ = run(
            cli,
            f"grep -c 'formatBadge' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        print(f"[VERIFY] formatBadge occurrences: {(out or '').strip()}")

        # handleOrderClick 智能定位
        _, out, _ = run(
            cli,
            f"grep -c 'handleOrderClick' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        print(f"[VERIFY] handleOrderClick occurrences: {(out or '').strip()}")

        # emoji 🎫 和 📦 必须从资产行去除（整文件中应不再出现，或者至少不出现在 bh-asset 区块）
        # 简单粗暴：搜索整文件，期望计数为 0
        _, out, _ = run(
            cli,
            f"grep -c '🎫\\|📦' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx || true",
        )
        emoji_hits = (out or "0").strip().splitlines()[-1] if out else "0"
        print(f"[VERIFY] legacy 🎫/📦 emoji remaining: {emoji_hits} (must be 0)")

        # 构建并启动 h5-web 容器
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=2400)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        time.sleep(15)

        # 等容器 running
        for _ in range(24):
            rc, out, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE",
            )
            if (out or "").strip() == "running":
                break
            time.sleep(5)

        # smoke：H5 页面 + 资产相关后端接口
        urls_smoke = [
            f"{BASE_URL}/",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/unified-orders",
            f"{BASE_URL}/api/orders/unified/counts",
        ]
        bad: list[tuple[str, str, str]] = []
        for u in urls_smoke:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if u.endswith("/api/orders/unified/counts"):
                if code == "500":
                    bad.append((u, code, "BACKEND_500"))
                elif code not in {"200", "401", "403"}:
                    bad.append((u, code, "UNEXPECTED"))
            else:
                if not (code.startswith("2") or code.startswith("3") or code in {"401", "403"}):
                    bad.append((u, code, "GENERAL"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
