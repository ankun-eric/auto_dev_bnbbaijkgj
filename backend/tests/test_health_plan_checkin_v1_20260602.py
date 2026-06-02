"""
[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 健康打卡（重做版）后端测试

覆盖：
1. 创建/查看/编辑/删除打卡计划
2. 删除计划时同步清除打卡记录
3. 日打卡
4. 补卡：3 天内允许 / 超出报错 / 今天不允许 / 未来不允许
5. 总览接口
6. 月历接口
7. 成果汇总接口
8. 管理端只读接口
"""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import HealthCheckInItem, HealthCheckInRecord


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.asyncio
async def test_create_and_list_checkin_plan(client: AsyncClient, auth_headers):
    payload = {
        "name": "每天喝 8 杯水",
        "repeat_frequency": "daily",
        "start_date": _today(),
        "end_date": None,
    }
    res = await client.post("/api/health-plan/checkin-items", json=payload, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "每天喝 8 杯水"
    assert body["repeat_frequency"] == "daily"
    assert body["start_date"] == _today()

    lst = await client.get("/api/health-plan/checkin-items", headers=auth_headers)
    assert lst.status_code == 200
    items = lst.json()["items"]
    assert any(i["id"] == body["id"] for i in items)


@pytest.mark.asyncio
async def test_create_weekly_plan_with_target_count(client: AsyncClient, auth_headers):
    payload = {
        "name": "每周锻炼 3 次",
        "repeat_frequency": "weekly",
        "weekly_target_count": 3,
        "start_date": _today(),
    }
    res = await client.post("/api/health-plan/checkin-items", json=payload, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["repeat_frequency"] == "weekly"
    assert body["weekly_target_count"] == 3


@pytest.mark.asyncio
async def test_update_and_delete_plan_cascades_records(client: AsyncClient, auth_headers, db_session):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "冥想", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    item_id = create.json()["id"]

    # 打个卡
    await client.post(f"/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=auth_headers)
    rec = await db_session.execute(
        select(HealthCheckInRecord).where(HealthCheckInRecord.item_id == item_id)
    )
    assert rec.scalar_one_or_none() is not None

    # 编辑
    upd = await client.put(
        f"/api/health-plan/checkin-items/{item_id}",
        json={"name": "晨间冥想", "weekly_target_count": 5, "repeat_frequency": "weekly"},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "晨间冥想"

    # 删除
    rm = await client.delete(f"/api/health-plan/checkin-items/{item_id}", headers=auth_headers)
    assert rm.status_code == 200

    rec2 = await db_session.execute(
        select(HealthCheckInRecord).where(HealthCheckInRecord.item_id == item_id)
    )
    assert rec2.scalar_one_or_none() is None  # 记录已被清除


@pytest.mark.asyncio
async def test_today_checkin(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "走 6000 步", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    item_id = create.json()["id"]

    r1 = await client.post(f"/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=auth_headers)
    assert r1.status_code == 200

    # 重复打卡应失败
    r2 = await client.post(f"/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=auth_headers)
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_makeup_within_3_days(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "拉伸", "repeat_frequency": "daily", "start_date": _days_ago(7)},
        headers=auth_headers,
    )
    item_id = create.json()["id"]

    # 补昨天
    r = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/makeup",
        json={"date": _days_ago(1)},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    # 补 3 天前 ok
    r3 = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/makeup",
        json={"date": _days_ago(3)},
        headers=auth_headers,
    )
    assert r3.status_code == 200

    # 补 4 天前应失败
    r4 = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/makeup",
        json={"date": _days_ago(4)},
        headers=auth_headers,
    )
    assert r4.status_code == 400


@pytest.mark.asyncio
async def test_makeup_today_forbidden(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "瑜伽", "repeat_frequency": "daily", "start_date": _days_ago(2)},
        headers=auth_headers,
    )
    item_id = create.json()["id"]
    r = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/makeup",
        json={"date": _today()},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_makeup_future_forbidden(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "p", "repeat_frequency": "daily"},
        headers=auth_headers,
    )
    item_id = create.json()["id"]
    r = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/makeup",
        json={"date": (date.today() + timedelta(days=1)).isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_overview_endpoint(client: AsyncClient, auth_headers):
    # 创建 2 个计划，打 1 个
    a = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "A", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "B", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    await client.post(f"/api/health-plan/checkin-items/{a.json()['id']}/checkin", json={}, headers=auth_headers)

    res = await client.get("/api/health-plan/checkin-overview", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["active_count"] >= 2
    assert body["today_done_count"] >= 1
    assert "week_completion_rate" in body


@pytest.mark.asyncio
async def test_calendar_endpoint(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "X", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    item_id = create.json()["id"]
    await client.post(f"/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=auth_headers)

    today = date.today()
    res = await client.get(
        f"/api/health-plan/checkin-calendar?year={today.year}&month={today.month}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["year"] == today.year
    assert body["month"] == today.month
    assert any(d["date"] == today.isoformat() and d["count"] >= 1 for d in body["days"])


@pytest.mark.asyncio
async def test_stats_summary(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "Q", "repeat_frequency": "daily", "start_date": _days_ago(2)},
        headers=auth_headers,
    )
    item_id = create.json()["id"]
    await client.post(f"/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=auth_headers)

    res = await client.get("/api/health-plan/checkin-stats-summary", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["streak_days"] >= 1
    assert body["total_checkins"] >= 1
    assert isinstance(body["plans"], list)


@pytest.mark.asyncio
async def test_admin_user_checkin_plans_readonly(client: AsyncClient, auth_headers, admin_headers):
    await client.post(
        "/api/health-plan/checkin-items",
        json={"name": "admin-test", "repeat_frequency": "daily", "start_date": _today()},
        headers=auth_headers,
    )
    res = await client.get("/api/admin/health-plan/user-checkin-plans", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert any(it["name"] == "admin-test" for it in body["items"])
