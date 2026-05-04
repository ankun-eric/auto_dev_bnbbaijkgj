"""[2026-05-05 H5 订单详情"支付方式"显示错误（优惠券全额抵扣场景）Bug 修复 v1.0]

针对 `_build_payment_method_text` 优先级判定的纯单元测试，覆盖修复方案 §四 的
TC-01 ~ TC-10，确保「以实付方式为准，预选通道仅作通道补充」的口径全面生效。

不依赖 DB / HTTP，使用 SimpleNamespace 构造伪订单对象快速验证逻辑分支。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.unified_orders import _build_payment_method_text


def _mk(
    *,
    payment_method=None,
    payment_channel_code=None,
    payment_display_name=None,
):
    return SimpleNamespace(
        payment_method=payment_method,
        payment_channel_code=payment_channel_code,
        payment_display_name=payment_display_name,
    )


# ---------------------------------------------------------------------------
# TC-01：优惠券全额抵扣 0 元单（预选通道为 alipay_h5）→ 优惠券全额抵扣
# ---------------------------------------------------------------------------

def test_tc01_coupon_deduction_with_alipay_h5_preselect_returns_coupon_text():
    """核心 Bug 复现：用户预选支付宝 H5 后改为优惠券全额抵扣，
    必须显示「优惠券全额抵扣」，不能显示「支付宝（H5）」。"""
    order = _mk(
        payment_method="coupon_deduction",
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "优惠券全额抵扣"


# ---------------------------------------------------------------------------
# TC-02：优惠券全额抵扣 0 元单（预选通道为 wechat_miniprogram）→ 优惠券全额抵扣
# ---------------------------------------------------------------------------

def test_tc02_coupon_deduction_with_wechat_miniprogram_preselect():
    order = _mk(
        payment_method="coupon_deduction",
        payment_channel_code="wechat_miniprogram",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "优惠券全额抵扣"


# ---------------------------------------------------------------------------
# TC-03：余额全额支付 0 元单（预选通道为任意）→ 余额支付
# ---------------------------------------------------------------------------

def test_tc03_balance_zero_order_with_alipay_app_preselect():
    order = _mk(
        payment_method="balance",
        payment_channel_code="alipay_app",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "余额支付"


# ---------------------------------------------------------------------------
# TC-04：积分兑换 0 元单 → 积分兑换
# ---------------------------------------------------------------------------

def test_tc04_points_zero_order_with_wechat_app_preselect():
    order = _mk(
        payment_method="points",
        payment_channel_code="wechat_app",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "积分兑换"


# ---------------------------------------------------------------------------
# TC-05：真实支付宝 H5 支付（实付 > 0）→ 支付宝（H5）
# ---------------------------------------------------------------------------

def test_tc05_real_alipay_h5_payment_returns_display_with_suffix():
    order = _mk(
        payment_method="alipay",
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "支付宝（H5）"


# ---------------------------------------------------------------------------
# TC-06：真实微信小程序支付（实付 > 0）→ 微信支付（小程序）
# ---------------------------------------------------------------------------

def test_tc06_real_wechat_miniprogram_payment():
    order = _mk(
        payment_method="wechat",
        payment_channel_code="wechat_miniprogram",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "微信支付（小程序）"


# ---------------------------------------------------------------------------
# TC-07：实付 > 0 的真实通道（wechat + wechat_app 端）→ 微信支付（APP）
# ---------------------------------------------------------------------------

def test_tc07_real_wechat_app_payment():
    order = _mk(
        payment_method="wechat",
        payment_channel_code="wechat_app",
        payment_display_name="微信支付",
    )
    assert _build_payment_method_text(order) == "微信支付（APP）"


# ---------------------------------------------------------------------------
# TC-08：兼容场景——旧订单只有 name 没有 code → 返回 name 作兜底
# 注意：当 payment_method ∈ {wechat, alipay} 但缺 code 时走中文兜底；
#      当 payment_method 完全为空时走 name 兜底。
# ---------------------------------------------------------------------------

def test_tc08_legacy_only_name_without_code_and_pm():
    order = _mk(
        payment_method=None,
        payment_channel_code=None,
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "支付宝"


def test_tc08b_pm_wechat_without_code_and_name_falls_back_to_chinese():
    order = _mk(
        payment_method="wechat",
        payment_channel_code=None,
        payment_display_name=None,
    )
    assert _build_payment_method_text(order) == "微信支付"


# ---------------------------------------------------------------------------
# TC-09：异常场景——所有字段都为空 → None
# ---------------------------------------------------------------------------

def test_tc09_all_empty_returns_none():
    order = _mk()
    assert _build_payment_method_text(order) is None


# ---------------------------------------------------------------------------
# TC-10：商家端拼装路径与统一接口一致（同等输入产出同一字符串）
# ---------------------------------------------------------------------------

def test_tc10_merchant_uses_same_builder_as_unified():
    """merchant.py 已改为复用 _build_payment_method_text，因此两路径必然一致。
    本用例保护这一一致性，防止后续重构再次出现独立拼装。"""
    from app.api import merchant as merchant_module

    assert merchant_module._build_payment_method_text is _build_payment_method_text


# ---------------------------------------------------------------------------
# 兼容：payment_method 为枚举对象（含 .value）也应正确解析
# ---------------------------------------------------------------------------

class _FakeEnum:
    def __init__(self, v):
        self.value = v


def test_pm_as_enum_object_resolves_value():
    order = _mk(
        payment_method=_FakeEnum("coupon_deduction"),
        payment_channel_code="alipay_h5",
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "优惠券全额抵扣"


# ---------------------------------------------------------------------------
# 边界：payment_method=alipay 但 code 是未知端 → 仅返回 name
# ---------------------------------------------------------------------------

def test_alipay_with_unknown_channel_code_returns_name_only():
    order = _mk(
        payment_method="alipay",
        payment_channel_code="alipay_pc",  # 未在 PLATFORM_LABEL 中
        payment_display_name="支付宝",
    )
    assert _build_payment_method_text(order) == "支付宝"
