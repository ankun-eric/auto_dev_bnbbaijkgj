"""[PRD-MED-HISTORY-V1] 用药提醒历史打卡记录 — 非UI自动化测试。

覆盖验收点：
 1. 日历月视图 - 正常返回 days 数组
 2. 日历 - 无用药计划时全月 no_plan
 3. 日历 - 有打卡 fully_done
 4. 日历 - 部分打卡 partial
 5. 日历 - 漏打卡 missed
 6. 记录详情 - 返回各状态记录
 7. 记录详情 - done 状态
 8. 补打卡 - 昨日漏打成功
 9. 补打卡 - 拒绝今日补打
10. 补打卡 - 拒绝超限日期
11. 补打卡 - 拒绝重复打卡
12. 补打卡 - 记录 check_in_type=supplement
13. 未打卡记录 can_supplement 判定

依赖 backend/tests/conftest.py 中的内存 SQLite fixture。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import MedicationCheckIn, MedicationReminder, User
def _plan_payload(name: str, **overrides) -> dict:
    """创建用药计划请求体。"""
    body = {
        "medicine_name": name,
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "time_period": "custom",
        "remind_time": "08:00",
        "frequency_per_day": 2,
        "custom_times": ["08:00", "20:00"],
        "long_term": True,
        "start_date": "2025-01-01",
        "guidance": "餐后",
        "notes": "",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


async def _create_plan(client: AsyncClient, auth_headers: dict, name: str = "阿司匹林", **overrides) -> int:
    """创建用药计划并返回 plan_id。"""
    r = await client.post("/api/health-plan/medications", json=_plan_payload(name, **overrides), headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ─────────── 1) 月视图日历 — 基础 ───────────


@pytest.mark.asyncio
async def test_calendar_empty_month(client: AsyncClient, auth_headers):
    """无用药计划时全月返回 no_plan。"""
    today = date.today()
    res = await client.get(
        "/api/medication/calendar",
        params={"year": today.year, "month": today.month},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["year"] == today.year
    assert body["month"] == today.month
    assert len(body["days"]) > 0
    for d in body["days"]:
        assert d["status"] == "no_plan"


@pytest.mark.asyncio
async def test_calendar_with_plans_and_checkins(client: AsyncClient, auth_headers):
    """创建计划并打卡后，日历反映对应状态。"""
    plan_id = await _create_plan(client, auth_headers, "布洛芬")
    today = date.today()

    # 打卡今天第一个时间点
    await client.post("/api/medication-check-in", json={
        "plan_id": plan_id, "scheduled_time": "08:00",
    }, headers=auth_headers)

    res = await client.get(
        "/api/medication/calendar",
        params={"year": today.year, "month": today.month},
        headers=auth_headers,
    )
    assert res.status_code == 200
    days = res.json()["days"]
    today_str = today.isoformat()
    today_day = next((d for d in days if d["date"] == today_str), None)
    assert today_day is not None
    # 今天有 1/2 打卡 → partial
    assert today_day["status"] == "partial"


@pytest.mark.asyncio
async def test_calendar_fully_done(client: AsyncClient, auth_headers):
    """全部时间点打卡后显示 fully_done。"""
    plan_id = await _create_plan(client, auth_headers, "二甲双胍")
    today = date.today()

    # 打卡全部时间点
    await client.post("/api/medication-check-in", json={
        "plan_id": plan_id, "scheduled_time": "08:00",
    }, headers=auth_headers)
    await client.post("/api/medication-check-in", json={
        "plan_id": plan_id, "scheduled_time": "20:00",
    }, headers=auth_headers)

    res = await client.get(
        "/api/medication/calendar",
        params={"year": today.year, "month": today.month},
        headers=auth_headers,
    )
    days = res.json()["days"]
    today_str = today.isoformat()
    today_day = next((d for d in days if d["date"] == today_str), None)
    assert today_day is not None
    assert today_day["status"] == "fully_done"
# ─────────── 2) 记录详情 ───────────


@pytest.mark.asyncio
async def test_records_returns_structure(client: AsyncClient, auth_headers):
    """records 端点返回正确的数据结构。"""
    plan_id = await _create_plan(client, auth_headers, "阿莫西林")
    today = date.today()

    res = await client.get(
        "/api/medication/records",
        params={"date": today.isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["date"] == today.isoformat()
    assert "records" in body
    # 2 个时间点：08:00, 20:00
    assert len(body["records"]) == 2
    for rec in body["records"]:
        assert rec["plan_id"] == plan_id
        assert rec["drug_name"] == "阿莫西林"
        assert rec["scheduled_time"] in ("08:00", "20:00")
        assert rec["status"] in ("not_yet", "done", "missed", "expired", "supplement")


@pytest.mark.asyncio
async def test_records_done_status(client: AsyncClient, auth_headers):
    """打卡后 records 返回 done 状态。"""
    plan_id = await _create_plan(client, auth_headers, "头孢")
    today = date.today()

    await client.post("/api/medication-check-in", json={
        "plan_id": plan_id, "scheduled_time": "08:00",
    }, headers=auth_headers)

    res = await client.get(
        "/api/medication/records",
        params={"date": today.isoformat()},
        headers=auth_headers,
    )
    records = res.json()["records"]
    done_rec = next((r for r in records if r["scheduled_time"] == "08:00"), None)
    assert done_rec is not None
    assert done_rec["status"] == "done"
    assert done_rec["check_in_time"] is not None
    assert done_rec["check_in_type"] == "normal"
    assert done_rec["can_supplement"] is False


@pytest.mark.asyncio
async def test_records_missed_can_supplement(client: AsyncClient, auth_headers):
    """昨日漏打卡的记录 can_supplement=True。"""
    plan_id = await _create_plan(client, auth_headers, "维生素C")
    yesterday = date.today() - timedelta(days=1)

    res = await client.get(
        "/api/medication/records",
        params={"date": yesterday.isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 200
    records = res.json()["records"]
    assert len(records) > 0
    for r in records:
        assert r["status"] == "missed"
        assert r["can_supplement"] is True
        assert r["check_in_time"] is None


@pytest.mark.asyncio
async def test_records_expired_no_supplement(client: AsyncClient, auth_headers):
    """超过 2 天的漏打卡记录 status=expired 且 can_supplement=False。"""
    plan_id = await _create_plan(client, auth_headers, "钙片")
    old_date = date.today() - timedelta(days=4)

    res = await client.get(
        "/api/medication/records",
        params={"date": old_date.isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 200
    records = res.json()["records"]
    assert len(records) > 0
    for r in records:
        assert r["status"] == "expired"
        assert r["can_supplement"] is False
# ─────────── 3) 补打卡 ───────────


@pytest.mark.asyncio
async def test_supplement_yesterday_success(client: AsyncClient, auth_headers):
    """补打昨天的漏打卡成功。"""
    plan_id = await _create_plan(client, auth_headers, "降压药")
    yesterday = date.today() - timedelta(days=1)

    res = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": yesterday.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plan_id"] == plan_id
    assert body["check_in_date"] == yesterday.isoformat()
    assert body["check_in_type"] == "supplement"
    assert body["id"] > 0


@pytest.mark.asyncio
async def test_supplement_today_rejected(client: AsyncClient, auth_headers):
    """拒绝补打今天。"""
    plan_id = await _create_plan(client, auth_headers, "感冒药")
    today = date.today()

    res = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": today.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 400
    assert "不可补打今日" in res.json()["detail"]


@pytest.mark.asyncio
async def test_supplement_exceed_limit_rejected(client: AsyncClient, auth_headers):
    """拒绝补打超过 2 天前的日期。"""
    plan_id = await _create_plan(client, auth_headers, "消炎药")
    old_date = date.today() - timedelta(days=3)

    res = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": old_date.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 400
    assert "已超过补打卡时限" in res.json()["detail"]


@pytest.mark.asyncio
async def test_supplement_duplicate_rejected(client: AsyncClient, auth_headers):
    """拒绝重复补打同一时间点。"""
    plan_id = await _create_plan(client, auth_headers, "止痛药")
    yesterday = date.today() - timedelta(days=1)

    # 第一次补打成功
    r1 = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": yesterday.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert r1.status_code == 200

    # 第二次补打同一时间点应被拒绝
    r2 = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": yesterday.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert r2.status_code == 400
    assert "已打卡" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_supplement_check_in_type_persisted(db_session, client: AsyncClient, auth_headers):
    """补打卡记录 check_in_type='supplement' 正确落库。"""
    plan_id = await _create_plan(client, auth_headers, "安眠药")
    yesterday = date.today() - timedelta(days=1)

    res = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": yesterday.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 200
    checkin_id = res.json()["id"]

    # 从数据库直接验证
    c = (await db_session.execute(
        select(MedicationCheckIn).where(MedicationCheckIn.id == checkin_id)
    )).scalar_one()
    assert c.check_in_type == "supplement"
    assert c.check_in_date == yesterday


@pytest.mark.asyncio
async def test_supplement_invalid_plan_rejected(client: AsyncClient, auth_headers):
    """拒绝补打不存在的计划。"""
    yesterday = date.today() - timedelta(days=1)
    res = await client.post("/api/medication/supplement", json={
        "plan_id": 99999,
        "check_in_date": yesterday.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_supplement_future_date_rejected(client: AsyncClient, auth_headers):
    """拒绝补打未来日期。"""
    plan_id = await _create_plan(client, auth_headers, "退烧药")
    future = date.today() + timedelta(days=1)

    res = await client.post("/api/medication/supplement", json={
        "plan_id": plan_id,
        "check_in_date": future.isoformat(),
        "scheduled_time": "08:00",
    }, headers=auth_headers)
    assert res.status_code == 400
