"""[PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] 健康档案页面优化 V2 后端验收测试

覆盖：
- /api/family-archive-v2/members：成员徽章 / 配色索引 / 守护状态
- /api/family-archive-v2/hero-counts：Hero 三入口数量
- /api/family-archive-v2/member/{id}/devices：设备列表（本人可管理 / 其他只读）
- /api/family-archive-v2/member/{id}/alert-settings：GET + PUT
- /api/family-archive-v2/member/{id}/alert-history
- /api/family-archive-v2/member/{id}/unbind/send-code
- /api/family-archive-v2/member/{id}/unbind/confirm
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
def _h(auth_headers):
    return auth_headers


@pytest.mark.asyncio
async def test_members_self_first_with_badge(client: AsyncClient, _h):
    # 新增一位"老婆"成员
    await client.post(
        "/api/family/members",
        json={"relationship_type": "老婆", "nickname": "丽丽", "gender": "female"},
        headers=_h,
    )
    r = await client.get("/api/family-archive-v2/members", headers=_h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 1
    # 本人是否第一
    if any(it["is_self"] for it in items):
        assert items[0]["is_self"] is True
    # 至少返回 avatar_color_index 与 relation_badge_char
    for it in items:
        assert "avatar_color_index" in it
        assert it["avatar_color_index"] in (0, 1, 2, 3, 4)
        assert "relation_badge_char" in it
        assert "guard_status" in it


@pytest.mark.asyncio
async def test_badge_char_mapping(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "爸爸", "nickname": "老爸"},
        headers=_h,
    )
    assert r.status_code == 200, r.text
    r = await client.get("/api/family-archive-v2/members", headers=_h)
    items = r.json()["items"]
    badges = {(it["relationship_type"], it["relation_badge_char"]) for it in items}
    # 爸爸→爸
    assert any(rel == "爸爸" and ch == "爸" for rel, ch in badges)


@pytest.mark.asyncio
async def test_hero_counts_default(client: AsyncClient, _h):
    r = await client.get("/api/family-archive-v2/hero-counts", headers=_h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "medication_today_count" in d
    assert "device_count" in d
    assert "family_member_count" in d
    assert d["medication_today_count"] >= 0
    assert d["device_count"] >= 0
    assert d["family_member_count"] >= 1


@pytest.mark.asyncio
async def test_member_devices_readonly_for_other(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "妈妈", "nickname": "老妈"},
        headers=_h,
    )
    member_id = r.json()["id"]
    r2 = await client.get(f"/api/family-archive-v2/member/{member_id}/devices", headers=_h)
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["readonly"] is True
    assert d["is_self"] is False
    assert isinstance(d["items"], list)


@pytest.mark.asyncio
async def test_alert_settings_get_and_put(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "儿子", "nickname": "小宝"},
        headers=_h,
    )
    member_id = r.json()["id"]
    g = await client.get(f"/api/family-archive-v2/member/{member_id}/alert-settings", headers=_h)
    assert g.status_code == 200, g.text
    d = g.json()
    assert d["ai_call_enabled"] is False
    assert d["ai_call_timing"] == "on_time"
    assert d["guardian_alert_minutes"] == 5
    assert d["show_guardian_alert"] is True

    # PUT
    p = await client.put(
        f"/api/family-archive-v2/member/{member_id}/alert-settings",
        json={"ai_call_enabled": True, "ai_call_timing": "delay_10", "guardian_alert_minutes": 15},
        headers=_h,
    )
    assert p.status_code == 200, p.text
    d2 = p.json()
    assert d2["ai_call_enabled"] is True
    assert d2["ai_call_timing"] == "delay_10"
    assert d2["guardian_alert_minutes"] == 15


@pytest.mark.asyncio
async def test_alert_settings_invalid_value(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "妹妹", "nickname": "小妹"},
        headers=_h,
    )
    member_id = r.json()["id"]
    p = await client.put(
        f"/api/family-archive-v2/member/{member_id}/alert-settings",
        json={"ai_call_timing": "delay_100"},
        headers=_h,
    )
    assert p.status_code == 400

    p2 = await client.put(
        f"/api/family-archive-v2/member/{member_id}/alert-settings",
        json={"guardian_alert_minutes": 7},
        headers=_h,
    )
    assert p2.status_code == 400


@pytest.mark.asyncio
async def test_alert_history_empty(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "姐姐", "nickname": "大姐"},
        headers=_h,
    )
    member_id = r.json()["id"]
    h = await client.get(f"/api/family-archive-v2/member/{member_id}/alert-history", headers=_h)
    assert h.status_code == 200
    assert h.json()["items"] == []


@pytest.mark.asyncio
async def test_unbind_unguarded_member_400(client: AsyncClient, _h):
    r = await client.post(
        "/api/family/members",
        json={"relationship_type": "爷爷", "nickname": "爷爷"},
        headers=_h,
    )
    member_id = r.json()["id"]
    # 未守护的成员尝试发送解绑验证码
    r2 = await client.post(
        f"/api/family-archive-v2/member/{member_id}/unbind/send-code",
        headers=_h,
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_member_self_alert_no_guardian_alert(client: AsyncClient, _h):
    # 找到本人成员
    r = await client.get("/api/family-archive-v2/members", headers=_h)
    items = r.json()["items"]
    self_item = next((it for it in items if it["is_self"]), None)
    if not self_item:
        pytest.skip("本人 family_member 不存在，跳过")
    member_id = self_item["id"]
    g = await client.get(f"/api/family-archive-v2/member/{member_id}/alert-settings", headers=_h)
    assert g.status_code == 200
    assert g.json()["show_guardian_alert"] is False


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    r = await client.get("/api/family-archive-v2/members")
    assert r.status_code in (401, 403)
