#!/usr/bin/env python3
"""[2026-05-05] 支付宝 SDK 复发诊断脚本（L0）。

逐条打印诊断信息：
1) backend 容器与镜像状态
2) 容器内 alipay/wechat 等 pip 包是否存在
3) 容器内 requirements.txt 是否包含 python-alipay-sdk
4) 镜像创建时间
5) 多端 SDK 健康抽测（alipay/wechatpy/aliyunsdkcore/tencentcloud/oss2/cos）
"""
from __future__ import annotations

import sys

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
        # 1) 容器/镜像
        run(ssh, f'docker ps -a --filter name={PROJECT_ID} --format "table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}"')
        run(ssh, f'docker inspect {BACKEND_NAME} --format "Created={{{{.Created}}}} Image={{{{.Image}}}}"')

        # 2) backend pip 列表
        run(ssh, f'docker exec {BACKEND_NAME} pip list 2>/dev/null | grep -iE "alipay|wechat|tencentcloud|aliyun|oss2|cos-python" || echo "[NO_MATCH]"')

        # 3) requirements.txt
        run(ssh, f'docker exec {BACKEND_NAME} sh -c "grep -i alipay /app/requirements.txt 2>/dev/null || cat /app/requirements.txt 2>/dev/null | head -30"')

        # 4) 项目目录 git 状态
        run(ssh, f'cd {PROJECT_DIR} && git log --oneline -5 2>/dev/null')
        run(ssh, f'grep -i alipay {PROJECT_DIR}/backend/requirements.txt')

        # 5) 多端 SDK 抽测
        run(ssh, f"""docker exec {BACKEND_NAME} python -c "
import importlib
for m in ['alipay','wechatpy','aliyunsdkcore','tencentcloud','jpush','oss2','qcloud_cos','cos']:
    try:
        importlib.import_module(m); print('[OK]   ', m)
    except Exception as ex:
        print('[MISS] ', m, '->', ex)
" """)

        # 6) 业务侧 import alipay
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from alipay import AliPay; print(\\"alipay sdk ok\\")" 2>&1 || echo "[ALIPAY_IMPORT_FAILED]"')

    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
