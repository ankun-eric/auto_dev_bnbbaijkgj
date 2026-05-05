"""[门店预约看板与改期能力升级 v1.0 · F-11] 改期通知三通道单元测试。

覆盖：
1. _format_slot_text 时段格式化（早晨/边界/凌晨/None）
2. build_reschedule_message 文案构造
3. _send_wechat_subscribe 缺失凭证返回 ok=False（不抛异常）
4. _send_app_push 缺失 provider 返回 ok=False
5. _send_sms 缺失模板 ID 返回 ok=False
6. ChannelResult / RescheduleNotifyResult 聚合行为（all_failed / any_ok）
7. notify_order_rescheduled 端到端 mock：三通道全部失败时 result.all_failed=True
"""
from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.reschedule_notification import (
    ChannelResult,
    RescheduleNotifyResult,
    _format_slot_text,
    _send_app_push,
    _send_sms,
    _send_wechat_subscribe,
    build_reschedule_message,
    notify_order_rescheduled,
)


# ─────────── 1. _format_slot_text ───────────


def test_format_slot_text_morning():
    dt = datetime(2026, 5, 6, 10, 30)
    assert _format_slot_text(dt) == "05月06日 10:00-12:00"


def test_format_slot_text_boundary_8am():
    dt = datetime(2026, 5, 6, 8, 0)
    assert _format_slot_text(dt) == "05月06日 08:00-10:00"


def test_format_slot_text_evening_22():
    dt = datetime(2026, 5, 6, 22, 30)
    assert _format_slot_text(dt) == "05月06日 22:00-24:00"


def test_format_slot_text_early_morning_clamp():
    dt = datetime(2026, 5, 6, 5, 30)
    s = _format_slot_text(dt)
    assert "05" in s and ("05:30" in s or "5:30" in s)


def test_format_slot_text_none():
    assert _format_slot_text(None) == "未指定"


# ─────────── 2. build_reschedule_message ───────────


def test_build_message_full():
    msg = build_reschedule_message(
        product_name="基础体检套餐",
        old_appointment_time=datetime(2026, 5, 6, 10, 0),
        new_appointment_time=datetime(2026, 5, 7, 14, 0),
        store_name="朝阳门店",
        store_phone="010-12345678",
        brand="XX 健康",
    )
    assert "【XX 健康】" in msg
    assert "「基础体检套餐」" in msg
    assert "原 05月06日 10:00-12:00" in msg
    assert "现 05月07日 14:00-16:00" in msg
    assert "朝阳门店" in msg
    assert "010-12345678" in msg


def test_build_message_no_brand_no_phone():
    msg = build_reschedule_message(
        product_name="项目",
        old_appointment_time=datetime(2026, 5, 6, 10, 0),
        new_appointment_time=datetime(2026, 5, 7, 14, 0),
        store_name="",
        store_phone="",
        brand="",
    )
    assert msg.startswith("您预约的「项目」")
    assert "门店：" not in msg
    assert "请联系门店" not in msg


# ─────────── 3. _send_wechat_subscribe ───────────


@pytest.mark.asyncio
async def test_wechat_subscribe_no_openid():
    res = await _send_wechat_subscribe(openid=None, template_id="x", data={})
    assert res.ok is False
    assert "未授权" in res.detail


@pytest.mark.asyncio
async def test_wechat_subscribe_no_credentials(monkeypatch):
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_MINI_APP_SECRET", raising=False)
    monkeypatch.delenv("WECHAT_RESCHEDULE_TEMPLATE_ID", raising=False)
    res = await _send_wechat_subscribe(openid="test_openid", template_id=None, data={})
    assert res.ok is False
    assert "凭证未配置" in res.detail


# ─────────── 4. _send_app_push ───────────


@pytest.mark.asyncio
async def test_app_push_no_provider(monkeypatch):
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)
    res = await _send_app_push(user_id=1, title="t", body="b")
    assert res.ok is False
    assert "服务商未配置" in res.detail


@pytest.mark.asyncio
async def test_app_push_jpush_no_creds(monkeypatch):
    monkeypatch.setenv("APP_PUSH_PROVIDER", "jpush")
    monkeypatch.delenv("JPUSH_APP_KEY", raising=False)
    monkeypatch.delenv("JPUSH_MASTER_SECRET", raising=False)
    res = await _send_app_push(user_id=1, title="t", body="b")
    assert res.ok is False
    assert "极光凭证缺失" in res.detail


# ─────────── 5. _send_sms ───────────


@pytest.mark.asyncio
async def test_sms_no_phone():
    res = await _send_sms(phone=None, template_params=["a"], db=None)
    assert res.ok is False
    assert "无手机号" in res.detail


