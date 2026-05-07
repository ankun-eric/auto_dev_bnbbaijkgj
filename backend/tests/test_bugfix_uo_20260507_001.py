"""[BUGFIX-UO-20260507-001] 商家端订单「预约时间」与「支付方式」与客户端不一致 Bug 修复测试

针对 Bug 修复方案文档 §五 的「验证清单」与 §七 的「单元测试建议」编写：

1. `_build_payment_method_text` 在 payment_method 与 payment_channel_code 不一致时
   必须以 channel_code 反推的 provider 为准（避免商家端显示"微信"而客户端显示"支付宝（H5）"）。
2. 商家端 `merchant.py` 的 `_format_time_slot` 在订单 list/detail 接口中已被正确复用：
   优先返回 appointment_data.time_slot 字符串（如 "14:00-15:00"），缺失时回退到
   appointment_time.strftime("%H:%M")。

不依赖 DB / HTTP，使用 SimpleNamespace 构造伪对象快速验证。
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.api.merchant import _format_time_slot
from app.api.unified_orders import _build_payment_method_text


def _mk_order(*, payment_method=None, payment_channel_code=None, payment_display_name=None):
    return SimpleNamespace(
        payment_method=payment_method,
        payment_channel_code=payment_channel_code,
        payment_display_name=payment_display_name,
    )


# ---------------------------------------------------------------------------
# A. 支付方式：payment_method 与 channel_code provider 冲突时矫正测试
# ---------------------------------------------------------------------------


def test_bugfix_a1_pm_wechat_but_channel_alipay_h5_returns_alipay_h5():
    """核心 Bug 复现：DB 中 payment_method=wechat 但 payment_channel_code=alipay_h5
    （由 /pay 漏传 payment_method + 异步通知幂等跳过造成）。
    商家端 _build_payment_method_text 必须以 channel_code 反推为支付宝，
    渲染为「支付宝（H5）」，与客户端显示一致。
    """
    order = _mk_order(
        payment_method="wechat",
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "支付宝（H5）"


def test_bugfix_a2_pm_alipay_but_channel_wechat_miniprogram_returns_wechat_mini():
    """对称用例：payment_method=alipay 但 channel_code=wechat_miniprogram，
    应以 channel_code 为准显示「微信支付（小程序）」。
    """
    order = _mk_order(
        payment_method="alipay",
        payment_channel_code="wechat_miniprogram",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "微信支付（小程序）"


def test_bugfix_a3_pm_alipay_channel_alipay_h5_no_change():
    """正常一致场景：payment_method=alipay + channel=alipay_h5，照旧显示「支付宝（H5）」。"""
    order = _mk_order(
        payment_method="alipay",
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "支付宝（H5）"


def test_bugfix_a4_pm_wechat_channel_wechat_app_no_change():
    """正常一致场景：payment_method=wechat + channel=wechat_app → 「微信支付（APP）」。"""
    order = _mk_order(
        payment_method="wechat",
        payment_channel_code="wechat_app",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "微信支付（APP）"


def test_bugfix_a5_coupon_deduction_not_affected():
    """非真实通道场景（优惠券全额抵扣）：即使 channel_code 是 alipay_h5，
    也必须显示「优惠券全额抵扣」，不能被本次修复影响。"""
    order = _mk_order(
        payment_method="coupon_deduction",
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "优惠券全额抵扣"


# ---------------------------------------------------------------------------
# B. 预约时段：_format_time_slot 在 list/detail 接口中复用正确性
# ---------------------------------------------------------------------------


def test_bugfix_b1_time_slot_from_appointment_data():
    """appointment_data.time_slot 存在时，必须返回完整时段字符串「14:00-15:00」，
    而不是只返回 appointment_time.strftime("%H:%M") 的「09:00」。"""
    appt = datetime(2026, 5, 8, 9, 0)  # DB 实存的时段起点
    data = {"date": "2026-05-08", "time_slot": "14:00-15:00"}
    assert _format_time_slot(appt, data) == "14:00-15:00"


def test_bugfix_b2_time_slot_fallback_to_appointment_time():
    """appointment_data 缺失或不含 time_slot 时，回退到 appointment_time 的 HH:MM。"""
    appt = datetime(2026, 5, 8, 14, 0)
    data = {"date": "2026-05-08"}  # 无 time_slot 字段
    assert _format_time_slot(appt, data) == "14:00"


def test_bugfix_b3_time_slot_fallback_when_data_none():
    """appointment_data 整体为 None 的场景（date 模式或老数据）。"""
    appt = datetime(2026, 5, 8, 10, 30)
    assert _format_time_slot(appt, None) == "10:30"


def test_bugfix_b4_time_slot_returns_none_when_all_empty():
    """两个都为 None（无预约商品）应返回 None。"""
    assert _format_time_slot(None, None) is None


def test_bugfix_b5_time_slot_strips_whitespace():
    """appointment_data.time_slot 含前后空白时也能正确返回（防御性）。"""
    appt = datetime(2026, 5, 8, 9, 0)
    data = {"time_slot": "  14:00-15:00  "}
    assert _format_time_slot(appt, data) == "14:00-15:00"
