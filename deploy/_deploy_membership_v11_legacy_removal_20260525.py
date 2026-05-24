"""[旧会员体系废弃与迁移 v1.1 2026-05-25] 部署脚本

本次新增/改动文件：
  backend/app/api/admin.py            - 旧 /points/levels API 标 @deprecated + warning 日志
  backend/app/api/points.py           - 旧 /points/level 公开 API 标 @deprecated + warning 日志
  backend/tests/test_membership_v1.py - 追加旧 API deprecated / 20% 上限 / 套餐购买禁止积分抵扣 测试
  h5-web/src/app/customer-service/page.tsx - 客服会员等级文案改为付费会员说明
  h5-web/src/app/checkout/page.tsx    - 收银台「会员折扣 + 积分抵扣」二选一 UI / 20% 上限
  h5-web/src/app/product/[id]/page.tsx- 商品类型新增 is_member_discount_eligible
  h5-web/src/lib/auth.ts              - 用户类型 memberLevel @deprecated
  miniprogram/pages/profile/index.js   - 个人中心加载付费会员套餐
  miniprogram/pages/profile/index.wxml - 个人中心展示付费会员套餐替代旧 memberLevel
  miniprogram/pages/member-card/index.js  - 会员卡加载付费会员套餐
  miniprogram/pages/member-card/index.wxml- 会员卡展示付费会员套餐替代旧 memberLevel
  miniprogram/pages/login/index.js     - formatMemberLevel 退化为空（不再生成历史标签）
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

BACKEND_FILES = [
    "backend/app/api/admin.py",
    "backend/app/api/points.py",
    "backend/tests/test_membership_v1.py",
]

H5_FILES = [
    "h5-web/src/app/customer-service/page.tsx",
    "h5-web/src/app/checkout/page.tsx",
    "h5-web/src/app/product/[id]/page.tsx",
    "h5-web/src/lib/auth.ts",
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def upload(sftp, client, local_abs, remote_abs):
    run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
    sftp.put(local_abs, remote_abs)


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        sftp = client.open_sftp()
        all_files = BACKEND_FILES + H5_FILES
        for rel in all_files:
            local_abs = os.path.join(base, rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{rel}"
            print(f"  upload: {rel}")
            upload(sftp, client, local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5-web"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"
        print(f"compose file: {compose_file}")

        # ── 1. backend：docker cp + restart ──
        print("\n--- docker cp backend 文件到容器 ---")
        for rel in BACKEND_FILES:
            host_abs = f"{PROJ_DIR}/{rel}"
            # backend/app/api/x.py -> /app/app/api/x.py；backend/tests/x.py -> /app/tests/x.py
            in_container = "/app/" + rel[len("backend/"):]
            run(client,
                f"docker cp '{host_abs}' '{backend_container}:{in_container}' 2>&1",
                ignore_err=True, show=False)

        print("\n--- 重启 backend 容器 ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart backend 2>&1 | tail -10",
            timeout=240, ignore_err=True)

        # 等待就绪
        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(80):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/api/openapi.json' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi -> {code}")
            if code == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready in 240s, continuing anyway")

        # 验证旧 API 已标 deprecated
        print("\n--- 端点验证：旧 points/levels API 已标 deprecated ---")
        run(client,
            f"curl -ks '{BASE_URL}/api/openapi.json' | "
            "python3 -c 'import json,sys; d=json.load(sys.stdin); paths=d[\"paths\"]; "
            "items=[(p, m, info.get(\"deprecated\", False)) "
            "for p, ms in paths.items() if (\"/points/level\" in p) "
            "for m, info in ms.items() if m in (\"get\",\"post\",\"put\",\"delete\")]; "
            "[print(p, m.upper(), \"deprecated=\", dep) for p, m, dep in items]' 2>&1 | tail -30",
            ignore_err=True)

        # 服务器内运行测试（含新增的 deprecated 测试）
        print("\n--- 服务器内运行 pytest（test_membership_v1） ---")
        run(client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_membership_v1.py -x --no-header -q 2>&1 | tail -80",
            timeout=300, ignore_err=True)

        # ── 2. h5-web rebuild ──
        print("\n--- rebuild h5-web ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3",
            ignore_err=True)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3",
            ignore_err=True)
        print("Building h5-web (5-10 min)...")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -120",
            timeout=1800)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] h5 / -> {code}")
            if code in ("200", "301", "302", "307", "308"):
                break
            time.sleep(3)

        # ── 3. 关键 URL 验证 ──
        print("\n--- 关键 URL 验证 ---")
        urls = [
            f"{BASE_URL}/api/openapi.json",
            f"{BASE_URL}/checkout",
            f"{BASE_URL}/customer-service",
            f"{BASE_URL}/admin",
        ]
        for u in urls:
            run(client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{u}' && echo '  <- {u}'",
                ignore_err=True, show=True)

        print("\nDEPLOY DONE.")
        print(f"H5: {BASE_URL}/")
        print(f"Admin: {BASE_URL}/admin")
    finally:
        client.close()


if __name__ == "__main__":
    main()
