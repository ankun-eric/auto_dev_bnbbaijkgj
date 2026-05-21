"""[PRD-AI-HOME-OPTIM-V4 2026-05-21] AI 首页体验优化 v4 后端接口测试。

覆盖：
- GET  /api/ai-home/refresh-config 返回 60 分钟阈值，且 session_refresh_ms = minutes * 60000
- POST /api/ai-home/track 11 个合法事件名全部接受 + 未识别事件名仍返回 200 ok=true
- POST /api/ai-home/track 携带 platform / payload 字段并能正确回显 received_at / event
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_config_default_60min(client: AsyncClient):
    """阈值默认 60 分钟，session_refresh_ms = 60 * 60000 = 3_600_000"""
    res = await client.get("/api/ai-home/refresh-config")
    assert res.status_code == 200
    body = res.json()
    assert body["session_refresh_minutes"] == 60
    assert body["session_refresh_ms"] == 60 * 60 * 1000
    assert body["enabled"] is True


@pytest.mark.asyncio
async def test_refresh_config_no_auth_required(client: AsyncClient):
    """该接口允许匿名调用，便于前端在登录前完成静态判断"""
    res = await client.get("/api/ai-home/refresh-config")
    assert res.status_code == 200


VALID_EVENTS = [
    "refresh_triggered",
    "refresh_skipped",
    "switch_consultant",
    "switch_undo_clicked",
    "switch_undo_expired",
    "floating_ball_shown",
    "floating_ball_clicked",
    "floating_ball_panel_action",
    "first_guide_shown",
    "refresh_anomaly",
    "system_message_visible",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("event", VALID_EVENTS)
async def test_track_valid_events(client: AsyncClient, event):
    """11 个合法事件名都能被接受。"""
    res = await client.post(
        "/api/ai-home/track",
        json={"event": event, "platform": "h5", "payload": {"k": "v"}},
    )
    assert res.status_code == 200, f"event={event}: {res.text}"
    body = res.json()
    assert body["ok"] is True
    assert body["event"] == event
    assert body["platform"] == "h5"
    assert isinstance(body["received_at"], str) and body["received_at"]


@pytest.mark.asyncio
async def test_track_unknown_event_still_ok(client: AsyncClient):
    """未识别事件名仍记录但加 [unknown] 前缀，整体仍返回 200 ok=true。"""
    res = await client.post(
        "/api/ai-home/track",
        json={"event": "totally_made_up_event", "platform": "miniprogram"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["event"] == "totally_made_up_event"


@pytest.mark.asyncio
async def test_track_payload_optional(client: AsyncClient):
    """payload 缺失时也能正常处理（默认空 dict）。"""
    res = await client.post(
        "/api/ai-home/track",
        json={"event": "switch_consultant", "platform": "flutter"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["platform"] == "flutter"


@pytest.mark.asyncio
async def test_track_platform_optional(client: AsyncClient):
    """platform 缺失时也能正常处理（platform=null）。"""
    res = await client.post(
        "/api/ai-home/track",
        json={"event": "first_guide_shown"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["platform"] is None


@pytest.mark.asyncio
async def test_refresh_config_keys_complete(client: AsyncClient):
    """响应字段必须包含 PRD 约定的 3 项：minutes / ms / enabled。"""
    res = await client.get("/api/ai-home/refresh-config")
    body = res.json()
    assert set(["session_refresh_minutes", "session_refresh_ms", "enabled"]).issubset(body.keys())
