"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 通过 SFTP 上传 + docker cp + exec 验证 DB 迁移结果"""
from __future__ import annotations

import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=120):
    print(f"\n$ {cmd[:240]}")
    _, out, err = client.exec_command(cmd, timeout=timeout)
    out_s = out.read().decode("utf-8", errors="replace")
    err_s = err.read().decode("utf-8", errors="replace")
    if out_s.strip():
        print(out_s[-4000:])
    if err_s.strip():
        print("STDERR:", err_s[-1500:])
    return out_s


def main():
    local_script = os.path.abspath(
        os.path.dirname(__file__) + os.sep + "_v11_db_verify_inner.py"
    )
    assert os.path.exists(local_script), local_script

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)

    try:
        # 1) 上传到服务器 /tmp/
        sftp = client.open_sftp()
        remote_path = "/tmp/_v11_db_verify_inner.py"
        sftp.put(local_script, remote_path)
        sftp.close()
        print(f"uploaded: {remote_path}")

        # 2) docker cp 到容器内
        run(client,
            f"docker cp /tmp/_v11_db_verify_inner.py {BACKEND_CONTAINER}:/tmp/_v11_db_verify_inner.py",
            timeout=30)

        # 3) 执行
        run(client,
            f"docker exec {BACKEND_CONTAINER} python /tmp/_v11_db_verify_inner.py 2>&1",
            timeout=120)
    finally:
        client.close()


if __name__ == "__main__":
    main()
