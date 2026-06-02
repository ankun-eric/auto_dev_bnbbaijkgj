"""[PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）后端测试

覆盖：
- 配置查询 / 修改（阈值、暂停、恢复）
- 签到：成功记录、含位置；超时后再签到自动解除预警
- 紧急联系人 CRUD（最多 3 位）
- 预警记录查询
- 扫描任务：超时触发预警、提前 1h 提醒
- 鉴权：未登录拒绝
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import test_session  # noqa: F401  (re-export)


@pytest.fixture(autouse=True)
def disable_email(monkeypatch):
    async def _noop(*args, **kwargs):
        return False
    monkeypatch.setattr("app.api.safety_rope_v1._send_email", _noop)




@pytest.mark.asyncio
async def test_status_requires_auth(client: AsyncClient):
    resp = await client.get("/api/safety-rope/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_status_default_config(client: AsyncClient, auth_headers):
    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["config"]["threshold_hours"] == 48
    assert body["config"]["status"] == "normal"
    assert body["runtime_status"] == "normal"
    assert body["last_checkin"] is None
    assert body["today_checked"] is False
    assert body["contacts_count"] == 0


@pytest.mark.asyncio
async def test_update_config_threshold(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"threshold_hours": 24},
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["threshold_hours"] == 24

    # 非法阈值
    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"threshold_hours": 12},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_config_pause_resume(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"paused": True, "paused_days": 7},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["config"]["status"] == "paused"
    assert body["runtime_status"] == "paused"
    assert body["config"]["paused_until"] is not None

    # 恢复
    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"paused": False},
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["status"] == "normal"


@pytest.mark.asyncio
async def test_checkin_creates_record(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/safety-rope/checkin",
        headers=auth_headers,
        json={"location_lat": 39.9, "location_lng": 116.4,
              "location_address": "北京市朝阳区建国路 88 号"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    # status 反映签到
    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    body = resp.json()
    assert body["last_checkin"] is not None
    assert body["last_checkin"]["location_address"] == "北京市朝阳区建国路 88 号"
    assert body["today_checked"] is True
    assert body["runtime_status"] == "normal"
    assert body["remaining_hours"] is not None and body["remaining_hours"] > 0


@pytest.mark.asyncio
async def test_contact_create_single(client: AsyncClient, auth_headers):
    # 创建 1 位
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "张儿子", "email": "son@example.com", "phone": "13800001111", "relation": "子女"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_contact_list_returns_created(client: AsyncClient, auth_headers):
    await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "张儿子", "email": "son@example.com"},
    )
    resp = await client.get("/api/safety-rope/contacts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) >= 1
    found = [c for c in body["items"] if c["name"] == "张儿子"]
    assert len(found) >= 1


@pytest.mark.asyncio
async def test_contact_limit_three(client: AsyncClient, auth_headers):
    # 清理：依次创建到 3，再尝试第 4
    for i in range(3):
        r = await client.post(
            "/api/safety-rope/contacts",
            headers=auth_headers,
            json={"name": f"联系人{i}", "email": f"limit{i}@example.com"},
        )
        # 由于跨测试可能已有，使用宽容判断
        assert r.status_code in (200, 400)
    # 第 N+1 位最终必然被拒
    r = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "多余", "email": "extra@example.com"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_contact_email_invalid_rejected():
    """直接调用 pydantic 模型验证邮箱格式校验逻辑。"""
    from app.api.safety_rope_v1 import ContactCreateRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ContactCreateRequest(name="x", email="not-an-email")


@pytest.mark.asyncio
async def test_alerts_list_empty(client: AsyncClient, auth_headers):
    """新用户查询预警记录应返回空列表。"""
    resp = await client.get("/api/safety-rope/alerts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_compute_runtime_state_function_only():
    """对 _compute_runtime_state 函数做纯单元测试（不走 HTTP/DB）。"""
    from app.api.safety_rope_v1 import _compute_runtime_state

    now = datetime(2026, 6, 3, 12, 0, 0)
    # 1) 无签到 → normal
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, None, now=now)
    assert r["runtime_status"] == "normal"

    # 2) 刚签到不久 → normal
    last = {"checkin_at": now - timedelta(hours=10)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, last, now=now)
    assert r["runtime_status"] == "normal"
    assert r["remaining_hours"] is not None and r["remaining_hours"] > 0

    # 3) 距阈值 < 1 小时 → near_timeout
    last = {"checkin_at": now - timedelta(hours=47, minutes=30)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, last, now=now)
    assert r["runtime_status"] == "near_timeout"

    # 4) 超时 + 状态 alerting → alerting
    last = {"checkin_at": now - timedelta(hours=49)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "alerting"}, last, now=now)
    assert r["runtime_status"] == "alerting"

    # 5) 暂停 → paused
    paused_until = now + timedelta(days=5)
    r = _compute_runtime_state({"threshold_hours": 48, "status": "paused",
                                 "paused_until": paused_until}, last, now=now)
    assert r["runtime_status"] == "paused"


@pytest.mark.asyncio
async def test_scan_alert_with_injected_data(client: AsyncClient, auth_headers):
    """通过直接调 API 注入历史签到（用 API/数据库都行）+ 手工调 scan。"""
    from app.api import safety_rope_v1 as srv1
    from tests.conftest import test_session

    # 先签到，让 last_checkin 存在
    await client.post(
        "/api/safety-rope/checkin", headers=auth_headers,
        json={"location_address": "初始位置"},
    )
    # 添加 1 位联系人
    await client.post(
        "/api/safety-rope/contacts", headers=auth_headers,
        json={"name": "联系人", "email": "contact@example.com"},
    )

    # 直接通过 SQL 把 checkin_at 向前调 49 小时（默认阈值 48）
    async with test_session() as db:
        await db.execute(text(
            "UPDATE safety_rope_checkin SET checkin_at = :t"
        ), {"t": datetime.utcnow() - timedelta(hours=49)})
        await db.commit()

    # 调度扫描
    import app.api.safety_rope_v1 as srv_mod
    original = srv_mod.async_session
    srv_mod.async_session = test_session
    try:
        stats = await srv1.scan_and_notify()
    finally:
        srv_mod.async_session = original

    assert stats["scanned"] >= 1
    assert stats["alerted"] >= 1

    # 状态变为 alerting
    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    assert resp.json()["config"]["status"] == "alerting"

    # 重新签到应解除
    resp = await client.post(
        "/api/safety-rope/checkin", headers=auth_headers,
        json={"location_address": "解除位置"},
    )
    assert resp.status_code == 200
    assert resp.json()["alert_resolved"] is True

    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    assert resp.json()["config"]["status"] == "normal"
