"""
[PRD-AIHOME-CARE-V1] AI 首页关怀版 v1.0 - 后端测试用例
覆盖 PRD §10.1 关键验收点：
- AC2: 跳过默认值 standard
- AC3: 模式持久化
- AC11: 高危词单触
- AC12: 双词触发
- AC13: 否定词过滤
- AC14: 疑问句过滤
- AC18: 关键词热配置
"""
import pytest
from httpx import AsyncClient


# ============ 用户偏好测试 ============
@pytest.mark.asyncio
async def test_get_default_user_preferences(client: AsyncClient, auth_headers):
    """AC2: 新用户首次访问偏好接口，默认 ui_mode=standard"""
    resp = await client.get("/api/care-v1/user-preferences", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ui_mode"] == "standard"
    assert data["ui_mode_first_choice"] is False
    assert data["sos_floating_enabled"] is True


@pytest.mark.asyncio
async def test_switch_to_care_mode(client: AsyncClient, auth_headers):
    """AC3: 切换到关怀模式后持久化"""
    resp = await client.put(
        "/api/care-v1/user-preferences/ui-mode",
        json={"ui_mode": "care", "first_choice": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["ui_mode"] == "care"

    # 再次 GET 验证持久化
    resp2 = await client.get("/api/care-v1/user-preferences", headers=auth_headers)
    assert resp2.json()["data"]["ui_mode"] == "care"
    assert resp2.json()["data"]["ui_mode_first_choice"] is True


@pytest.mark.asyncio
async def test_invalid_ui_mode_rejected(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/care-v1/user-preferences/ui-mode",
        json={"ui_mode": "invalid"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sos_floating_toggle(client: AsyncClient, auth_headers):
    """SOS 悬浮球开关可切换"""
    resp = await client.put(
        "/api/care-v1/user-preferences/ui-mode",
        json={"ui_mode": "care", "sos_floating_enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sos_floating_enabled"] is False


# ============ SOS 关键词测试 ============
@pytest.mark.asyncio
async def test_get_default_keywords(client: AsyncClient):
    """关键词配置有默认种子值"""
    resp = await client.get("/api/care-v1/sos/keywords")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "high_risk" in data
    assert "symptom" in data
    assert "degree" in data
    assert "negation" in data
    assert "救命" in data["high_risk"]
    assert "胸闷" in data["symptom"]
    assert "厉害" in data["degree"]


@pytest.mark.asyncio
async def test_admin_add_keyword_hot_config(client: AsyncClient, admin_headers):
    """AC18: 后台修改关键词后客户端可立即拉到新词"""
    resp = await client.post(
        "/api/care-v1/admin/sos/keywords",
        json={"category": "high_risk", "keyword": "测试高危词XYZ", "enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    # 再次获取
    resp2 = await client.get("/api/care-v1/sos/keywords")
    assert "测试高危词XYZ" in resp2.json()["data"]["high_risk"]


# ============ SOS 触发检测测试 ============
@pytest.mark.asyncio
async def test_sos_high_risk_single(client: AsyncClient):
    """AC11: 高危词单触"""
    resp = await client.post("/api/care-v1/sos/detect", json={"text": "救命啊"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["hit"] is True
    assert data["rule"] == "high_risk"
    assert "救命" in data["matched"]


@pytest.mark.asyncio
async def test_sos_combo_trigger(client: AsyncClient):
    """AC12: 普通症状词 + 程度词双触"""
    resp = await client.post("/api/care-v1/sos/detect", json={"text": "胸闷得厉害"})
    data = resp.json()["data"]
    assert data["hit"] is True
    assert data["rule"] == "combo"


@pytest.mark.asyncio
async def test_sos_negation_filter(client: AsyncClient):
    """AC13: 否定词过滤"""
    resp = await client.post("/api/care-v1/sos/detect", json={"text": "胸口不闷"})
    data = resp.json()["data"]
    assert data["hit"] is False
    assert "否定词" in data["reason"]


@pytest.mark.asyncio
async def test_sos_question_filter(client: AsyncClient):
    """AC14: 疑问句过滤"""
    resp = await client.post("/api/care-v1/sos/detect", json={"text": "是不是要胸闷？"})
    data = resp.json()["data"]
    assert data["hit"] is False
    assert "疑问句" in data["reason"]


@pytest.mark.asyncio
async def test_sos_single_symptom_no_trigger(client: AsyncClient):
    """规则 3: 单独症状词不触发 SOS"""
    resp = await client.post("/api/care-v1/sos/detect", json={"text": "今天有点头晕"})
    data = resp.json()["data"]
    assert data["hit"] is False


@pytest.mark.asyncio
async def test_sos_empty_text(client: AsyncClient):
    resp = await client.post("/api/care-v1/sos/detect", json={"text": ""})
    assert resp.status_code == 200
    assert resp.json()["data"]["hit"] is False


# ============ SOS 事件测试 ============
@pytest.mark.asyncio
async def test_create_and_cancel_sos_event(client: AsyncClient, auth_headers):
    """AC15: 5 秒撤销窗口"""
    resp = await client.post(
        "/api/care-v1/sos/events",
        json={"trigger_source": "floating_button"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    event_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "pending"

    # 取消
    resp2 = await client.put(
        f"/api/care-v1/sos/events/{event_id}/resolve",
        json={"status": "cancelled", "countdown_remaining_ms": 3500},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_dispatch_120(client: AsyncClient, auth_headers):
    """AC17: 呼叫 120 状态流转"""
    resp = await client.post(
        "/api/care-v1/sos/events",
        json={"trigger_source": "keyword_high_risk", "trigger_keyword": "救命", "trigger_text": "救命啊"},
        headers=auth_headers,
    )
    event_id = resp.json()["data"]["id"]
    resp2 = await client.put(
        f"/api/care-v1/sos/events/{event_id}/resolve",
        json={"status": "dispatched_120"},
        headers=auth_headers,
    )
    assert resp2.json()["data"]["status"] == "dispatched_120"


@pytest.mark.asyncio
async def test_list_sos_events(client: AsyncClient, auth_headers):
    """SOS 事件列表"""
    # 先创建一条
    await client.post(
        "/api/care-v1/sos/events",
        json={"trigger_source": "floating_button"},
        headers=auth_headers,
    )
    resp = await client.get("/api/care-v1/sos/events", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_sos_resolve_invalid_status(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/care-v1/sos/events",
        json={"trigger_source": "floating_button"},
        headers=auth_headers,
    )
    eid = resp.json()["data"]["id"]
    resp2 = await client.put(
        f"/api/care-v1/sos/events/{eid}/resolve",
        json={"status": "INVALID"},
        headers=auth_headers,
    )
    assert resp2.status_code == 400


# ============ AI 主动卡片测试 ============
@pytest.mark.asyncio
async def test_get_proactive_cards(client: AsyncClient, auth_headers):
    """AC8 + AC9: 健康简报含血糖，2x2 网格"""
    resp = await client.get("/api/care-v1/home/proactive-cards", headers=auth_headers)
    assert resp.status_code == 200
    cards = resp.json()["data"]
    # 健康简报四宫格
    assert "health_brief" in cards
    hb = cards["health_brief"]
    assert "blood_pressure" in hb
    assert "blood_glucose" in hb  # AC8 含血糖
    assert "sleep" in hb
    assert "steps" in hb
    # 血糖 7.2 >7.0 应标记 abnormal=True (AC9)
    assert hb["blood_glucose"]["abnormal"] is True
    # 用药提醒
    assert "med_reminder" in cards
    assert isinstance(cards["med_reminder"]["items"], list)
    # 居家安全 (AC10 烟感电量 18 < 20 异常)
    assert "home_safety" in cards
    devices = cards["home_safety"]["devices"]
    smoke = next((d for d in devices if d["type"] == "smoke_detector"), None)
    if smoke and smoke["battery"] < 20:
        assert smoke["abnormal"] is True


# ============ 欢迎区测试 ============
@pytest.mark.asyncio
async def test_get_welcome(client: AsyncClient, auth_headers):
    """时段问候 + 称呼"""
    resp = await client.get("/api/care-v1/home/welcome", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "nickname" in data
    assert "greeting" in data
    assert "main_text" in data


# ============ 未登录访问保护 ============
@pytest.mark.asyncio
async def test_get_preferences_unauthorized(client: AsyncClient):
    resp = await client.get("/api/care-v1/user-preferences")
    assert resp.status_code == 401
