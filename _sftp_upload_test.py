"""上传新增的 test_book_after_pay_bugfix.py 到服务器 backend 容器。

deploy_remote.py 的 EXCLUDES 包含 'tests'，会把项目内的 backend/tests 目录都过滤掉。
本脚本通过 SFTP 直接将测试文件复制到服务器，再 docker cp 到容器内。
"""

import paramiko
import os
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

LOCAL_FILES = [
    r"backend/tests/test_book_after_pay_bugfix.py",
]


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    for rel in LOCAL_FILES:
        local = os.path.join(os.getcwd(), rel.replace("/", os.sep))
        remote_tmp = f"/tmp/{os.path.basename(rel)}"
        print(f"Uploading {local} → {remote_tmp}")
        sftp.put(local, remote_tmp)
        cmd = f"docker cp {remote_tmp} {CONTAINER}:/app/tests/{os.path.basename(rel)}"
        print(f"$ {cmd}")
        _, sout, serr = ssh.exec_command(cmd, timeout=60)
        print(sout.read().decode("utf-8", errors="replace"))
        err = serr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR:", err)
        ssh.exec_command(f"rm -f {remote_tmp}")
    sftp.close()
    ssh.close()
    print("Upload complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
