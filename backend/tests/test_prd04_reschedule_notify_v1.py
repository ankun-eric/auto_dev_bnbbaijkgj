"""[PRD-04 改期通知三通道 v1.0] 单元测试套件。

覆盖本期增量功能（企业微信告警 + 商家详情页通知状态字段）：
- F-04-6：三通道全失败时触发企业微信群机器人 webhook 告警
- F-04-5：商家订单详情接口返回 last_reschedule_notify_status / last_reschedule_notify

测试不依赖真实 DB / 真实 HTTP，全部用 unittest.mock 隔离外部 IO，
可在 `pytest --noconftest` 模式下纯函数式跑通。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from app.services.reschedule_notification import (
    ChannelResult,
    RescheduleNotifyResult,
    _send_wechat_work_alert,
    notify_order_rescheduled,
)


# ─────────── 1. _send_wechat_work_alert 凭证缺失/异常场景 ───────────


@pytest.mark.asyncio
async def test_wechat_work_alert_no_webhook(monkeypatch):
    """未配置 WECHAT_WORK_ALERT_WEBHOOK 时返回 ok=False，不抛异常。"""
    monkeypatch.delenv("WECHAT_WORK_ALERT_WEBHOOK", raising=False)
    res = await _send_wechat_work_alert(
        order_no="ORD001",
        user_name="张三",
        user_phone="13812345678",
        old_text="05月06日 10:00-12:00",
        new_text="05月07日 14:00-16:00",
        store_name="朝阳门店",
    )
    assert res.ok is False
    assert "未配置" in res.detail
    assert res.name == "wechat_work_alert"


@pytest.mark.asyncio
async def test_wechat_work_alert_explicit_webhook_phone_masked(monkeypatch):
    """显式传入 webhook_url 时优先生效，且手机号中间四位被遮蔽。"""

    captured = {}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"errcode": 0, "errmsg": "ok"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None, **_kwargs):
            captured["url"] = url
            captured["payload"] = json
            return _FakeResp()

    with patch("httpx.AsyncClient", _FakeClient):
        res = await _send_wechat_work_alert(
            webhook_url="https://qyapi.weixin.qq.com/test-hook",
            order_no="ORD002",
            user_name="李四",
            user_phone="13987654321",
            old_text="05月06日 10:00-12:00",
            new_text="05月07日 14:00-16:00",
            store_name="海淀门店",
            failure_detail="wx=cred missing; sms=template missing; push=provider missing",
        )

    assert res.ok is True
    assert "已发送" in res.detail
    assert captured["url"] == "https://qyapi.weixin.qq.com/test-hook"
    body = captured["payload"]
    assert body["msgtype"] == "text"
    content = body["text"]["content"]
    # 手机号中间四位必须被遮蔽，避免群聊全量曝光
    assert "13987654321" not in content
    assert "139****4321" in content
    # 关键字段都要出现
    assert "ORD002" in content
    assert "李四" in content
    assert "海淀门店" in content
    assert "05月06日 10:00-12:00" in content
    assert "05月07日 14:00-16:00" in content


@pytest.mark.asyncio
async def test_wechat_work_alert_http_error_returns_ok_false():
    """webhook 返回非 200 时返回 ok=False，不抛异常。"""

    class _FakeResp:
        status_code = 500
        text = "Internal Server Error"

        def json(self):
            return {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None, **_kwargs):
            return _FakeResp()

    with patch("httpx.AsyncClient", _FakeClient):
        res = await _send_wechat_work_alert(
            webhook_url="https://qyapi.weixin.qq.com/x",
            order_no="O", user_name="U", user_phone="13800000000",
            old_text="o", new_text="n", store_name="s",
        )
    assert res.ok is False
    assert "HTTP 500" in res.detail


@pytest.mark.asyncio
async def test_wechat_work_alert_errcode_nonzero_returns_ok_false():
    class _FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"errcode": 93000, "errmsg": "invalid webhook url"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None, **_kwargs):
            return _FakeResp()

    with patch("httpx.AsyncClient", _FakeClient):
        res = await _send_wechat_work_alert(
            webhook_url="https://qyapi.weixin.qq.com/y",
            order_no="O", user_name="U", user_phone="138",
            old_text="o", new_text="n", store_name="s",
        )
    assert res.ok is False
    assert "errcode=93000" in res.detail


# ─────────── 2. notify_order_rescheduled 全失败时触发企微告警 ───────────


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_all_failed_triggers_wechat_work_alert(monkeypatch):
    """三通道全部失败时，必须调用 _send_wechat_work_alert 一次，
    并把结果写入 to_dict 与 Notification.extra_data。"""
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_MINI_APP_SECRET", raising=False)
    monkeypatch.delenv("WECHAT_RESCHEDULE_TEMPLATE_ID", raising=False)
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)
    monkeypatch.delenv("RESCHEDULE_SMS_TEMPLATE_ID", raising=False)
    # 关键：让告警函数本身返回 ok=True，验证编排器会调用它
    fake_alert = AsyncMock(return_value=ChannelResult(
        name="wechat_work_alert", ok=True, detail="企业微信告警已发送（mock）"
    ))

    fake_user = SimpleNamespace(
        wechat_openid="open_xx", phone="13812345678",
        real_name="张三", nickname="zs", username="zs"
    )
    fake_store = SimpleNamespace(name="朝阳门店", contact_phone="010-12345678")
    fake_item = SimpleNamespace(
        product_name="基础体检套餐",
        product=SimpleNamespace(name="基础体检套餐"),
    )
    fake_order = SimpleNamespace(
        id=42, order_no="ORD-PRD04",
        user_id=7, user=fake_user, store=fake_store,
        items=[fake_item],
    )

    db = _FakeDB()
    with patch(
        "app.services.reschedule_notification._send_wechat_work_alert",
        new=fake_alert,
    ):
        res = await notify_order_rescheduled(
            db,
            order=fake_order,
            old_appointment_time=datetime(2026, 5, 6, 10, 0),
            new_appointment_time=datetime(2026, 5, 7, 14, 0),
        )

    assert res.all_failed is True
    assert res.any_ok is False
    assert fake_alert.await_count == 1
    # 调用参数中包含订单号 / 客户姓名 / 客户手机号 / 原新时段 / 门店名（PRD §2.8）
    call_kwargs = fake_alert.await_args.kwargs
    assert call_kwargs["order_no"] == "ORD-PRD04"
    assert call_kwargs["user_name"] == "张三"
    assert call_kwargs["user_phone"] == "13812345678"
    assert call_kwargs["store_name"] == "朝阳门店"
    assert "05月06日" in call_kwargs["old_text"]
    assert "05月07日" in call_kwargs["new_text"]
    # to_dict 中应包含 wechat_work_alert
    d = res.to_dict()
    assert "wechat_work_alert" in d
    assert d["wechat_work_alert"]["ok"] is True
    # 站内通知 extra_data 应包含 wechat_work_alert
    assert len(db.added) == 1
    n = db.added[0]
    extra = getattr(n, "extra_data", {}) or {}
    assert extra.get("notify_status") == "all_failed"
    assert extra.get("wechat_work_alert", {}).get("ok") is True


@pytest.mark.asyncio
async def test_partial_success_does_NOT_trigger_alert(monkeypatch):
    """任一通道成功即不应触发企业微信告警。"""
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)

    async def fake_send_sms(*args, **kwargs):
        return ChannelResult(name="sms", ok=True, detail="mocked ok")

    fake_alert = AsyncMock(return_value=ChannelResult(
        name="wechat_work_alert", ok=True, detail="should not be called"
    ))

    fake_order = SimpleNamespace(
        id=1, order_no="O1",
        user_id=1,
        user=SimpleNamespace(
            wechat_openid=None, phone="13800000000",
            real_name="A", nickname="a", username="a",
        ),
        store=SimpleNamespace(name="S", contact_phone="0"),
        items=[SimpleNamespace(product_name="P", product=SimpleNamespace(name="P"))],
    )
    db = _FakeDB()
    with (
        patch("app.services.reschedule_notification._send_sms", side_effect=fake_send_sms),
        patch("app.services.reschedule_notification._send_wechat_work_alert", new=fake_alert),
    ):
        res = await notify_order_rescheduled(
            db, order=fake_order,
            old_appointment_time=datetime(2026, 5, 6, 10, 0),
            new_appointment_time=datetime(2026, 5, 7, 14, 0),
        )

    assert res.any_ok is True
    assert res.all_failed is False
    assert fake_alert.await_count == 0
    d = res.to_dict()
    # any_ok=true 时不应挂载 wechat_work_alert
    assert "wechat_work_alert" not in d


@pytest.mark.asyncio
async def test_all_failed_alert_exception_is_swallowed(monkeypatch):
    """企业微信告警自身异常时，不应阻塞主流程。"""
    monkeypatch.delenv("WECHAT_MINI_APP_ID", raising=False)
    monkeypatch.delenv("APP_PUSH_PROVIDER", raising=False)
    monkeypatch.delenv("RESCHEDULE_SMS_TEMPLATE_ID", raising=False)

    async def boom(**kwargs):
        raise RuntimeError("alert webhook crashed")

    fake_order = SimpleNamespace(
        id=1, order_no="O1",
        user_id=1,
        user=SimpleNamespace(
            wechat_openid=None, phone=None,
            real_name=None, nickname=None, username="u",
        ),
        store=SimpleNamespace(name="S", contact_phone=""),
        items=[SimpleNamespace(product_name="P", product=SimpleNamespace(name="P"))],
    )
    db = _FakeDB()
    with patch(
        "app.services.reschedule_notification._send_wechat_work_alert",
        side_effect=boom,
    ):
        res = await notify_order_rescheduled(
            db, order=fake_order,
            old_appointment_time=datetime(2026, 5, 6, 10, 0),
            new_appointment_time=datetime(2026, 5, 7, 14, 0),
        )
    # 主流程仍然返回结果对象，all_failed=True
    assert res.all_failed is True


# ─────────── 3. to_dict 在不同场景的字段输出 ───────────


def test_to_dict_no_alert_when_no_failure():
    r = RescheduleNotifyResult()
    r.channels.append(ChannelResult("a", ok=True, detail="ok"))
    d = r.to_dict()
    assert d["any_ok"] is True
    assert "wechat_work_alert" not in d


def test_to_dict_includes_alert_when_attached():
    r = RescheduleNotifyResult()
    r.channels.append(ChannelResult("a", ok=False, detail="x"))
    r.channels.append(ChannelResult("b", ok=False, detail="y"))
    r.alert = ChannelResult(  # type: ignore[attr-defined]
        name="wechat_work_alert", ok=False, detail="webhook 未配置"
    )
    d = r.to_dict()
    assert d["all_failed"] is True
    assert d["wechat_work_alert"]["ok"] is False
    assert "未配置" in d["wechat_work_alert"]["detail"]


# ─────────── 4. 短手机号 / 边界遮蔽逻辑 ───────────


@pytest.mark.asyncio
async def test_alert_short_phone_no_mask_crash(monkeypatch):
    """手机号短于 7 位（异常数据）时不应抛异常，仍可正常构建消息。"""
    monkeypatch.delenv("WECHAT_WORK_ALERT_WEBHOOK", raising=False)
    res = await _send_wechat_work_alert(
        order_no="O", user_name="U", user_phone="123",
        old_text="o", new_text="n", store_name="s",
    )
    # webhook 未配置 → 直接 ok=False，但函数本身不应崩
    assert res.ok is False


@pytest.mark.asyncio
async def test_alert_empty_phone_no_crash(monkeypatch):
    monkeypatch.delenv("WECHAT_WORK_ALERT_WEBHOOK", raising=False)
    res = await _send_wechat_work_alert(
        order_no="O", user_name="U", user_phone="",
        old_text="o", new_text="n", store_name="s",
    )
    assert res.ok is False
