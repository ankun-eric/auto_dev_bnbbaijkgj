"""[PRD-365 商家后台「预约看板」替换升级 v1.0] 新预约通知单元测试。

覆盖 `app.services.merchant_new_appointment_notify` 模块的：
- `_mask_phone` 手机号脱敏
- 缺少配置时的安全降级（不抛异常）
- 推送收件人为空 / 已绑定 / 部分失败 等典型场景

设计原则：
- 不依赖真实 DB / 真实 HTTP，使用纯函数验证 + AsyncMock 隔离
- 在 `pytest --noconftest` 模式下可独立通过
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from app.services.merchant_new_appointment_notify import (
    _mask_phone,
    notify_merchant_new_appointment,
)


# ─────────── 1. _mask_phone 脱敏 ───────────


def test_mask_phone_full_11():
    assert _mask_phone("13987654321") == "139****4321"


def test_mask_phone_short_7_to_10():
    # 7 位手机号：保留前 3 + 末 2，中间 ****
    assert _mask_phone("1234567") == "123****67"
    # 10 位
    assert _mask_phone("1234567890") == "123****90"


def test_mask_phone_too_short():
    assert _mask_phone("123") == "123"
    assert _mask_phone("") == ""
    assert _mask_phone(None) == ""


# ─────────── 2. notify_merchant_new_appointment 配置缺失/收件人为空场景 ───────────


class _FakeResult:
    """模拟 db.execute(...).scalars()/scalar() 链式结果。"""

    def __init__(self, items=None, single=None):
        self._items = items or []
        self._single = single

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._single

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else self._single

    def one_or_none(self):
        return self._single


class _FakeDB:
    """按调用顺序返回预设结果列表。"""

    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, _stmt):
        if self._idx >= len(self._results):
            return _FakeResult()
        r = self._results[self._idx]
        self._idx += 1
        return r


def _make_order(*, order_id=1, user_id=10, order_no="ORD20260506001"):
    """构造一个最小化的 UnifiedOrder 模拟对象。"""
    return SimpleNamespace(
        id=order_id,
        user_id=user_id,
        order_no=order_no,
    )


@pytest.mark.asyncio
async def test_notify_skipped_when_order_has_no_store(monkeypatch):
    """订单第一项缺少 store_id → skipped=True，不发任何消息。"""
    order = _make_order()
    # 第一次 db.execute 取 OrderItem，返回一个 store_id=None 的 item
    fake_item = SimpleNamespace(store_id=None, product_id=1, appointment_time=None)
    db = _FakeDB([_FakeResult(items=[fake_item])])

    res = await notify_merchant_new_appointment(db, order=order)
    assert res["skipped"] is True
    assert res["recipients_total"] == 0
    assert "store_id" in res["detail"]


@pytest.mark.asyncio
async def test_notify_skipped_when_no_membership(monkeypatch):
    """门店下无任何 membership → skipped=True，不发推送。"""
    order = _make_order()
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="测试门店")
    fake_product = SimpleNamespace(id=1, name="精油按摩")
    fake_user = SimpleNamespace(id=10, nickname="张三", phone="13812345678", real_name=None)

    db = _FakeDB([
        _FakeResult(items=[fake_item]),               # OrderItem
        _FakeResult(single=fake_store),               # MerchantStore
        _FakeResult(single=fake_product),             # Product
        _FakeResult(single=fake_user),                # User (customer)
        _FakeResult(items=[]),                        # MerchantStoreMembership empty
    ])

    res = await notify_merchant_new_appointment(db, order=order)
    assert res["skipped"] is True
    assert res["store_id"] == 99
    assert res["recipients_total"] == 0
    assert "无关联员工" in res["detail"]


@pytest.mark.asyncio
async def test_notify_skipped_when_no_wechat_bound(monkeypatch):
    """门店下 membership 都没绑微信 → skipped=True。"""
    order = _make_order()
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="测试门店")
    fake_product = SimpleNamespace(id=1, name="精油按摩")
    fake_customer = SimpleNamespace(id=10, nickname="张三", phone="13812345678", real_name=None)
    fake_membership = SimpleNamespace(user_id=20, store_id=99)
    fake_employee = SimpleNamespace(id=20, wechat_openid=None)

    db = _FakeDB([
        _FakeResult(items=[fake_item]),
        _FakeResult(single=fake_store),
        _FakeResult(single=fake_product),
        _FakeResult(single=fake_customer),
        _FakeResult(items=[fake_membership]),
        _FakeResult(items=[fake_employee]),
    ])

    res = await notify_merchant_new_appointment(db, order=order)
    assert res["skipped"] is True
    assert "无已绑定微信的员工" in res["detail"]


@pytest.mark.asyncio
async def test_notify_skipped_when_template_id_missing(monkeypatch):
    """有绑定微信的员工，但缺少 template_id 配置 → skipped=True。"""
    monkeypatch.delenv("WECHAT_NEW_APPOINTMENT_TEMPLATE_ID", raising=False)
    monkeypatch.delenv("WECHAT_RESCHEDULE_TEMPLATE_ID", raising=False)

    order = _make_order()
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="测试门店")
    fake_product = SimpleNamespace(id=1, name="精油按摩")
    fake_customer = SimpleNamespace(id=10, nickname="张三", phone="13812345678", real_name=None)
    fake_membership = SimpleNamespace(user_id=20, store_id=99)
    fake_employee = SimpleNamespace(id=20, wechat_openid="oABC123")

    db = _FakeDB([
        _FakeResult(items=[fake_item]),
        _FakeResult(single=fake_store),
        _FakeResult(single=fake_product),
        _FakeResult(single=fake_customer),
        _FakeResult(items=[fake_membership]),
        _FakeResult(items=[fake_employee]),
    ])

    res = await notify_merchant_new_appointment(db, order=order)
    assert res["skipped"] is True
    assert res["recipients_total"] == 1
    assert "TEMPLATE_ID" in res["detail"] or "未配置" in res["detail"]


@pytest.mark.asyncio
async def test_notify_skipped_when_access_token_missing(monkeypatch):
    """有 template_id 但缺 access_token 凭证 → skipped=True。"""
    monkeypatch.setenv("WECHAT_NEW_APPOINTMENT_TEMPLATE_ID", "TPL001")
    monkeypatch.delenv("WECHAT_MP_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_MP_APP_SECRET", raising=False)
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_MINI_APP_SECRET", raising=False)

    order = _make_order()
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="测试门店")
    fake_product = SimpleNamespace(id=1, name="精油按摩")
    fake_customer = SimpleNamespace(id=10, nickname="张三", phone="13812345678", real_name=None)
    fake_membership = SimpleNamespace(user_id=20, store_id=99)
    fake_employee = SimpleNamespace(id=20, wechat_openid="oABC123")

    db = _FakeDB([
        _FakeResult(items=[fake_item]),
        _FakeResult(single=fake_store),
        _FakeResult(single=fake_product),
        _FakeResult(single=fake_customer),
        _FakeResult(items=[fake_membership]),
        _FakeResult(items=[fake_employee]),
    ])

    res = await notify_merchant_new_appointment(db, order=order)
    assert res["skipped"] is True
    assert "access_token" in res["detail"] or "未能获取" in res["detail"]


@pytest.mark.asyncio
async def test_notify_sends_template_to_bound_employees(monkeypatch):
    """有 template_id + access_token，且员工已绑微信 → 触发推送，sent>0。"""
    monkeypatch.setenv("WECHAT_NEW_APPOINTMENT_TEMPLATE_ID", "TPL001")
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_appid_test")
    monkeypatch.setenv("WECHAT_MP_APP_SECRET", "wx_secret_test")

    order = _make_order(order_no="ORD-NEW-001")
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="朝阳门店")
    fake_product = SimpleNamespace(id=1, name="精油按摩")
    fake_customer = SimpleNamespace(id=10, nickname="李四", phone="13987654321", real_name=None)
    fake_membership_a = SimpleNamespace(user_id=20, store_id=99)
    fake_membership_b = SimpleNamespace(user_id=21, store_id=99)
    fake_emp_a = SimpleNamespace(id=20, wechat_openid="oABC")
    fake_emp_b = SimpleNamespace(id=21, wechat_openid="oXYZ")

    db = _FakeDB([
        _FakeResult(items=[fake_item]),
        _FakeResult(single=fake_store),
        _FakeResult(single=fake_product),
        _FakeResult(single=fake_customer),
        _FakeResult(items=[fake_membership_a, fake_membership_b]),
        _FakeResult(items=[fake_emp_a, fake_emp_b]),
    ])

    sent_payloads = []

    async def _fake_get_token():
        return "FAKE_TOKEN"

    async def _fake_send(*, access_token, openid, template_id, data, url=""):
        sent_payloads.append({"openid": openid, "template_id": template_id, "data": data})
        return True  # 全部成功

    with patch(
        "app.services.merchant_new_appointment_notify._get_wechat_access_token",
        new=_fake_get_token,
    ), patch(
        "app.services.merchant_new_appointment_notify._send_template_message",
        new=_fake_send,
    ):
        res = await notify_merchant_new_appointment(db, order=order)

    assert res["skipped"] is False
    assert res["ok"] is True
    assert res["recipients_total"] == 2
    assert res["recipients_sent"] == 2
    assert res["recipients_failed"] == 0
    # 验证至少有一条 payload 含到本次的关键字段（脱敏手机号 / 订单号 / 门店名）
    flat = str(sent_payloads)
    assert "139****4321" in flat
    assert "ORD-NEW-001" in flat
    assert "朝阳门店" in flat
    assert "精油按摩" in flat


@pytest.mark.asyncio
async def test_notify_partial_failure_still_returns_ok(monkeypatch):
    """部分员工推送失败时，整体 ok 仍为 True，failed 计数正确。"""
    monkeypatch.setenv("WECHAT_NEW_APPOINTMENT_TEMPLATE_ID", "TPL001")
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_appid_test")
    monkeypatch.setenv("WECHAT_MP_APP_SECRET", "wx_secret_test")

    order = _make_order()
    fake_item = SimpleNamespace(
        store_id=99, product_id=1,
        appointment_time=datetime(2026, 5, 6, 10, 0),
    )
    fake_store = SimpleNamespace(id=99, store_name="测试门店")
    fake_product = SimpleNamespace(id=1, name="服务X")
    fake_customer = SimpleNamespace(id=10, nickname="王五", phone="13800000000", real_name=None)
    fake_m1 = SimpleNamespace(user_id=30, store_id=99)
    fake_m2 = SimpleNamespace(user_id=31, store_id=99)
    fake_e1 = SimpleNamespace(id=30, wechat_openid="o1")
    fake_e2 = SimpleNamespace(id=31, wechat_openid="o2")

    db = _FakeDB([
        _FakeResult(items=[fake_item]),
        _FakeResult(single=fake_store),
        _FakeResult(single=fake_product),
        _FakeResult(single=fake_customer),
        _FakeResult(items=[fake_m1, fake_m2]),
        _FakeResult(items=[fake_e1, fake_e2]),
    ])

    call_idx = {"n": 0}

    async def _fake_get_token():
        return "TOK"

    async def _fake_send(*, access_token, openid, template_id, data, url=""):
        call_idx["n"] += 1
        return call_idx["n"] == 1  # 第一条成功，第二条失败

    with patch(
        "app.services.merchant_new_appointment_notify._get_wechat_access_token",
        new=_fake_get_token,
    ), patch(
        "app.services.merchant_new_appointment_notify._send_template_message",
        new=_fake_send,
    ):
        res = await notify_merchant_new_appointment(db, order=order)

    assert res["skipped"] is False
    assert res["ok"] is True
    assert res["recipients_total"] == 2
    assert res["recipients_sent"] == 1
    assert res["recipients_failed"] == 1


@pytest.mark.asyncio
async def test_notify_unexpected_exception_swallowed(monkeypatch):
    """内部任何异常都不会抛出，整体安全降级。"""
    order = _make_order()

    class _ExplodeDB:
        async def execute(self, _stmt):
            raise RuntimeError("DB exploded for test")

    res = await notify_merchant_new_appointment(_ExplodeDB(), order=order)
    assert res["skipped"] is True
    assert "内部异常" in res["detail"]
