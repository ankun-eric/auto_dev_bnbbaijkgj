#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[PRD-BP-DETAIL-OPTIMIZE-V1] 将新测试文件复制进 backend 容器并运行 pytest。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{PID}-backend"
LOCAL_TEST = "backend/tests/test_bp_detail_optimize_v1_20260531.py"
REMOTE_TMP = f"/tmp/test_bp_detail_optimize_v1_20260531.py"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    def run(cmd, timeout=600):
        print(f"$ {cmd}")
        _, out, err = ssh.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", errors="ignore")
        e = err.read().decode("utf-8", errors="ignore")
        if o:
            print(o.rstrip())
        if e:
            print("STDERR:", e.rstrip())
        return o, e

    sftp = ssh.open_sftp()
    sftp.put(LOCAL_TEST, REMOTE_TMP)
    sftp.close()
    print(">>> uploaded test file")

    run(f"docker cp {REMOTE_TMP} {BE}:/app/tests/test_bp_detail_optimize_v1_20260531.py")
    run(f"rm -f {REMOTE_TMP}")
    # 运行本次新测试 + 血糖/血压回归
    run(f"docker exec {BE} sh -c 'cd /app && python -m pytest tests/test_bp_detail_optimize_v1_20260531.py tests/test_glucose_card_optimize_v2.py -q -p no:warnings 2>&1 | tail -30'")
    ssh.close()


if __name__ == "__main__":
    main()
