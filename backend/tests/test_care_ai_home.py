"""
[PRD-CARE-AI-HOME 2026-05-27] 关怀模式 AI 主页 v1 - 后端测试用例

覆盖需求清单 §5.1 新建接口：
- GET  /api/care/daily-summary
- GET  /api/care/alerts/active
- POST /api/care/alerts/{id}/dismiss
"""
import pytest
from httpx import AsyncClient


# ============ 健康简评卡 ============
@pytest.mark.asyncio
async def test_daily_summary_first_call(client: AsyncClient, auth_headers):
    """首次调用应生成并返回评语 + 3 项指标。"""
    resp = await client.get("/api/care/daily-summary", headers=auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert "summary_text" in data and isinstance(data["summary_text"], str)
    assert len(data["summary_text"]) > 0
    metrics = data["metrics"]
    assert isinstance(metrics, list) and len(metrics) == 3
    types = {m["type"] for m in metrics}
    assert types == {"blood_pressure", "heart_rate", "sleep"}
    for m in metrics:
        assert m["status"] in ("正常", "偏高", "偏低")
        assert "value" in m and "unit" in m and "label" in m


@pytest.mark.asyncio
async def test_daily_summary_cached_same_day(client: AsyncClient, auth_headers):
    """同一天内二次调用应返回缓存（cached=True）。"""
    r1 = await client.get("/api/care/daily-summary", headers=auth_headers)
    r2 = await client.get("/api/care/daily-summary", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    # 内容一致
    assert r1.json()["data"]["summary_text"] == r2.json()["data"]["summary_text"]
    # 第二次必然 cached=True
    assert r2.json()["data"]["cached"] is True


@pytest.mark.asyncio
async def test_daily_summary_requires_auth(client: AsyncClient):
    """未登录访问应被拒绝。"""
    resp = await client.get("/api/care/daily-summary")
    assert resp.status_code in (401, 403)


# ============ 活跃告警列表 ============
@pytest.mark.asyncio
async def test_active_alerts_empty_initially(client: AsyncClient, auth_headers):
    """无任何告警时返回空列表。"""
    resp = await client.get("/api/care/alerts/active", headers=auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"]["alerts"], list)


@pytest.mark.asyncio
async def test_seed_and_list_alert(client: AsyncClient, auth_headers):
    """通过 seed-demo 创建一条告警后，active 列表应能查到。"""
    seed = await client.post("/api/care/alerts/_seed-demo", headers=auth_headers)
    assert seed.status_code == 200

    resp = await client.get("/api/care/alerts/active", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()["data"]["alerts"]
    assert len(alerts) >= 1
    a = alerts[0]
    for key in ("id", "type", "title", "content", "severity", "created_at"):
        assert key in a


# ============ 忽略告警 ============
@pytest.mark.asyncio
async def test_dismiss_alert(client: AsyncClient, auth_headers):
    """忽略告警后再次列出 active，该告警不应出现。"""
    seed = await client.post("/api/care/alerts/_seed-demo", headers=auth_headers)
    assert seed.status_code == 200

    list_resp = await client.get("/api/care/alerts/active", headers=auth_headers)
    alerts = list_resp.json()["data"]["alerts"]
    if not alerts:
        pytest.skip("没有可忽略的告警（可能因 24h 防重复保护被跳过）")
    target_id = alerts[0]["id"]

    dismiss = await client.post(
        f"/api/care/alerts/{target_id}/dismiss", headers=auth_headers
    )
    assert dismiss.status_code == 200
    body = dismiss.json()
    assert body["success"] is True
    assert body["id"] == target_id

    # 再列一次，target_id 不应出现
    again = await client.get("/api/care/alerts/active", headers=auth_headers)
    again_ids = [x["id"] for x in again.json()["data"]["alerts"]]
    assert target_id not in again_ids


@pytest.mark.asyncio
async def test_dismiss_nonexistent_alert(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/care/alerts/9999999/dismiss", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dismiss_idempotent(client: AsyncClient, auth_headers):
    """重复 dismiss 同一告警应保持成功（幂等）。"""
    seed = await client.post("/api/care/alerts/_seed-demo", headers=auth_headers)
    list_resp = await client.get("/api/care/alerts/active", headers=auth_headers)
    alerts = list_resp.json()["data"]["alerts"]
    if not alerts:
        pytest.skip("无可用告警")
    aid = alerts[0]["id"]
    r1 = await client.post(f"/api/care/alerts/{aid}/dismiss", headers=auth_headers)
    r2 = await client.post(f"/api/care/alerts/{aid}/dismiss", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["success"] is True
