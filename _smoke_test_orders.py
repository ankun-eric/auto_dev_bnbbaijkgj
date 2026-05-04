#!/usr/bin/env python3
"""[订单列表固定列与列宽优化 v1.0] 烟雾测试 — 在 backend 容器内直接 import 验证"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return c


def run(c, cmd, timeout=120):
    print(f"\n>>> {cmd[:300]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"--- EXIT {rc} ---")
    return rc, out


def main():
    c = make_ssh()

    # 1. 验证 schema 模块可以正常 import 且新增字段存在
    rc, out = run(
        c,
        f"docker exec -e PYTHONPATH=/app {BACKEND} python -c "
        f"\"from app.schemas.unified_orders import UnifiedOrderResponse; "
        f"fields = UnifiedOrderResponse.model_fields; "
        f"print('user_nickname' in fields, 'user_phone' in fields, 'total_quantity' in fields)\"",
    )
    assert "True True True" in out, f"schema 字段校验失败: {out}"

    # 2. 通过 host 上的 curl 调容器外暴露的 nginx 验证接口
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    rc, out = run(
        c,
        f"curl -s -o /dev/null -w '%{{http_code}}' '{base}/api/admin/orders/unified?page=1&page_size=5'",
    )
    print(f"  [admin orders unified, no auth] -> {out.strip()}")
    assert "401" in out, f"未鉴权请求应返回 401，实际: {out!r}"

    # 3. /api/health 通畅
    rc, out = run(c, f"curl -s '{base}/api/health'")
    print(f"  [health body] -> {out.strip()[:200]}")

    # 4. 检查 product_admin.py 模块可以正常 import（不要报语法/import 错）
    rc, out = run(
        c,
        f"docker exec -e PYTHONPATH=/app {BACKEND} python -c "
        f"\"from app.api import product_admin; print('product_admin OK')\"",
    )
    assert "product_admin OK" in out, f"product_admin import 失败: {out}"

    # 5. 检查 merchant.py 模块可以正常 import
    rc, out = run(
        c,
        f"docker exec -e PYTHONPATH=/app {BACKEND} python -c "
        f"\"from app.api import merchant; print('merchant OK')\"",
    )
    assert "merchant OK" in out, f"merchant import 失败: {out}"

    c.close()
    print("\n=== ALL SMOKE TESTS PASSED ===")


if __name__ == "__main__":
    main()
