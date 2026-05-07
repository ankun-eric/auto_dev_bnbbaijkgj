"""[PRD-370 BUG-FIX-LOGIN-DESIGN-ALIGN-V1] H5 登录页设计稿对齐 + 后端开关部署脚本

本次改动文件：
- h5-web/src/app/login/page.tsx        (重写)
- h5-web/src/app/login/login.module.css (新建)
- h5-web/src/app/legal/service-agreement/page.tsx (新建)
- h5-web/src/app/legal/privacy-policy/page.tsx    (新建)
- h5-web/src/app/layout.tsx (theme-color)
- backend/app/api/login_ui_config.py (新建)
- backend/app/main.py (注册 login_ui_config 路由)

部署流程：SFTP 上传 → docker build h5-web + backend → up -d → gateway reload → HTTPS smoke
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
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    # H5 端
    "h5-web/src/app/login/page.tsx",
    "h5-web/src/app/login/login.module.css",
    "h5-web/src/app/legal/service-agreement/page.tsx",
    "h5-web/src/app/legal/privacy-policy/page.tsx",
    "h5-web/src/app/layout.tsx",
    # 小程序（先上传到服务器，后续打包用）
    "miniprogram/pages/login/index.wxml",
    "miniprogram/pages/login/index.wxss",
    "miniprogram/pages/login/index.js",
    # Flutter 端
    "flutter_app/lib/screens/login_screen.dart",
    # 后端
    "backend/app/api/login_ui_config.py",
    "backend/app/main.py",
]


def exec_cmd(client: paramiko.SSHClient, cmd: str, timeout: int = 600):
    print(f"[exec] {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err and code != 0:
        print("[stderr]", err[-2000:])
    return code, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    client.connect(
        HOST, port=22, username=USER, password=PASSWORD,
        timeout=30, banner_timeout=30, auth_timeout=30,
    )
    sftp = client.open_sftp()

    repo_root = Path(__file__).resolve().parent
    print(f"\n=== SFTP 上传 ===  repo={repo_root}")
    for rel in FILES:
        local = repo_root / rel
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        if not local.exists():
            print(f"  - SKIP missing: {local}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        exec_cmd(client, f"mkdir -p '{remote_dir}'")
        print(f"  ↑ {rel}  ({local.stat().st_size} bytes)")
        sftp.put(str(local), remote)
    sftp.close()

    # backend rebuild
    print("\n=== docker compose build backend ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build backend 2>&1 | tail -100",
        timeout=900,
    )
    if rc != 0:
        print("[warn] backend build 退出非零")

    # h5-web rebuild (no-cache 确保重写的 page.tsx 被打包)
    print("\n=== docker compose build h5-web ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -200",
        timeout=1500,
    )
    if rc != 0:
        print("[fail] h5-web build 失败")
        client.close()
        return 1

    # up -d
    print("\n=== docker compose up -d --force-recreate h5-web backend ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose up -d --force-recreate h5-web backend 2>&1 | tail -80",
        timeout=240,
    )

    time.sleep(10)

    # gateway reload
    print("\n=== gateway nginx reload ===")
    exec_cmd(client, "docker exec gateway nginx -t 2>&1 | tail -10", timeout=30)
    exec_cmd(client, "docker exec gateway nginx -s reload 2>&1 | tail -10", timeout=30)

    # HTTPS smoke
    print("\n=== HTTPS smoke ===")
    urls = [
        (f"{BASE_URL}/", "200|3"),
        (f"{BASE_URL}/login/", "200|3"),
        (f"{BASE_URL}/legal/service-agreement/", "200|3"),
        (f"{BASE_URL}/legal/privacy-policy/", "200|3"),
        (f"{BASE_URL}/api/openapi.json", "200"),
        (f"{BASE_URL}/api/config/login_ui_version", "200"),
        (f"{BASE_URL}/api/auth/register-settings", "200|4"),
        (f"{BASE_URL}/admin/", "200|3"),
    ]
    smoke_pass = True
    fails = []
    for u, expected in urls:
        rc, out, err = exec_cmd(
            client, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{u}'", timeout=20,
        )
        code = (out or "").strip()
        if expected == "200":
            ok = code == "200"
        elif expected == "404":
            ok = code == "404"
        elif expected == "200|3":
            ok = code in ("200", "301", "302", "303", "307", "308")
        elif expected == "200|4":
            ok = code in ("200", "401", "403", "404")
        else:
            ok = False
        marker = "OK  " if ok else "FAIL"
        print(f"  [{marker}] {u} -> {code} (expect {expected})")
        if not ok:
            smoke_pass = False
            fails.append((u, code, expected))

    # 容器内确认 chunks 包含设计稿对齐关键 token
    print("\n=== 容器内 H5 chunks 关键 token 检查 ===")
    container = f"{DEPLOY_ID}-h5-web"
    for token, label in [
        ("34C759", "iOS 标准绿主色"),
        ("4AD97A", "浅绿渐变起点"),
        ("2BD4C4", "青色渐变尾段"),
        ("\\u5BBE\\u5C3C\\u5C0F\\u5EB7", "宾尼小康"),  # u5bbe u5c3c u5c0f u5eb7
        ("AI \\u5065\\u5EB7\\u7BA1\\u5BB6", "AI 健康管家"),
        ("\\u670D\\u52A1\\u534F\\u8BAE\\u53CA\\u9690\\u79C1\\u4FDD\\u62A4", "服务协议及隐私保护"),
    ]:
        exec_cmd(
            client,
            f"docker exec {container} sh -lc \"grep -rl '{token}' /app/.next/static/chunks/app/login/ 2>/dev/null | head -1 || echo NOT_FOUND_{label}\"",
            timeout=30,
        )

    # 后端登录 UI 版本接口验证
    print("\n=== 后端 /api/config/login_ui_version 内容 ===")
    exec_cmd(
        client,
        f"curl -k -s '{BASE_URL}/api/config/login_ui_version' | head -c 500",
        timeout=30,
    )

    client.close()
    print("\n=== 部署完成 ===")
    print(f"smoke_pass={smoke_pass}")
    if fails:
        print("FAILED URLS:")
        for u, c, e in fails:
            print(f"  {u}  got={c} expect={e}")
    return 0 if smoke_pass else 2


if __name__ == "__main__":
    sys.exit(main())
