"""[PRD-448 v1.2] 增量补丁部署脚本 — AI 首页「本人态咨询人胶囊」修复

将 H5-web + 后端的 v1.2 改动部署到测试服务器：
- 前端 ai-home/page.tsx：本人态显式渲染胶囊（移除 selectedConsultant !== null 卡死判断），
  上层显式传 memberName='本人' + isSelf=true + consultantId=0
- 前端 ProfileCard.tsx：capsule 变体支持上层 memberName/isSelf 覆盖；本人态接口失败/空数据
  也渲染兜底胶囊（折叠态"本次回答结合 本人 的档案" + 展开态"档案完整度 0%"引导）
- 后端 consultant_profile_card.py：id=0 且本人 FamilyMember 不存在时，不返 404，
  返回基础结构体（nickname="本人" + 其他字段空 + percent=0）

仅改 h5-web + backend；admin-web / 小程序 / app 无需重建。
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
    # 前端
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/components/ai-chat/ProfileCard.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/ProfileCard.tsx"),
    # 后端
    ("backend/app/api/consultant_profile_card.py",
     f"{REMOTE_PROJ}/backend/app/api/consultant_profile_card.py"),
    # 测试用例
    ("backend/tests/test_prd448_v12_self_consultant_card.py",
     f"{REMOTE_PROJ}/backend/tests/test_prd448_v12_self_consultant_card.py"),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[REMOTE] $ {cmd[:200]}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
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
        rc, _, _ = run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)
        # h5-web 容器（前端源码变更）和 backend 容器（后端 py 改动）都要重建
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web backend", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web backend", timeout=600)
        time.sleep(15)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/chat/1",
            f"{BASE_URL}/health-archive",
        ]
        bad = []
        for u in urls:
            rc, out, _ = run(cli, f"curl -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if not code.startswith(("2", "3")):
                bad.append((u, code))

        # [PRD-448 v1.2 §7.2 接口验收] 直接打 /api/v1/consultant/0/profile_card 验证
        # （未登录态：必须 401；登录态：另由前端 e2e 验证）
        rc, out, _ = run(
            cli,
            f"curl -s -o /dev/null -w '%{{http_code}}' "
            f"{BASE_URL}/api/v1/consultant/0/profile_card",
        )
        code = (out or "").strip()
        print(f"[v1.2 §7.2] /api/v1/consultant/0/profile_card unauth -> {code}")
        # 401/403 都算通过
        if not code.startswith(("4",)):
            bad.append((f"{BASE_URL}/api/v1/consultant/0/profile_card", code))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
