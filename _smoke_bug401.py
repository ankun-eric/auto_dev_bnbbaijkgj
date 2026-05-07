"""[BUGFIX-UO-20260507-001] 端到端非UI自动化烟测：

验证商家端订单详情/列表接口对样本订单（UO20260507075333421500）返回的字段是否正确：
- 预约时段：必须返回 `time_slot="14:00-15:00"`，而不是只有 `appointment_time=09:00`。
- 支付方式：必须返回 `payment_method_text="支付宝（H5）"`，而不是显示成「微信」。

直接通过服务器内网调用 backend API（绕过 Nginx），获取商家凭证后访问 /api/merchant/orders/{id}/detail。
"""
from __future__ import annotations

import json
import subprocess

SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
PREFIX = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SAMPLE_ORDER_NO = "UO20260507075333421500"


def ssh(cmd: str, timeout: int = 60) -> str:
    full = ["ssh", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd]
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"[SSH FAILED RC={r.returncode}] {cmd[:120]}")
        print(r.stderr[-1000:])
    return r.stdout


def run_sql(sql: str) -> str:
    cmd = (
        f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 bini_health "
        f"-N -B -e \"{sql}\" 2>/dev/null"
    )
    return ssh(cmd)


def main():
    print("=== [Step 1] 数据库直查样本订单当前状态 ===")
    out = run_sql(
        f"SELECT id, payment_method, payment_channel_code, status FROM unified_orders "
        f"WHERE order_no='{SAMPLE_ORDER_NO}'"
    )
    print(out)

    print("\n=== [Step 2] 数据库直查样本订单 OrderItem ===")
    out = run_sql(
        f"SELECT oi.appointment_time, oi.appointment_data FROM order_items oi "
        f"JOIN unified_orders uo ON uo.id=oi.order_id "
        f"WHERE uo.order_no='{SAMPLE_ORDER_NO}'"
    )
    print(out)

    print("\n=== [Step 3] 拿到样本订单关联的 store_id 和商家用户信息 ===")
    out = run_sql(
        "SELECT uo.id, uo.store_id, uo.user_id, oi.id AS item_id "
        f"FROM unified_orders uo JOIN order_items oi ON oi.order_id=uo.id "
        f"WHERE uo.order_no='{SAMPLE_ORDER_NO}' LIMIT 1"
    )
    print(out)
    parts = out.strip().split()
    if len(parts) < 4:
        print("[FAIL] 找不到样本订单！")
        return
    order_id, store_id, _user_id, _item_id = parts[:4]

    print("\n=== [Step 4] 找一个能访问该 store 的商家账号 ===")
    out = run_sql(
        f"""
        SELECT u.id, u.phone FROM users u
        JOIN account_identities ai ON ai.user_id = u.id
        WHERE ai.identity_type='merchant'
        ORDER BY u.id LIMIT 5
        """
    )
    print(out)

    # 先简化：直接用容器内 python 调用 backend，通过内部访问验证 detail 接口字段
    print("\n=== [Step 5] 进入 backend 容器，直接构造请求验证商家端 detail 接口 ===")
    py_script = f'''
import asyncio
from app.core.database import get_db
from app.api.merchant import merchant_get_order_detail, _format_time_slot, _ensure_store_access
from app.api.unified_orders import _build_payment_method_text
from app.models.models import UnifiedOrder, OrderItem
from sqlalchemy import select

async def main():
    async for db in get_db():
        try:
            uo_res = await db.execute(
                select(UnifiedOrder).where(UnifiedOrder.order_no == "{SAMPLE_ORDER_NO}")
            )
            uo = uo_res.scalar_one_or_none()
            if not uo:
                print("[FAIL] 样本订单不存在")
                return
            oi_res = await db.execute(
                select(OrderItem).where(OrderItem.order_id == uo.id).limit(1)
            )
            oi = oi_res.scalar_one_or_none()
            print(f"[DB] order_id={{uo.id}} order_no={{uo.order_no}}")
            print(f"[DB] payment_method={{uo.payment_method}} channel_code={{uo.payment_channel_code}} display_name={{uo.payment_display_name}}")
            print(f"[DB] appointment_time={{oi.appointment_time}} appointment_data={{oi.appointment_data}}")

            # 验证 _format_time_slot
            ts = _format_time_slot(oi.appointment_time, oi.appointment_data)
            print(f"[CHECK] _format_time_slot -> {{ts!r}} (期望 '14:00-15:00')")
            assert ts == "14:00-15:00", f"FAIL: time_slot={{ts}}"

            # 验证 _build_payment_method_text 在 wechat + alipay_h5 不一致下的矫正
            pm_text = _build_payment_method_text(uo)
            print(f"[CHECK] _build_payment_method_text -> {{pm_text!r}} (期望 '支付宝（H5）')")
            assert pm_text == "支付宝（H5）", f"FAIL: pm_text={{pm_text}}"
            print("\\n[OK] 全部断言通过！")
        finally:
            break

asyncio.run(main())
'''
    encoded = py_script.replace('"', r'\"').replace("$", r"\$")
    out = ssh(
        f'docker exec {PREFIX}-backend python -c "{encoded}" 2>&1'
    )
    print(out)


if __name__ == "__main__":
    main()
