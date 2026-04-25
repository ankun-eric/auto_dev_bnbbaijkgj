"""[2026-04-25] PRD V1.0 链接最终验证（跟随重定向）"""
from __future__ import annotations

import sys

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://localhost/autodev/{DEPLOY_ID}"


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PASS, timeout=30)
    try:
        for path, name in [
            ("/", "h5_root"),
            ("/login", "login"),
            ("/merchant/login", "merchant_pc_login"),
            ("/merchant/profile", "merchant_pc_profile"),
            ("/merchant/store-settings", "merchant_pc_store"),
            ("/merchant/m/profile", "merchant_h5_profile"),
            ("/merchant/m/store-settings", "merchant_h5_store"),
            ("/merchant/m/me", "merchant_h5_me"),
        ]:
            cmd = (
                f"curl -ILks --max-redirs 5 -o /dev/null "
                f"-w '{name}: status=%{{http_code}} redirects=%{{num_redirects}} final=%{{url_effective}}\\n' "
                f"{BASE}{path}"
            )
            _stdin, stdout, _ = c.exec_command(cmd, timeout=15)
            print(stdout.read().decode("utf-8", errors="replace"), flush=True)

        for path, name in [
            ("/api/health", "api_health"),
            ("/api/merchant/profile", "api_merchant_profile"),
            ("/api/merchant/shop/info", "api_merchant_shop"),
        ]:
            cmd = (
                f"curl -sk -o /dev/null "
                f"-w '{name}: status=%{{http_code}}\\n' "
                f"{BASE}{path}"
            )
            _stdin, stdout, _ = c.exec_command(cmd, timeout=15)
            print(stdout.read().decode("utf-8", errors="replace"), flush=True)

        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
