"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 修复 system_config → system_configs 表名后重新部署后端"""
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
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"

FILES = [
    ("backend/app/services/prd_legacy_home_cleanup_v11_migration.py",
     "backend/app/services/prd_legacy_home_cleanup_v11_migration.py"),
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}")
    _, out, err = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    out_s = out.read().decode("utf-8", errors="replace")
    err_s = err.read().decode("utf-8", errors="replace")
    rc = out.channel.recv_exit_status()
    if show and out_s.strip():
        print(out_s[-2500:])
    if show and err_s.strip():
        print("STDERR:", err_s[-1000:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}")
    return rc, out_s, err_s


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        for local_rel, remote_rel in FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"upload: {local_rel}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # docker cp 到容器内
        for local_p, _ in FILES:
            container_p = "/app/" + local_p.replace("backend/", "")
            run(client,
                f"docker cp {PROJ_DIR}/{local_p} {BACKEND_CONTAINER}:{container_p}",
                ignore_err=False, show=True)

        print("\n--- 重启 backend，重跑迁移 ---")
        run(client, f"docker restart {BACKEND_CONTAINER}", timeout=180)

        print("\n--- 等待 backend 就绪（curl backend 容器内 8000） ---")
        ready = False
        for i in range(40):
            rc, out, _ = run(
                client,
                f"docker exec {BACKEND_CONTAINER} curl -ks -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i+1)*3}s] {s}")
            if s == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready")

        # 查看迁移日志
        print("\n--- 迁移日志 ---")
        run(client,
            f"docker logs --tail 400 {BACKEND_CONTAINER} 2>&1 | grep -E 'prd_legacy_home_cleanup|legacy_home_cleanup' | tail -20",
            ignore_err=True, show=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
