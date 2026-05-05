#!/usr/bin/env python3
"""[2026-05-05 营业管理入口收敛 PRD v1.0] 部署后远程验证 v3

聚焦：HTTP 链接通过 https + -k（忽略自签证书）访问。
"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{PROJECT_ID}-backend"
ADMIN = f"{PROJECT_ID}-admin"


def run(ssh, cmd, timeout=900):
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


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # https + 跟随 + 忽略证书
        base = f"https://{HOST}/autodev/{PROJECT_ID}"
        urls = [
            f"{base}/api/health",
            f"{base}/admin/",
            f"{base}/admin/login",
            f"{base}/admin/merchant/stores",
            f"{base}/admin/merchant/business-config",
            f"{base}/admin/product-system/products",
            f"{base}/api/merchant/stores/1/booking-config",
            f"{base}/api/merchant/concurrency-limit?store_id=1",
        ]
        for u in urls:
            run(
                ssh,
                "curl -k -L -s -o /dev/null -w 'final=%{url_effective} code=%{http_code}\\n' '"
                + u
                + "'",
            )
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
