"""
Non-UI integration tests for 打卡积分 (Check-in Points) feature.

Covers: admin rule config, points awarding on check-in (health / medication / plan task / quick),
daily limit logic, partial award, progress query, and points records.

Run with: pytest tests/test_checkin_points.py -v
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    HealthCheckInItem,
    MedicationReminder,
    SystemConfig,
    UserPlan,
    UserPlanTask,
)


# ── helpers ──


async def set_checkin_rules(
    client: AsyncClient,
    admin_headers: dict,
    *,
    enabled: str = "true",
    per_action: str = "5",
    daily_limit: str = "50",
):
    """Configure check-in points rules via the admin API."""
    resp = await client.post(
        "/api/admin/points/rules",
        headers=admin_headers,
        json={
            "checkin_points_enabled": enabled,
            "checkin_points_per_action": per_action,
            "checkin_points_daily_limit": daily_limit,
        },
    )
    assert resp.status_code == 200
    return resp


async def create_health_checkin_item(
    client: AsyncClient, auth_headers: dict, name: str = "早起打卡"
) -> int:
    """Create a health check-in item and return its id."""
    resp = await client.post(
        "/api/health-plan/checkin-items",
        headers=auth_headers,
        json={"name": name},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def do_health_checkin(
    client: AsyncClient, auth_headers: dict, item_id: int
) -> dict:
    """Perform a health habit check-in and return the response body."""
    resp = await client.post(
        f"/api/health-plan/checkin-items/{item_id}/checkin",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    return resp.json()


async def create_medication_reminder(
    client: AsyncClient,
    auth_headers: dict,
    name: str = "阿司匹林",
) -> int:
    """Create a medication reminder and return its id."""
    resp = await client.post(
        "/api/health-plan/medications",
        headers=auth_headers,
        json={
            "medicine_name": name,
            "dosage": "1片",
            "time_period": "早上",
            "remind_time": "08:00",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def create_user_plan_with_task(
    client: AsyncClient,
    auth_headers: dict,
    plan_name: str = "测试计划",
    task_name: str = "跑步",
) -> tuple[int, int]:
    """Create a user plan with one task. Returns (plan_id, task_id)."""
    resp = await client.post(
        "/api/health-plan/user-plans",
        headers=auth_headers,
        json={
            "plan_name": plan_name,
            "duration_days": 30,
            "tasks": [
                {"task_name": task_name, "target_value": 5000, "target_unit": "步", "sort_order": 0}
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    plan_id = data["id"]
    task_id = data["tasks"][0]["id"]
    return plan_id, task_id


# ── TC-001 ──


@pytest.mark.asyncio
async def test_tc001_admin_save_checkin_rules(
    client: AsyncClient, admin_headers: dict
):
    """TC-001: 管理员配置打卡积分规则 - 保存成功"""
    resp = await client.post(
        "/api/admin/points/rules",
        headers=admin_headers,
        json={
            "checkin_points_enabled": "true",
            "checkin_points_per_action": "5",
            "checkin_points_daily_limit": "20",
        },
    )
    assert resp.status_code == 200

    get_resp = await client.get("/api/admin/points/rules", headers=admin_headers)
    assert get_resp.status_code == 200
    rules = get_resp.json()["rules"]
    assert rules["checkin_points_enabled"] == "true"
    assert rules["checkin_points_per_action"] == "5"
    assert rules["checkin_points_daily_limit"] == "20"


# ── TC-002 ──


@pytest.mark.asyncio
async def test_tc002_disabled_no_points(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-002: 打卡积分开关关闭时，打卡不送积分"""
    await set_checkin_rules(client, admin_headers, enabled="false")

    item_id = await create_health_checkin_item(client, auth_headers, "饮水打卡")
    result = await do_health_checkin(client, auth_headers, item_id)

    assert result["points_earned"] == 0
    assert result["points_limit_reached"] is False


# ── TC-003 ──


