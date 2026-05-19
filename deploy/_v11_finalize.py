"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 最终修复：
1) 上传新的 init_data.py（移除 3 条废弃 KV 的默认值）
2) docker cp 到容器内
3) 手动 DELETE 残留的 3 条 KV
4) 重启 backend 验证不再被 init_default_data 重新插入
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
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=300, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}")
    _, out, err = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    out_s = out.read().decode("utf-8", errors="replace")
    err_s = err.read().decode("utf-8", errors="replace")
    rc = out.channel.recv_exit_status()
    if show and out_s.strip():
        print(out_s[-3000:])
    if show and err_s.strip():
        print("STDERR:", err_s[-1500:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}")
    return rc, out_s, err_s


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    local_init_data = os.path.join(base, "backend", "app", "init_data.py")
    local_finalize_inner = os.path.abspath(
        os.path.dirname(__file__) + os.sep + "_v11_finalize_inner.py"
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        remote_init = f"{PROJ_DIR}/backend/app/init_data.py"
        print(f"upload: {remote_init}")
        sftp.put(local_init_data, remote_init)

        remote_finalize = "/tmp/_v11_finalize_inner.py"
        sftp.put(local_finalize_inner, remote_finalize)
        sftp.close()

        # docker cp init_data.py 到容器
        run(client,
            f"docker cp {remote_init} {BACKEND_CONTAINER}:/app/app/init_data.py",
            ignore_err=False)

        # docker cp finalize 脚本到容器
        run(client,
            f"docker cp {remote_finalize} {BACKEND_CONTAINER}:/tmp/_v11_finalize_inner.py",
            ignore_err=False)

        # 执行手动 DELETE
        print("\n--- 手动 DELETE 残留 KV ---")
        run(client,
            f"docker exec {BACKEND_CONTAINER} python /tmp/_v11_finalize_inner.py 2>&1",
            timeout=120)

        # 重启 backend，确保新 init_data.py 生效
        print("\n--- 重启 backend ---")
        run(client, f"docker restart {BACKEND_CONTAINER}", timeout=180)

        # 等待 + 再次验证
        print("\n--- 等待 backend 就绪 ---")
        for i in range(40):
            rc, out, _ = run(
                client,
                "curl -ks -o /dev/null -w '%{http_code}' "
                f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/openapi.json "
                "|| echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            if s == "200":
                print(f"  ready @ {(i+1)*3}s")
                break
            time.sleep(3)

        # 再次 DB 验证
        print("\n--- 再次 DB 验证 ---")
        run(client,
            f"docker exec {BACKEND_CONTAINER} python /tmp/_v11_db_verify_inner.py 2>&1",
            timeout=60, ignore_err=True)

        print("\n✅ 最终化完成")
    finally:
        client.close()


if __name__ == "__main__":
    main()
