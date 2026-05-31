#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将会员中心优化测试文件部署到后端容器并执行 pytest。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{PID}-backend"
TEST_FILE = "backend/tests/test_member_center_optim_v1_20260531.py"
REMOTE_TMP = "/tmp/test_member_center_optim_v1_20260531.py"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)

    def run(cmd, timeout=300):
        print(f"\n$ {cmd}")
        _, out, err = ssh.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", errors="ignore")
        e = err.read().decode("utf-8", errors="ignore")
        if o:
            print(o.rstrip())
        if e.strip():
            print("STDERR:", e.rstrip())
        return o, e

    # 上传测试文件到服务器
    sftp = ssh.open_sftp()
    sftp.put(TEST_FILE, REMOTE_TMP)
    sftp.close()
    print(">>> uploaded test file")

    # 确认后端容器测试目录
    run(f"docker exec {BE} sh -c 'ls /app/tests/ | head -20'")
    # 复制测试文件到容器
    run(f"docker cp {REMOTE_TMP} {BE}:/app/tests/test_member_center_optim_v1_20260531.py")
    run(f"rm -f {REMOTE_TMP}")
    # 跑该测试
    run(
        f"docker exec {BE} sh -c 'cd /app && python -m pytest tests/test_member_center_optim_v1_20260531.py -v 2>&1 | tail -40'",
        timeout=300,
    )
    ssh.close()


if __name__ == "__main__":
    main()
