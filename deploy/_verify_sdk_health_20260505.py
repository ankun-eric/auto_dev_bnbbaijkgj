#!/usr/bin/env python3
"""[2026-05-05] 验证 SDK 健康看板部署后的实际可用性。

1) 通过 HTTPS 拉取 /api/health
2) 通过 admin login 获取 token，再请求 /api/admin/health/sdk
3) 模拟"测试支付宝H5"按钮（不依赖真实配置，只看是否还报"未安装 python-alipay-sdk"）
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import ssl

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
BACKEND_NAME = f"{PROJECT_ID}-backend"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"


def run(ssh, cmd, timeout=120, ignore_err=False):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err[-800:]}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}")
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    try:
        # 1) HTTPS 健康检查
        run(ssh, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' {BASE_URL}/api/health")

        # 2) /api/admin/health/sdk 鉴权前
        run(ssh, f"curl -sk -o /dev/null -w 'sdk_no_auth=%{{http_code}}\\n' {BASE_URL}/api/admin/health/sdk")

        # 3) 通过容器内 python 直接打 API（模拟 admin 登录）
        # 直接走 backend 容器内 import + 调用 endpoint 是最稳的方式
        # 也可以用 admin 登录拿 token 再 curl，但 admin 凭据未知；改为容器内调用 SDK 健康函数验证
        run(ssh, f'docker exec {BACKEND_NAME} python -c "import json; from app.core.sdk_health import get_snapshot; s=get_snapshot(); print(\\"core=\\", s[\\"summary\\"][\\"missing_core\\"], \\" optional=\\", s[\\"summary\\"][\\"missing_optional\\"]); [print(\\"missing\\",it[\\"key\\"],it[\\"install_cmd\\"]) for g in s[\\"groups\\"].values() for it in g if not it[\\"ok\\"]]"')

        # 4) 关键回归：模拟支付宝 H5 测试按钮的核心逻辑——加载 alipay_service 并发起一次 SDK import
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from app.services.alipay_service import _build_client_from_config; print(\\"alipay_service module loaded ok\\")"')

        # 5) 完整 backend 日志最后 50 行（看启动期 SDK-HEALTH 是否打印）
        run(ssh, f"docker logs {BACKEND_NAME} 2>&1 | grep -E 'SDK-HEALTH|sdk_health' | tail -30", ignore_err=True)
        run(ssh, f"docker logs {BACKEND_NAME} 2>&1 | tail -30")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
