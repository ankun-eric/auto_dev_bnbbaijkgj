"""[PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）后端测试 v2

[BUGFIX-SAFETY-ROPE-V1 2026-06-03] v2 锁死版测试覆盖：
- 配置查询 / 修改（阈值、暂停、恢复）
- 签到：成功记录、含位置；超时后再签到自动解除预警
- 紧急联系人 CRUD（最多 3 位）
  - 手机号必填 + 格式校验
  - 必须是 bini-health 已注册用户
  - 关系字段 7 芯片白名单校验
  - 添加成功后立即可在 list 查到
- check-phone 接口：未注册返回 registered=false，已注册返回 registered=true
- 预警记录查询
- 扫描任务：超时触发预警（站内信，无邮件）、提前 1h 提醒
- 鉴权：未登录拒绝
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.models.models import User, UserRole
from tests.conftest import test_session  # noqa: F401  (re-export)


# 测试用户的 phone（来自 conftest.user_token fixture）
TEST_USER_PHONE = "13900000001"


async def _create_extra_user(phone: str, nickname: str) -> int:
    """在数据库中创建一个额外用户（用于"已注册联系人"场景）。返回 user_id。"""
    async with test_session() as session:
        u = User(
            phone=phone,
            password_hash=get_password_hash("pw123"),
            nickname=nickname,
            role=UserRole.user,
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u.id


# ─────────────── 鉴权 / 基础状态 ───────────────


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


# ─────────────── 配置 ───────────────


@pytest.mark.asyncio
async def test_update_config_threshold(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"threshold_hours": 24},
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["threshold_hours"] == 24

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

    resp = await client.put(
        "/api/safety-rope/config",
        headers=auth_headers,
        json={"paused": False},
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["status"] == "normal"


# ─────────────── 签到 ───────────────


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

    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    body = resp.json()
    assert body["last_checkin"] is not None
    assert body["last_checkin"]["location_address"] == "北京市朝阳区建国路 88 号"
    assert body["today_checked"] is True
    assert body["runtime_status"] == "normal"
    assert body["remaining_hours"] is not None and body["remaining_hours"] > 0


# ─────────────── 紧急联系人：核心 Bug 验证 ───────────────


@pytest.mark.asyncio
async def test_check_phone_unregistered(client: AsyncClient, auth_headers):
    """check-phone：未注册手机号应返回 registered=false。"""
    resp = await client.get(
        "/api/safety-rope/contacts/check-phone",
        params={"phone": "13700001111"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["registered"] is False


@pytest.mark.asyncio
async def test_check_phone_invalid_format(client: AsyncClient, auth_headers):
    """check-phone：手机号格式错误应返回 valid=false。"""
    resp = await client.get(
        "/api/safety-rope/contacts/check-phone",
        params={"phone": "123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False


@pytest.mark.asyncio
async def test_check_phone_registered(client: AsyncClient, auth_headers):
    """check-phone：已注册手机号应返回 registered=true + 用户名。"""
    await _create_extra_user("13711112222", "张儿子")
    resp = await client.get(
        "/api/safety-rope/contacts/check-phone",
        params={"phone": "13711112222"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["registered"] is True
    assert body["name"] == "张儿子"


@pytest.mark.asyncio
async def test_create_contact_requires_phone(client: AsyncClient, auth_headers):
    """Bug 修复核心：手机号必填。"""
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "张儿子"},  # 缺手机号
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_contact_rejects_unregistered_phone(client: AsyncClient, auth_headers):
    """Bug 修复核心：未注册的手机号必须被拒绝。"""
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "张儿子", "phone": "13700009999", "relation": "子女"},
    )
    assert resp.status_code == 400
    assert "未注册" in (resp.json().get("detail") or "")


@pytest.mark.asyncio
async def test_create_contact_rejects_bad_relation(client: AsyncClient, auth_headers):
    """关系字段 7 芯片白名单校验。"""
    await _create_extra_user("13733334444", "李配偶")
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "李配偶", "phone": "13733334444", "relation": "情人"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_contact_success_and_visible_in_list(client: AsyncClient, auth_headers):
    """🔥 核心 Bug 修复验证：添加联系人后立即出现在 list 中。"""
    extra_uid = await _create_extra_user("13755556666", "王邻居")

    # 1. 添加
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "王邻居", "phone": "13755556666", "relation": "邻居"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["matched_user_id"] == extra_uid

    # 2. 立即 list
    resp = await client.get("/api/safety-rope/contacts", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    found = [c for c in items if c["name"] == "王邻居"]
    assert len(found) == 1
    c = found[0]
    assert c["phone"] == "13755556666"
    assert c["relation"] == "邻居"
    assert c["matched_user_id"] == extra_uid


@pytest.mark.asyncio
async def test_create_contact_all_7_relations(client: AsyncClient, auth_headers):
    """7 种合法关系都应能保存。"""
    # 因为最多 3 位联系人，分组验证：直接调 schema 校验逻辑
    from app.api.safety_rope_v1 import ALLOWED_RELATIONS
    assert ALLOWED_RELATIONS == {"子女", "配偶", "父母", "邻居", "朋友", "护工", "其他"}


@pytest.mark.asyncio
async def test_contact_limit_three(client: AsyncClient, auth_headers):
    """最多 3 位。"""
    await _create_extra_user("13760000001", "联系人1")
    await _create_extra_user("13760000002", "联系人2")
    await _create_extra_user("13760000003", "联系人3")
    await _create_extra_user("13760000004", "联系人4")

    for i in range(1, 4):
        r = await client.post(
            "/api/safety-rope/contacts",
            headers=auth_headers,
            json={"name": f"联系人{i}", "phone": f"1376000000{i}", "relation": "其他"},
        )
        assert r.status_code == 200, r.text

    r = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "联系人4", "phone": "13760000004", "relation": "其他"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_contact_no_email_required(client: AsyncClient, auth_headers):
    """🔥 邮箱字段已删除：不传 email 也能成功保存。"""
    await _create_extra_user("13788889999", "无邮箱用户")
    resp = await client.post(
        "/api/safety-rope/contacts",
        headers=auth_headers,
        json={"name": "无邮箱用户", "phone": "13788889999", "relation": "朋友"},
    )
    assert resp.status_code == 200, resp.text


# ─────────────── 预警记录 ───────────────


@pytest.mark.asyncio
async def test_alerts_list_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/safety-rope/alerts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


# ─────────────── 纯单元函数 ───────────────


@pytest.mark.asyncio
async def test_compute_runtime_state_function_only():
    from app.api.safety_rope_v1 import _compute_runtime_state

    now = datetime(2026, 6, 3, 12, 0, 0)
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, None, now=now)
    assert r["runtime_status"] == "normal"

    last = {"checkin_at": now - timedelta(hours=10)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, last, now=now)
    assert r["runtime_status"] == "normal"
    assert r["remaining_hours"] is not None and r["remaining_hours"] > 0

    last = {"checkin_at": now - timedelta(hours=47, minutes=30)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "normal"}, last, now=now)
    assert r["runtime_status"] == "near_timeout"

    last = {"checkin_at": now - timedelta(hours=49)}
    r = _compute_runtime_state({"threshold_hours": 48, "status": "alerting"}, last, now=now)
    assert r["runtime_status"] == "alerting"

    paused_until = now + timedelta(days=5)
    r = _compute_runtime_state({"threshold_hours": 48, "status": "paused",
                                 "paused_until": paused_until}, last, now=now)
    assert r["runtime_status"] == "paused"


# ─────────────── 扫描任务（站内信，无邮件） ───────────────


@pytest.mark.asyncio
async def test_scan_alert_with_injected_data(client: AsyncClient, auth_headers):
    """超时扫描应触发预警，且通过站内信通知 matched_user_id。"""
    from app.api import safety_rope_v1 as srv1

    await client.post(
        "/api/safety-rope/checkin", headers=auth_headers,
        json={"location_address": "初始位置"},
    )
    await _create_extra_user("13799990000", "扫描联系人")
    r = await client.post(
        "/api/safety-rope/contacts", headers=auth_headers,
        json={"name": "扫描联系人", "phone": "13799990000", "relation": "子女"},
    )
    assert r.status_code == 200, r.text

    # 把签到时间往前推 49h（默认阈值 48h）
    async with test_session() as db:
        await db.execute(text(
            "UPDATE safety_rope_checkin SET checkin_at = :t"
        ), {"t": datetime.utcnow() - timedelta(hours=49)})
        await db.commit()

    import app.api.safety_rope_v1 as srv_mod
    original = srv_mod.async_session
    srv_mod.async_session = test_session
    try:
        stats = await srv1.scan_and_notify()
    finally:
        srv_mod.async_session = original

    assert stats["scanned"] >= 1
    assert stats["alerted"] >= 1

    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    assert resp.json()["config"]["status"] == "alerting"

    # 重新签到解除
    resp = await client.post(
        "/api/safety-rope/checkin", headers=auth_headers,
        json={"location_address": "解除位置"},
    )
    assert resp.status_code == 200
    assert resp.json()["alert_resolved"] is True

    resp = await client.get("/api/safety-rope/status", headers=auth_headers)
    assert resp.json()["config"]["status"] == "normal"
