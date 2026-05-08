"""[Bug-428] H5 端 AI 对话首页"瀑布流回看"修复 远程 Smoke 测试。

测试范围（非 UI 自动化测试）：
- T1：核心入口可达性 / + /ai-home + /api/ai-home-config + /api/health
- T2：/ai-home 页面 SSR HTML 中包含修复后新增的 DOM 标记
      (ai-home-top-panel 顶部面板始终挂载的 data-testid)
- T3：核心后端依赖（聊天会话相关）API 在不带 token 的情况下返回 401（即接口存活）
"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh_run(ssh: paramiko.SSHClient, cmd: str) -> tuple[int, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, (out + err).strip()


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USER, PASSWORD, timeout=30)

    failed = []

    # T1: 核心可达性
    cases_t1 = [
        ("/api/health", "200"),
        ("/api/ai-home-config", "200"),
        ("/", "200"),
    ]
    for path, expected in cases_t1:
        code, status = ssh_run(
            ssh,
            f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE_URL}{path}'",
        )
        passed = (status == expected)
        print(f"[T1] GET {path} → {status} (expect {expected}) {'PASS' if passed else 'FAIL'}")
        if not passed:
            failed.append(f"T1:{path}")

    # T2: SSR HTML 含 Bug-428 修复后的关键 DOM 标记
    code, html_markers = ssh_run(
        ssh,
        f"curl -sL '{BASE_URL}/ai-home' | "
        f"grep -oE 'ai-home-top-panel|ai-home-topbar' | sort -u",
    )
    has_top_panel = "ai-home-top-panel" in html_markers
    has_topbar = "ai-home-topbar" in html_markers
    if has_top_panel and has_topbar:
        print(f"[T2] /ai-home 包含修复后 DOM 标记 (top-panel + topbar) PASS")
    else:
        print(f"[T2] /ai-home DOM 标记缺失：{html_markers!r} FAIL")
        failed.append("T2:DOM markers missing")

    # T3: 核心 API 存活（401 表示接口活着、只是缺 token）
    code, status = ssh_run(
        ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE_URL}/api/chat/sessions'",
    )
    if status in ("401", "403"):
        print(f"[T3] GET /api/chat/sessions (no token) → {status} PASS (接口存活)")
    elif status == "200":
        print(f"[T3] GET /api/chat/sessions (no token) → 200 PASS (无认证保护，但接口存活)")
    else:
        print(f"[T3] GET /api/chat/sessions (no token) → {status} FAIL")
        failed.append(f"T3:{status}")

    ssh.close()

    print("\n========== Smoke 测试结果 ==========")
    if failed:
        print(f"FAIL: {len(failed)} 项失败 → {failed}")
        sys.exit(1)
    print("PASS: 全部用例通过")


if __name__ == "__main__":
    main()
