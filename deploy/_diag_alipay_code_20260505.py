#!/usr/bin/env python3
"""[2026-05-05] 进一步诊断：服务器容器内的 alipay_service.py 实际代码状态。"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
BACKEND_NAME = f"{PROJECT_ID}-backend"


def run(ssh, cmd, timeout=180):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"[exit_code={rc}]")
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 容器内 alipay_service.py 是否含 AliPayCert 顶部 import 之类
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "head -50 /app/app/services/alipay_service.py 2>&1 || echo NO_FILE"')
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "grep -nE \'AliPayCert|未安装 python-alipay-sdk\' /app/app/services/alipay_service.py 2>&1"')
        # 测试接口路径
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "grep -rnE \'未安装 python-alipay-sdk|alipay_service\' /app/app/api/ 2>&1 | head -30"')
        # 是否 payment_config 中也有支付宝 H5 测试接口
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "grep -nE \'def.*test|alipay|wap_pay\' /app/app/api/payment_config.py 2>&1 | head -50"')
        # 最近 backend 日志
        run(ssh, f'docker logs --tail 60 {BACKEND_NAME} 2>&1 | tail -60')
        # 主机代码 vs 容器代码差异
        run(ssh, f'cd {PROJECT_DIR} && git log --oneline -5 backend/app/services/alipay_service.py 2>/dev/null || echo NO_FILE')
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "wc -l /app/app/services/alipay_service.py && md5sum /app/app/services/alipay_service.py"')
        run(ssh, f'wc -l {PROJECT_DIR}/backend/app/services/alipay_service.py 2>/dev/null && md5sum {PROJECT_DIR}/backend/app/services/alipay_service.py 2>/dev/null')
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    main()
