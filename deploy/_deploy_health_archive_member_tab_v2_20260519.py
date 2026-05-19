"""[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 健康档案页顶部成员 Tab V2 样式修复部署脚本。

改动范围（仅 H5 顶部成员 Tab）：
- 后端：
  - 新增 backend/app/utils/relation_badge.py（关系→徽章字映射，PRD §2.2，含 儿/女 拆分）
  - backend/app/api/family.py：list/add/get/put 返回带 avatar_color_index/relation_badge_char/guard_status；
    新增成员时按 count % 5 分配 avatar_color_index
  - backend/app/api/health_archive_optim_v2.py：徽章映射统一转发到 utils
  - backend/app/schemas/user.py：FamilyMemberResponse 扩展三个可选字段
  - backend/tests/test_health_archive_member_tab_v2_20260519.py（新增 6 用例）
- H5：
  - h5-web/src/app/health-profile/page.tsx：renderMemberBar 完整重写为 PRD V2 样式
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

FILES = [
    # 后端
    ("backend/app/utils/relation_badge.py", "backend/app/utils/relation_badge.py"),
    ("backend/app/api/family.py", "backend/app/api/family.py"),
    ("backend/app/api/health_archive_optim_v2.py", "backend/app/api/health_archive_optim_v2.py"),
    ("backend/app/schemas/user.py", "backend/app/schemas/user.py"),
    ("backend/tests/test_health_archive_member_tab_v2_20260519.py",
     "backend/tests/test_health_archive_member_tab_v2_20260519.py"),
    # H5
    ("h5-web/src/app/health-profile/page.tsx", "h5-web/src/app/health-profile/page.tsx"),
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
        for local_rel, remote_rel in FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1", ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # 同步 backend 改动到容器
        print("\n--- 同步 backend 改动到容器 ---")
        backend_files = [
            ("backend/app/utils/relation_badge.py", "/app/app/utils/relation_badge.py"),
            ("backend/app/api/family.py", "/app/app/api/family.py"),
            ("backend/app/api/health_archive_optim_v2.py", "/app/app/api/health_archive_optim_v2.py"),
            ("backend/app/schemas/user.py", "/app/app/schemas/user.py"),
            ("backend/tests/test_health_archive_member_tab_v2_20260519.py",
             "/app/tests/test_health_archive_member_tab_v2_20260519.py"),
        ]
        for local_p, container_p in backend_files:
            run(
                client,
                f"docker cp {PROJ_DIR}/{local_p} {backend_container}:{container_p} 2>&1",
                ignore_err=True,
                show=False,
            )

        print("\n--- 重启 backend ---")
        run(client, f"docker restart {backend_container} 2>&1 | tail -5", ignore_err=True, timeout=120)

        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(40):
            rc, out, _ = run(
                client,
                "curl -ks -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi: {s}")
            if s == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready within timeout")

        # rebuild h5-web（page.tsx 改动需要 next build）
        print("\n--- rebuild h5-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -100", timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 5}s] h5-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client, f"docker logs --tail 40 {h5_container} 2>&1 | tail -25",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    break
            time.sleep(5)

        # smoke 访问
        print("\n--- smoke ---")
        base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for url in [
            f"{base_url}/api/openapi.json",
            f"{base_url}/health-profile",
            f"{base_url}/api/family/members",  # 未鉴权应 401，证明路由可达
            f"{base_url}/api/family-archive-v2/members",
        ]:
            rc, out, _ = run(client, f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                             ignore_err=True, show=False)
            print(f"  {url} -> {out.strip()}")

        # 容器内 pytest 回归
        print("\n--- backend pytest（容器内，本次新增 6 用例 + 既有 V2 10 用例） ---")
        run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_health_archive_member_tab_v2_20260519.py "
            f"tests/test_health_archive_optim_v2_20260518.py "
            f"-v --tb=short 2>&1 | tail -80",
            ignore_err=True,
            timeout=300,
        )

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
