"""验证 cards v2 后端核心 API 接口可达性（涵盖 401 鉴权拦截 = 已注册）"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 这些路径必须返回 200/401/422（说明路由已注册），404/502 表示路由未挂载
        endpoints = [
            ("GET", "/api/cards"),
            ("GET", "/api/products/1/savings-tip"),
            ("POST", "/api/cards/purchase"),
            ("POST", "/api/staff/cards/redeem"),
            ("POST", "/api/orders/unified/checkout"),
            ("GET", "/api/cards/me/renewable"),
            ("GET", "/api/admin/cards/dashboard/summary"),
            ("GET", "/api/cards/1/share-poster"),
            ("GET", "/api/cards/me/1/redemption-code/current"),
            ("POST", "/api/cards/me/1/redemption-code"),
            ("POST", "/api/cards/me/1/renew"),
            ("POST", "/api/orders/unified/1/pay-card"),
            ("POST", "/api/orders/unified/1/refund-card"),
            ("GET", "/api/cards/me/1/usage-logs"),
        ]
        ok, fail = 0, []
        for m, path in endpoints:
            url = BASE + path
            cmd = (
                f"curl -ksL -o /dev/null -w '%{{http_code}}' --max-time 15 "
                f"-X {m} -H 'Content-Type: application/json' -d '{{}}' '{url}'"
            )
            _, stdout, _ = ssh.exec_command(cmd, timeout=30)
            code = stdout.read().decode("utf-8", errors="ignore").strip().split()[-1]
            print(f"{m} {path} -> {code}")
            if code in ("200", "201", "401", "403", "422", "405"):
                ok += 1
            else:
                fail.append((m, path, code))
        print(f"\n通过: {ok}/{len(endpoints)}")
        if fail:
            print("失败:")
            for m, p, c in fail:
                print(f"  - {m} {p} -> {c}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
