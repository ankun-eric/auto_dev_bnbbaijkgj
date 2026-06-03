"""[Bug 修复 v1.0 · 会员中心入口与权益对比 2026-05-26] 部署脚本

涉及变更：
- h5-web/src/components/ai-chat/MoreMenu.tsx (金色 + 「新」角标)
- h5-web/src/components/ai-chat/Sidebar.tsx  (我的设备 → 会员中心)
- h5-web/src/app/member-center/page.tsx (集成权益对比表)
- h5-web/src/app/member-center/components/BenefitsCompareTable.tsx (新增)
- miniprogram/pages/ai/* (更多菜单)
- miniprogram/pages/member-center/* (新增 web-view 页面)
- miniprogram/app.json (注册路由)
- flutter_app/lib/screens/ai/ai_home_screen.dart (更多菜单)
- flutter_app/lib/screens/member/member_center_webview.dart (新增)
- flutter_app/lib/main.dart (注册路由)
- flutter_app/pubspec.yaml (webview_flutter)
- backend/tests/test_member_center_v2.py (新增 1 条测试)

部署：仅 H5 需要重新构建（其他端通过打包阶段处理）；同时跑 backend 单测验证后端兼容
"""
from __future__ import annotations

import sys
import tarfile
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
TS = int(time.time())
LOCAL_TAR = ROOT / f"bugfix_member_compare_{TS}.tar.gz"
REMOTE_TAR = f"/tmp/bugfix_member_compare_{TS}.tar.gz"


def make_tar() -> Path:
    print(f"[1] 打包变更到 {LOCAL_TAR.name}")
    paths = [
        # H5
        Path("h5-web/src/components/ai-chat/MoreMenu.tsx"),
        Path("h5-web/src/components/ai-chat/Sidebar.tsx"),
        Path("h5-web/src/app/member-center/page.tsx"),
        Path("h5-web/src/app/member-center/components/BenefitsCompareTable.tsx"),
        # backend tests
        Path("backend/tests/test_member_center_v2.py"),
    ]
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        for p in paths:
            abs_p = ROOT / p
            if abs_p.exists():
                tar.add(abs_p, arcname=str(p).replace("\\", "/"))
                print(f"    + {p}")
            else:
                print(f"    [WARN] missing: {p}")
    size_kb = LOCAL_TAR.stat().st_size / 1024
    print(f"    打包完成：{size_kb:.1f} KB")
    return LOCAL_TAR


def ssh_run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f"[ssh] $ {cmd[:160]}{'...' if len(cmd) > 160 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = (out + ("\n[stderr]\n" + err if err.strip() else ""))
    tail = "\n".join(combined.splitlines()[-60:])
    print(tail)
    print(f"[ssh] exit={rc}")
    return rc, combined


def main() -> None:
    make_tar()

    print(f"\n[2] SSH 连接 {HOST}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print(f"\n[3] 上传 {LOCAL_TAR.name} → {REMOTE_TAR}")
        sftp.put(str(LOCAL_TAR), REMOTE_TAR)
        print("    上传完成")

        ssh_run(client, f"cd {REMOTE_PROJECT_DIR} && tar xzf {REMOTE_TAR}")
        ssh_run(client, f"ls -la {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/MoreMenu.tsx")
        ssh_run(client, f"ls -la {REMOTE_PROJECT_DIR}/h5-web/src/app/member-center/components/BenefitsCompareTable.tsx")

        print(f"\n[4] backend pytest（验证后端兼容 + 新增对比表数据测试）")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_member_center_v2.py -v 2>&1 | tail -60'",
            timeout=300,
        )

        print(f"\n[5] 重新构建 h5-web")
        rc, _ = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -30",
            timeout=1200,
        )
        if rc == 0:
            ssh_run(
                client,
                f"cd {REMOTE_PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
                timeout=120,
            )

        # 等待 h5-web 就绪
        print("    等待 h5-web 健康……")
        for i in range(30):
            time.sleep(3)
            rc, out = ssh_run(
                client,
                f"curl -sk -o /dev/null -w '%{{http_code}}' '{BASE_URL}/member-center/' || echo 000",
                timeout=15,
            )
            code = out.strip()
            if "200" in code or "302" in code:
                print(f"    h5-web ready @ {(i + 1) * 3}s, status={code}")
                break

        print(f"\n[6] HTTP smoke 测试关键 URL")
        for path in [
            "/api/openapi.json",
            "/api/member/plans",
            "/member-center/",
            "/ai-home/",
        ]:
            ssh_run(
                client,
                f"curl -sk -o /dev/null -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=20,
            )

        print(f"\n[7] 校验 H5 build 产物是否包含权益对比组件 chunk")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-h5-web sh -c "
            f"'find /app/.next -name \"*.js\" 2>/dev/null | xargs grep -l \"BenefitsCompareTable\\|权益对比\" 2>/dev/null | head -5' || echo no-match",
            timeout=30,
        )

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()
        print("\n[Done] 部署流程结束")


if __name__ == "__main__":
    main()
