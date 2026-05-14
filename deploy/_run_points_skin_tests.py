# -*- coding: utf-8 -*-
"""仅运行 PRD-POINTS-SKIN-V1 的服务器自动化测试（不重建 / 不部署）。"""
import sys
import paramiko

sys.path.insert(0, "./deploy")
from _deploy_points_skin_v1 import HOST, PORT, USER, PASSWORD, run_tests  # noqa


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting {USER}@{HOST}:{PORT} ...")
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        run_tests(ssh)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
