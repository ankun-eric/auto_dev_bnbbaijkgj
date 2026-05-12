"""[PRD-469] 部署后路由校验：检测 308 后的真实状态码。"""
from __future__ import annotations

import urllib.parse
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run(cli, cmd, timeout=60):
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        urls = [
            "/health-profile-v2",
            "/health-profile-v2/",
            "/health-profile",
            "/health-profile/",
            "/api/prd469/family-member/relation-options",
            f"/api/prd469/medication-library/search?kw={urllib.parse.quote('阿')}",
            "/api/prd469/device/list",
        ]
        for u in urls:
            out, _ = run(cli, f"curl -k -L -s -o /dev/null -w '%{{http_code}} (final: %{{url_effective}})' '{BASE_URL}{u}'")
            print(f"{u:80s} -> {out.strip()}")

        # 看看 medication-library/search 中文是否真的能 200
        print("\n[search content check]")
        out, _ = run(cli, f"curl -k -L -s '{BASE_URL}/api/prd469/medication-library/search?kw={urllib.parse.quote('阿')}'")
        print(out[:500])

        # 看一下后端日志
        print("\n[backend tail]")
        out, _ = run(cli, f"docker logs --tail 30 {DEPLOY_ID}-backend 2>&1")
        print(out[-2000:])
    finally:
        cli.close()


if __name__ == "__main__":
    main()
