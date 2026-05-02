# -*- coding: utf-8 -*-
"""仅做 URL 自检，不重新部署。"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

PUBLIC = [
    ("/api/health", {"200"}),
    ("/admin/login", {"200", "308"}),
    ("/admin/product-system/coupons", {"200", "308"}),
]
PROTECTED = [
    "/api/admin/coupons/type-descriptions",
    "/api/admin/coupons/scope-limits",
    "/api/admin/coupons/category-tree",
    "/api/admin/coupons/product-picker",
    "/api/admin/coupons/active-product-count",
    "/api/admin/coupons/category-product-count?category_ids=1",
    "/api/admin/coupons/categories-by-ids?ids=1",
]


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PASS, timeout=30)
    fails = []
    try:
        for path, allow in PUBLIC:
            url = f"https://localhost/autodev/{DEPLOY_ID}{path}"
            _i, o, _e = c.exec_command(f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", timeout=20)
            code = (o.read().decode().strip() or "000").split()[-1]
            ok = code in allow
            print(f"  [{code}] PUBLIC {path} {'OK' if ok else 'FAIL'}")
            if not ok:
                fails.append((path, code))
        for path in PROTECTED:
            url = f"https://localhost/autodev/{DEPLOY_ID}{path}"
            _i, o, _e = c.exec_command(f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", timeout=20)
            code = (o.read().decode().strip() or "000").split()[-1]
            ok = code in {"401", "403"}
            print(f"  [{code}] PROTECTED {path} {'OK' if ok else 'FAIL'}")
            if not ok:
                fails.append((path, code))
    finally:
        c.close()
    if fails:
        print(f"\n[FAIL] {len(fails)} 项失败：{fails}")
        raise SystemExit(2)
    print("\n== ALL OK ==")


if __name__ == "__main__":
    main()