@pytest.mark.asyncio
async def test_tc003_enabled_first_checkin_earns_points(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-003: 打卡积分开关开启时，首次打卡获得积分"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    item_id = await create_health_checkin_item(client, auth_headers, "冥想打卡")
    result = await do_health_checkin(client, auth_headers, item_id)

    assert result["points_earned"] == 5
    assert result["points_limit_reached"] is False


# ── TC-004 ──


@pytest.mark.asyncio
async def test_tc004_daily_limit_reached(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-004: 用户打卡积分累计达到上限后不再发放"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="10"
    )

    item1 = await create_health_checkin_item(client, auth_headers, "打卡A")
    item2 = await create_health_checkin_item(client, auth_headers, "打卡B")
    item3 = await create_health_checkin_item(client, auth_headers, "打卡C")

    r1 = await do_health_checkin(client, auth_headers, item1)
    assert r1["points_earned"] == 5
    assert r1["points_limit_reached"] is False

    r2 = await do_health_checkin(client, auth_headers, item2)
    assert r2["points_earned"] == 5
    assert r2["points_limit_reached"] is True

    r3 = await do_health_checkin(client, auth_headers, item3)
    assert r3["points_earned"] == 0
    assert r3["points_limit_reached"] is True


# ── TC-005 ──


@pytest.mark.asyncio
async def test_tc005_partial_points_when_limit_not_enough(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-005: 剩余积分不足一次完整发放时，发放剩余可得积分"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="8"
    )

    item1 = await create_health_checkin_item(client, auth_headers, "打卡X")
    item2 = await create_health_checkin_item(client, auth_headers, "打卡Y")

    r1 = await do_health_checkin(client, auth_headers, item1)
    assert r1["points_earned"] == 5

    r2 = await do_health_checkin(client, auth_headers, item2)
    assert r2["points_earned"] == 3
    assert r2["points_limit_reached"] is True


# ── TC-006 ──


@pytest.mark.asyncio
async def test_tc006_today_progress(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-006: 今日打卡积分进度查询"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    resp1 = await client.get(
        "/api/points/checkin/today-progress", headers=auth_headers
    )
    assert resp1.status_code == 200
    p1 = resp1.json()
    assert p1["earned_today"] == 0
    assert p1["daily_limit"] == 50
    assert p1["is_limit_reached"] is False
    assert p1["enabled"] is True

    item_id = await create_health_checkin_item(client, auth_headers, "步行打卡")
    await do_health_checkin(client, auth_headers, item_id)

    resp2 = await client.get(
        "/api/points/checkin/today-progress", headers=auth_headers
    )
    assert resp2.status_code == 200
    p2 = resp2.json()
    assert p2["earned_today"] == 5


# ── TC-007 ──


@pytest.mark.asyncio
async def test_tc007_points_records_contain_checkin(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-007: 积分明细中包含打卡积分记录"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    item_id = await create_health_checkin_item(client, auth_headers, "拉伸打卡")
    await do_health_checkin(client, auth_headers, item_id)

    resp = await client.get("/api/points/records", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    checkin_records = [r for r in data["items"] if r["type"] == "checkin"]
    assert len(checkin_records) >= 1
    assert "打卡" in checkin_records[0]["description"]


# ── TC-008 ──


@pytest.mark.asyncio
async def test_tc008_medication_checkin_earns_points(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-008: 用药提醒打卡送积分"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    reminder_id = await create_medication_reminder(client, auth_headers, "布洛芬")

    resp = await client.post(
        f"/api/health-plan/medications/{reminder_id}/checkin",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["points_earned"] > 0


# ── TC-009 ──


@pytest.mark.asyncio
async def test_tc009_plan_task_checkin_earns_points(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-009: 健康计划任务打卡送积分"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    plan_id, task_id = await create_user_plan_with_task(client, auth_headers)

    resp = await client.post(
        f"/api/health-plan/user-plans/{plan_id}/tasks/{task_id}/checkin",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["points_earned"] > 0


# ── TC-010 ──


@pytest.mark.asyncio
async def test_tc010_quick_checkin_earns_points(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """TC-010: 快速打卡送积分"""
    await set_checkin_rules(
        client, admin_headers, enabled="true", per_action="5", daily_limit="50"
    )

    item_id = await create_health_checkin_item(client, auth_headers, "快速打卡项")

    resp = await client.post(
        f"/api/health-plan/today-todos/{item_id}/check",
        headers=auth_headers,
        json={"type": "checkin", "value": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "points_earned" in data
    assert data["points_earned"] > 0
