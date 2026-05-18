"""[PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 健康档案页面优化 后端验收测试

覆盖用例：
1. AI 外呼配置 — 默认查询返回本人节点（enabled=False, dnd=22:00–07:00, call_target=self）
2. AI 外呼配置 — 更新本人配置（enabled True + dnd 时段）
3. AI 外呼配置 — 单点查询本人配置
4. AI 外呼配置 — call_target=guardian 但当前无守护关系 → 自动回退 'self'
5. AI 外呼配置 — 非本人且无守护关系 → 403
6. AI 外呼配置 — call_target 非法值 → 400
7. 守护人摘要 — guardian/summary 默认 0
8. family-members/guarded-flags — 默认返回所有家庭成员，guarded=False
9. medication-plans/hero-count — consultant_id=0(本人) 不报错且返回文案
10. medication-plans/hero-count — consultant_id=-1 兼容旧版（不过滤）
11. medication-plans/summary — consultant_id=0 不报错
12. guardian/devices — 非守护人 403
13. guardian/devices/remind-bind — 非守护人 403
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_aicall_default_settings_list(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/ai-call/settings", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)
    # 至少包含本人
    self_items = [it for it in data["items"] if it["is_self"]]
    assert len(self_items) >= 1
    s = self_items[0]
    assert s["enabled"] is False
    assert s["dnd_start"] == "22:00"
    assert s["dnd_end"] == "07:00"
    assert s["call_target"] == "self"


@pytest.mark.asyncio
async def test_aicall_update_self(client: AsyncClient, auth_headers, user_token):
    # 先获取本人 user_id
    me = await client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    uid = me.json().get("id") or me.json().get("user_id") or me.json().get("data", {}).get("id")
    if uid is None:
        # 兜底从 /api/health-archive/ai-call/settings 取
        r = await client.get("/api/health-archive/ai-call/settings", headers=auth_headers)
        items = r.json()["items"]
        uid = next(it["target_user_id"] for it in items if it["is_self"])
    r = await client.put(
        f"/api/health-archive/ai-call/settings/{uid}",
        json={"enabled": True, "dnd_start": "23:00", "dnd_end": "08:00", "call_target": "self"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enabled"] is True
    assert data["dnd_start"] == "23:00"
    assert data["dnd_end"] == "08:00"


@pytest.mark.asyncio
async def test_aicall_get_self_setting(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/ai-call/settings", headers=auth_headers)
    items = r.json()["items"]
    uid = next(it["target_user_id"] for it in items if it["is_self"])
    g = await client.get(f"/api/health-archive/ai-call/settings/{uid}", headers=auth_headers)
    assert g.status_code == 200
    d = g.json()
    assert d["is_self"] is True
    assert d["target_user_id"] == uid


@pytest.mark.asyncio
async def test_aicall_guardian_target_fallback_to_self(client: AsyncClient, auth_headers):
    """call_target=guardian 但当前是本人（无守护关系），自动回退为 self。"""
    r = await client.get("/api/health-archive/ai-call/settings", headers=auth_headers)
    items = r.json()["items"]
    uid = next(it["target_user_id"] for it in items if it["is_self"])
    r2 = await client.put(
        f"/api/health-archive/ai-call/settings/{uid}",
        json={"call_target": "guardian"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["call_target"] == "self"  # 自动回退


@pytest.mark.asyncio
async def test_aicall_other_user_403(client: AsyncClient, auth_headers):
    """目标 user_id 既不是本人也不是被守护对象 → 403"""
    r = await client.put(
        "/api/health-archive/ai-call/settings/999999",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_aicall_invalid_call_target(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/ai-call/settings", headers=auth_headers)
    items = r.json()["items"]
    uid = next(it["target_user_id"] for it in items if it["is_self"])
    r2 = await client.put(
        f"/api/health-archive/ai-call/settings/{uid}",
        json={"call_target": "invalid_value"},
        headers=auth_headers,
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_guardian_summary_default_zero(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/guardian/summary", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["managed_count"] == 0
    assert d["managed_user_ids"] == []


@pytest.mark.asyncio
async def test_family_members_guarded_flags_default(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/family-members/guarded-flags", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d
    # 所有成员的 guarded 默认为 False
    for it in d["items"]:
        assert it["guarded"] is False


@pytest.mark.asyncio
async def test_hero_count_consultant_self(client: AsyncClient, auth_headers):
    r = await client.get("/api/medication-plans/hero-count?consultant_id=0", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "display_text" in d
    assert d["display_text"].startswith("今日用药")


@pytest.mark.asyncio
async def test_hero_count_consultant_none_compat(client: AsyncClient, auth_headers):
    r = await client.get("/api/medication-plans/hero-count?consultant_id=-1", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "display_text" in d


@pytest.mark.asyncio
async def test_summary_consultant_self(client: AsyncClient, auth_headers):
    r = await client.get("/api/medication-plans/summary?consultant_id=0", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "items" in d
    assert isinstance(d["items"], list)


@pytest.mark.asyncio
async def test_guardian_devices_403(client: AsyncClient, auth_headers):
    r = await client.get("/api/health-archive/guardian/999999/devices", headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_guardian_remind_bind_403(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/health-archive/guardian/999999/devices/remind-bind", headers=auth_headers
    )
    assert r.status_code == 403