@pytest.mark.asyncio
async def test_sms_no_template(monkeypatch):
    monkeypatch.delenv("RESCHEDULE_SMS_TEMPLATE_ID", raising=False)
    res = await _send_sms(phone="13800138000", template_params=["a"], db=None)
    assert res.ok is False
    assert "模板 ID 未配置" in res.detail


# ─────────── 6. ChannelResult / Result 聚合 ───────────


def test_result_aggregate_any_ok():
    r = RescheduleNotifyResult()
    r.channels.append(ChannelResult("a", ok=False, detail=""))
    r.channels.append(ChannelResult("b", ok=True, detail="ok"))
    assert r.any_ok is True
    assert r.all_failed is False


def test_result_aggregate_all_failed():
    r = RescheduleNotifyResult()
    r.channels.append(ChannelResult("a", ok=False, detail=""))
    r.channels.append(ChannelResult("b", ok=False, detail=""))
    r.channels.append(ChannelResult("c", ok=False, detail=""))
    assert r.any_ok is False
    assert r.all_failed is True


def test_result_aggregate_to_dict():
    r = RescheduleNotifyResult()
    r.channels.append(ChannelResult("wechat_subscribe", ok=True, detail="ok"))
    r.channels.append(ChannelResult("app_push", ok=False, detail="skip"))
    r.channels.append(ChannelResult("sms", ok=False, detail="cred"))
    d = r.to_dict()
    assert d["any_ok"] is True
    assert d["all_failed"] is False
    assert len(d["channels"]) == 3
    names = [c["name"] for c in d["channels"]]
    assert "wechat_subscribe" in names
    assert "app_push" in names
    assert "sms" in names


# ─────────── 7. notify_order_rescheduled 端到端 ───────────


class _FakeDB:
    """最小 mock，实现 add()/flush() 即可。"""
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_notify_order_rescheduled_all_failed_when_no_creds(monkeypatch):
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_MINI_APP_SECRET", raising=False)
    monkeypatch.delenv("WECHAT_RESCHEDULE_TEMPLATE_ID", raising=False)
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)
    monkeypatch.delenv("RESCHEDULE_SMS_TEMPLATE_ID", raising=False)

    fake_user = SimpleNamespace(wechat_openid="openid_xxx", phone="13800138000")
    fake_store = SimpleNamespace(name="朝阳门店", contact_phone="010-12345678")
    fake_item = SimpleNamespace(
        product_name="基础体检套餐",
        product=SimpleNamespace(name="基础体检套餐"),
    )
    fake_order = SimpleNamespace(
        id=42,
        order_no="ORDER001",
        user_id=7,
        user=fake_user,
        store=fake_store,
        items=[fake_item],
    )

    db = _FakeDB()
    res = await notify_order_rescheduled(
        db,
        order=fake_order,
        old_appointment_time=datetime(2026, 5, 6, 10, 0),
        new_appointment_time=datetime(2026, 5, 7, 14, 0),
    )

    assert isinstance(res, RescheduleNotifyResult)
    assert len(res.channels) == 3
    assert res.all_failed is True
    assert res.any_ok is False
    # 站内 Notification 记录应被写入
    assert len(db.added) == 1
    n = db.added[0]
    assert getattr(n, "event_type", None) == "order_rescheduled"
    assert "改期" in (getattr(n, "title", "") or "")


@pytest.mark.asyncio
async def test_notify_order_rescheduled_partial_success(monkeypatch):
    """模拟 sms 通道成功、其他失败 → any_ok=True, all_failed=False。"""
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)

    async def fake_send_sms(*args, **kwargs):
        from app.services.reschedule_notification import ChannelResult as _CR
        return _CR(name="sms", ok=True, detail="mocked ok")

    with patch(
        "app.services.reschedule_notification._send_sms", side_effect=fake_send_sms
    ):
        fake_user = SimpleNamespace(wechat_openid=None, phone="13800138000")
        fake_store = SimpleNamespace(name="朝阳门店", contact_phone="010-12345678")
        fake_item = SimpleNamespace(
            product_name="基础体检套餐",
            product=SimpleNamespace(name="基础体检套餐"),
        )
        fake_order = SimpleNamespace(
            id=42, order_no="ORDER001", user_id=7,
            user=fake_user, store=fake_store, items=[fake_item],
        )
        db = _FakeDB()
        res = await notify_order_rescheduled(
            db,
            order=fake_order,
            old_appointment_time=datetime(2026, 5, 6, 10, 0),
            new_appointment_time=datetime(2026, 5, 7, 14, 0),
        )
        assert res.any_ok is True
        assert res.all_failed is False
