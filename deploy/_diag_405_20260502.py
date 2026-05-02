# -*- coding: utf-8 -*-
"""诊断 v2.2 优惠券新接口在远程容器上 405 的根因。"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def run(c, cmd, timeout=60):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err.strip():
        print("STDERR:", err[-1500:])


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    try:
        run(c, f"cd /home/ubuntu/{DEPLOY_ID} && git log -1 --oneline")
        run(c, f"cd /home/ubuntu/{DEPLOY_ID} && grep -n -E 'router\\.(get|put|post)' backend/app/api/coupons_admin.py | head -40")
        run(c, f"docker exec {BACKEND} grep -n -E 'router\\.(get|put|post)' /app/app/api/coupons_admin.py | head -40")
        run(c, f"docker exec {BACKEND} python -c \"from app.api.coupons_admin import router; [print(r.methods, r.path) for r in router.routes]\"")
        run(c, f"docker exec {BACKEND} curl -s -o /dev/null -w 'code=%{{http_code}}\\n' -X GET http://localhost:8000/api/admin/coupons/type-descriptions")
        run(c, f"docker exec {BACKEND} curl -s -o /dev/null -w 'code=%{{http_code}}\\n' -X GET http://localhost:8000/api/admin/coupons/scope-limits")
        run(c, f"docker exec {BACKEND} curl -s -i -X GET http://localhost:8000/api/admin/coupons/type-descriptions | head -20")
    finally:
        c.close()


if __name__ == "__main__":
    main()
