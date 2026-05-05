"""
[PRD-02 门店端预约看板 v1.0] 看板接口字段口径与边界回归测试

覆盖：
- F-02-2 日 9 宫格：cells 9 段、字段含 appointment_count/verified_count/verified_amount/label
- F-02-5 9 宫格抽屉：order 卡片包含 PRD §2.7 5 字段（customer_name/customer_phone/product_name/status + 操作型）
- F-02-6 月视图弹窗 6 字段标准版：appointment_time/customer_name/customer_phone/product_name/status/amount
- F-02-8 已核金额仅算已核销订单（_is_verified_status 必须只接受 verified/completed/pending_receipt 之类的"核销后"状态，
        不接受 cancelled/pending_payment/pending_appointment 等未核销状态）
- F-02-9 金额仍以 float 返回，不强制后端字符串化（前端按 ¥+整数渲染）
- R-02-03 商家端看到的客户手机号不脱敏（_build_order_card 返回原始 user.phone）
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.merchant_dashboard import (
    SLOT_HOURS,
    _build_order_card,
    _is_active_status,
    _is_verified_status,
)


# ─────────────── F-02-8 已核金额口径 ───────────────

class _Status:
    """模拟 SQLAlchemy Enum 对象，含 .value 属性"""

    def __init__(self, value):
        self.value = value


@pytest.mark.parametrize(
    "status_str,expected_verified",
    [
        ("verified", True),  # 严格 PRD §2.8 命中
        ("completed", True),  # 已完成 = 核销过的终态
        ("pending_receipt", True),  # 已核销但待收货
        ("appointed", False),  # 已预约未核销
        ("pending_use", False),  # 待核销
        ("pending_appointment", False),  # 待预约
        ("pending_payment", False),  # 待付款
        ("cancelled", False),  # 已取消
        ("refund_success", False),  # 已退款（不计入已核金额）
        ("refunding", False),
        ("refunded", False),
    ],
)
def test_verified_status_predicate(status_str, expected_verified):
    """F-02-8 已核金额仅统计已核销订单：未核销的状态全部不计入"""
    assert _is_verified_status(status_str) is expected_verified
    # 同时验证 enum-like 对象（含 .value）也走得通
    assert _is_verified_status(_Status(status_str)) is expected_verified


@pytest.mark.parametrize(
    "status_str,expected_active",
    [
        ("verified", True),
        ("completed", True),
        ("pending_use", True),
        ("appointed", True),
        ("pending_appointment", True),
        ("pending_receipt", True),
        ("cancelled", False),  # 已取消 → 不计入"预约 N"
        ("refund_success", False),  # 已退款 → 不计入"预约 N"
        ("pending_payment", False),  # 未支付 → 不计入"预约 N"
    ],
)
def test_active_status_predicate(status_str, expected_active):
    """F-02-2 预约 N 计数：cancelled / refund_success / pending_payment 不计入"""
    assert _is_active_status(status_str) is expected_active


# ─────────────── F-02-7 抽屉订单卡片 5 字段（操作型） ───────────────


def _make_item(appt_time: datetime, product_name="基础体检套餐", subtotal=588.0, item_id=11):
    return SimpleNamespace(
        id=item_id,
        appointment_time=appt_time,
        product_name=product_name,
        subtotal=subtotal,
    )


def _make_order(order_id=101, order_no="ORD20260505001", status="verified"):
    return SimpleNamespace(
        id=order_id,
        order_no=order_no,
        status=_Status(status),
    )


def _make_user(nickname="张三", phone="13812345678"):
    return SimpleNamespace(nickname=nickname, phone=phone)


def test_build_order_card_contains_all_required_fields():
    """PRD §2.7 抽屉订单 5 字段（操作型）+ §2.5 月视图 6 字段（标准版）所需字段必须都返回"""
    item = _make_item(datetime(2026, 5, 5, 10, 30))
    order = _make_order(status="verified")
    user = _make_user(nickname="张三", phone="13812345678")

    card = _build_order_card(item, order, user)

    # 5 字段操作型（抽屉用）：客户姓名 / 客户手机号 / 服务项目名 / 订单状态 / 订单 ID 用于详情按钮
    assert card["customer_name"] == "张三"
    assert card["customer_phone"] == "13812345678"
    assert card["product_name"] == "基础体检套餐"
    assert card["status"] == "verified"
    assert card["order_id"] == 101
    # 6 字段标准版（月视图弹窗用）：还需预约时段 / 订单金额
    assert card["slot_no"] == 3  # 10:30 → slot 3 (10:00-12:00)
    assert card["slot_label"] == "10:00-12:00"
    assert card["amount"] == 588.0
    assert card["appointment_time"] == "2026-05-05T10:30:00"


def test_build_order_card_phone_not_masked():
    """R-02-03 商家端看到的客户手机号不脱敏（11 位完整展示）"""
    item = _make_item(datetime(2026, 5, 5, 10, 0))
    order = _make_order()
    user = _make_user(phone="13812345678")
    card = _build_order_card(item, order, user)
    assert card["customer_phone"] == "13812345678"
    assert "*" not in (card["customer_phone"] or "")
    assert len(card["customer_phone"]) == 11


def test_build_order_card_fallback_when_no_nickname():
    """客户姓名缺失时降级为手机号或'未知'，确保抽屉永远有客户名字"""
    item = _make_item(datetime(2026, 5, 5, 10, 0))
    order = _make_order()
    user = _make_user(nickname=None, phone="13812345678")
    card = _build_order_card(item, order, user)
    assert card["customer_name"] == "13812345678"


def test_build_order_card_fallback_when_user_none():
    """user 缺失时降级为'未知'，不抛异常"""
    item = _make_item(datetime(2026, 5, 5, 10, 0))
    order = _make_order()
    card = _build_order_card(item, order, None)
    assert card["customer_name"] == "未知"
    assert card["customer_phone"] is None


def test_build_order_card_amount_is_float_not_string():
    """F-02-9 金额由前端按 `¥` + 整数格式化；后端保持 float 不预格式化"""
    item = _make_item(datetime(2026, 5, 5, 10, 0), subtotal=1280.0)
    order = _make_order()
    user = _make_user()
    card = _build_order_card(item, order, user)
    assert isinstance(card["amount"], float)
    assert card["amount"] == 1280.0


def test_build_order_card_status_extracted_from_enum():
    """status 字段必须从 enum-like 对象提取 .value，方便前端直接 statusTag(card.status)"""
    item = _make_item(datetime(2026, 5, 5, 10, 0))
    order = _make_order(status="pending_use")
    user = _make_user()
    card = _build_order_card(item, order, user)
    assert card["status"] == "pending_use"


# ─────────────── F-02-2 9 宫格段号映射回归 ───────────────


@pytest.mark.parametrize(
    "hour,expected_slot,expected_label",
    [
        (6, 1, "06:00-08:00"),
        (7, 1, "06:00-08:00"),
        (8, 2, "08:00-10:00"),
        (10, 3, "10:00-12:00"),
        (12, 4, "12:00-14:00"),
        (14, 5, "14:00-16:00"),
        (16, 6, "16:00-18:00"),
        (18, 7, "18:00-20:00"),
        (20, 8, "20:00-22:00"),
        (22, 9, "22:00-24:00"),
        (23, 9, "22:00-24:00"),
    ],
)
def test_build_order_card_slot_mapping_for_each_grid(hour, expected_slot, expected_label):
    """9 宫格每段都能从 appointment_time 正确映射到 slot_no + slot_label"""
    item = _make_item(datetime(2026, 5, 5, hour, 0))
    card = _build_order_card(item, _make_order(), _make_user())
    assert card["slot_no"] == expected_slot
    assert card["slot_label"] == expected_label


def test_build_order_card_dawn_slot_is_none():
    """R-02-04 / 异常处理：凌晨段订单（00:00-06:00）slot_no=None，9 宫格不渲染"""
    item = _make_item(datetime(2026, 5, 5, 3, 0))
    card = _build_order_card(item, _make_order(), _make_user())
    assert card["slot_no"] is None
    assert card["slot_label"] == ""


# ─────────────── F-02-2 9 段配置 ───────────────


def test_dashboard_grid_has_9_cells():
    """日视图 9 宫格 = 9 段，确保没有越界"""
    assert len(SLOT_HOURS) == 9


def test_morning_slots_are_first_three():
    """月视图弹窗左栏（上午 06:00-12:00）= slot 1/2/3，与 get_month_day_orders 拆分一致"""
    # slot 1=6-8, slot 2=8-10, slot 3=10-12
    morning_slots = [(start, end) for start, end in SLOT_HOURS if start < 12]
    assert len(morning_slots) == 3
    assert morning_slots[0] == (6, 8)
    assert morning_slots[-1] == (10, 12)


def test_afternoon_slots_are_last_six():
    """月视图弹窗右栏（下午+晚上 12:00-24:00）= slot 4-9"""
    afternoon_slots = [(start, end) for start, end in SLOT_HOURS if start >= 12]
    assert len(afternoon_slots) == 6
    assert afternoon_slots[0] == (12, 14)
    assert afternoon_slots[-1] == (22, 24)
