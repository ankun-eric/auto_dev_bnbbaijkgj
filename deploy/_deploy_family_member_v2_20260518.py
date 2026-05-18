"""[PRD-FAMILY-MEMBER-V2 2026-05-18] 部署脚本

仅 H5 + 小程序改动（无后端文件改动）。
- 上传 h5-web 变更文件 + 重建 h5-web 容器
- 上传小程序变更文件（小程序通过 zip 包分发给用户，无需在服务器重启）
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    # H5-web
    ("h5-web/src/lib/family-relation.ts",
     "h5-web/src/lib/family-relation.ts"),
    ("h5-web/src/components/family/MemberBadge.tsx",
     "h5-web/src/components/family/MemberBadge.tsx"),
    ("h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
     "h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx"),
    ("h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
     "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx"),
    ("h5-web/src/app/health-profile/page.tsx",
     "h5-web/src/app/health-profile/page.tsx"),
    # 小程序
    ("miniprogram/app.json", "miniprogram/app.json"),
    ("miniprogram/pages/family-member-add/index.json",
     "miniprogram/pages/family-member-add/index.json"),
    ("miniprogram/pages/family-member-add/index.js",
     "miniprogram/pages/family-member-add/index.js"),
    ("miniprogram/pages/family-member-add/index.wxml",
     "miniprogram/pages/family-member-add/index.wxml"),
    ("miniprogram/pages/family-member-add/index.wxss",
     "miniprogram/pages/family-member-add/index.wxss"),
    # 后端测试
    ("backend/tests/test_family_member_v2_20260518.py",
     "backend/tests/test_family_member_v2_20260518.py"),
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

        # 同步测试文件到 backend 容器
        print("\n--- 同步 backend 测试文件到容器 ---")
        run(
            client,
            f"docker cp {PROJ_DIR}/backend/tests/test_family_member_v2_20260518.py "
            f"{backend_container}:/app/tests/test_family_member_v2_20260518.py 2>&1",
            ignore_err=True,
        )

        # 重建 h5-web
        print("\n--- rebuild h5-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (5-10 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -100", timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        # 等 h5-web
        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i+1)*5}s] h5-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client,
                    f"docker logs --tail 40 {h5_container} 2>&1 | tail -25",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    print("  h5-web ready.")
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke 测试 ---")
        for url in [
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/openapi.json",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile",
        ]:
            rc, out, _ = run(client, f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                             ignore_err=True, show=False)
            print(f"  {url} -> {out.strip()}")

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
