#!/usr/bin/env python3
"""[2026-05-05] E2E 回归：管理员登录后访问 SDK 健康接口 + 重新检测接口 + 触发支付宝 H5 测试按钮。"""
from __future__ import annotations

import json
import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"


def run(ssh, cmd, timeout=120, ignore_err=False):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err[-500:]}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(cmd)
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 1) 登录拿 token
        run(ssh, (
            f'curl -sk -X POST {BASE}/api/admin/login '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"phone":"13800000000","password":"admin123"}}\' > /tmp/login.json'
        ))
        run(ssh, "cat /tmp/login.json")
        run(ssh, 'TOKEN=$(python3 -c "import json;print(json.load(open(\\"/tmp/login.json\\"))[\\"token\\"])"); echo "TOKEN_LEN=${#TOKEN}"')

        # 2) 调 /api/admin/health/sdk
        run(ssh, (
            'TOKEN=$(python3 -c "import json;print(json.load(open(\\"/tmp/login.json\\"))[\\"token\\"])"); '
            f'curl -sk -H "Authorization: Bearer $TOKEN" {BASE}/api/admin/health/sdk > /tmp/sdk.json; '
            'python3 -c "import json;d=json.load(open(\\"/tmp/sdk.json\\"));print(\\"summary=\\",d[\\"summary\\"]);'
            'print(\\"checked_at=\\",d.get(\\"checked_at\\"));'
            '[print(\\"  -\\",g,\\":\\",len(items),\\"items\\") for g,items in d[\\"groups\\"].items()]"'
        ))

        # 3) 调 /api/admin/health/sdk/refresh
        run(ssh, (
            'TOKEN=$(python3 -c "import json;print(json.load(open(\\"/tmp/login.json\\"))[\\"token\\"])"); '
            f'curl -sk -X POST -H "Authorization: Bearer $TOKEN" {BASE}/api/admin/health/sdk/refresh '
            '-w "\\n[HTTP %{http_code}]\\n" -o /tmp/refresh.json; '
            'python3 -c "import json;d=json.load(open(\\"/tmp/refresh.json\\"));print(\\"refresh ok=\\",d[\\"ok\\"], d[\\"summary\\"])"'
        ))

        # 4) 调 /api/admin/payment-channels/alipay_h5/test（核心回归）
        run(ssh, (
            'TOKEN=$(python3 -c "import json;print(json.load(open(\\"/tmp/login.json\\"))[\\"token\\"])"); '
            f'curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" '
            f'-d \'{{}}\' {BASE}/api/admin/payment-channels/alipay_h5/test '
            '-w "\\n[HTTP %{http_code}]\\n" > /tmp/test_alipay.txt 2>&1 || true; '
            'cat /tmp/test_alipay.txt'
        ))

    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
