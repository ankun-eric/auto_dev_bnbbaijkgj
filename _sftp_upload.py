#!/usr/bin/env python3
"""Upload changed files to remote via SFTP."""
import sys
import paramiko
import posixpath

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
REMOTE_BASE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

# Files changed in commit 4b48f72
FILES = [
    "admin-web/src/app/(admin)/merchant/stores/page.tsx",
    "backend/app/api/account_security.py",
    "backend/app/api/admin_merchant.py",
    "backend/app/api/product_admin.py",
    "backend/app/schemas/merchant.py",
    "backend/app/services/schema_sync.py",
    "backend/tests/test_h5_checkout_v1.py",
    "backend/tests/test_business_hours_scope_fix.py",
    "h5-web/src/app/merchant/m/store-settings/page.tsx",
    "h5-web/src/app/merchant/store-settings/page.tsx",
]


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    sftp = client.open_sftp()

    for rel in FILES:
        local = "C:/auto_output/bnbbaijkgj/" + rel
        remote = REMOTE_BASE + "/" + rel
        # Ensure remote dir exists
        d = posixpath.dirname(remote)
        # mkdir -p via shell
        client.exec_command(f"mkdir -p '{d}'")[1].channel.recv_exit_status()
        try:
            sftp.put(local, remote)
            print(f"OK  {rel}")
        except Exception as e:
            print(f"ERR {rel}: {e}")
    sftp.close()
    client.close()


if __name__ == "__main__":
    main()
