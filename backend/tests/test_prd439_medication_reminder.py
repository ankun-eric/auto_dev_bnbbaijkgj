"""[PRD-439] 用药提醒 API 测试。

覆盖 9 个端点：
- GET /plans / POST /plans / PUT /plans/{id} / DELETE /plans/{id}
- GET /today / POST /check / POST /uncheck
- GET /badge / GET /appointments

含：成功路径 / 401 未认证 / 422 参数校验 / 边界（空列表、跨用户、重复打卡、撤销）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


PREFIX = "/api/medication-reminder"


# ──────────────── 401 未认证 ────────────────


@pytest.mark.asyncio
async def test_plans_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/plans")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_today_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/today")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_check_requires_auth(client: AsyncClient):
    r = await client.post(f"{PREFIX}/check", json={"plan_id": 1, "scheduled_time": "08:00"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_badge_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/badge")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_appointments_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/appointments")
    assert r.status_code in (401, 403)


# ──────────────── 边界：空列表 ────────────────


@pytest.mark.asyncio
async def test_plans_empty_list(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/plans", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_today_empty(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/today", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_badge_zero(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["medication_unchecked"] == 0
    assert body["appointment_pending"] == 0
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_appointments_empty(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/appointments", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


# ──────────────── 创建/编辑/删除 ────────────────


@pytest.mark.asyncio
async def test_create_plan_then_list(client: AsyncClient, auth_headers):
    payload = {
        "drug_name": "阿司匹林",
        "dosage": "1片",
        "schedule": ["08:00", "14:00", "20:00"],
        "note": "饭后服用",
        "enabled": True,
    }
    r = await client.post(f"{PREFIX}/plans", headers=auth_headers, json=payload)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["drug_name"] == "阿司匹林"
    assert plan["schedule"] == ["08:00", "14:00", "20:00"]
    assert plan["enabled"] is True
    pid = plan["id"]

    r2 = await client.get(f"{PREFIX}/plans", headers=auth_headers)
    assert r2.status_code == 200
    plans = r2.json()
    assert len(plans) == 1
    assert plans[0]["id"] == pid


@pytest.mark.asyncio
async def test_create_plan_invalid_schedule(client: AsyncClient, auth_headers):
    # 422：schedule 类型错（应为列表，给字符串）
    r = await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "X", "dosage": "1片", "schedule": "25:00"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_plan_invalid_time_value(client: AsyncClient, auth_headers):
    # 400：schedule 时间值越界（25:00）
    r = await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "X", "dosage": "1片", "schedule": ["25:00"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_plan_missing_fields(client: AsyncClient, auth_headers):
    # 422：缺少 dosage
    r = await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "X", "schedule": ["08:00"]},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_plan(client: AsyncClient, auth_headers):
    payload = {"drug_name": "A", "dosage": "1片", "schedule": ["08:00"]}
    r = await client.post(f"{PREFIX}/plans", headers=auth_headers, json=payload)
    pid = r.json()["id"]

    r2 = await client.put(
        f"{PREFIX}/plans/{pid}",
        headers=auth_headers,
        json={"drug_name": "B", "enabled": False},
    )
    assert r2.status_code == 200
    assert r2.json()["drug_name"] == "B"
    assert r2.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_plan(client: AsyncClient, auth_headers):
    payload = {"drug_name": "A", "dosage": "1片", "schedule": ["08:00"]}
    pid = (await client.post(f"{PREFIX}/plans", headers=auth_headers, json=payload)).json()["id"]
    r = await client.delete(f"{PREFIX}/plans/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    plans = (await client.get(f"{PREFIX}/plans", headers=auth_headers)).json()
    assert plans == []


@pytest.mark.asyncio
async def test_update_plan_not_found(client: AsyncClient, auth_headers):
    r = await client.put(
        f"{PREFIX}/plans/99999", headers=auth_headers, json={"drug_name": "X"}
    )
    assert r.status_code == 404


# ──────────────── 今日/打卡/撤销 ────────────────


@pytest.mark.asyncio
async def test_today_after_create(client: AsyncClient, auth_headers):
    payload = {"drug_name": "A", "dosage": "1片", "schedule": ["08:00", "20:00"]}
    pid = (await client.post(f"{PREFIX}/plans", headers=auth_headers, json=payload)).json()["id"]

    r = await client.get(f"{PREFIX}/today", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert all(it["plan_id"] == pid for it in items)
    assert {it["scheduled_time"] for it in items} == {"08:00", "20:00"}
    assert all(it["checked"] is False for it in items)


@pytest.mark.asyncio
async def test_check_then_today_marks_checked(client: AsyncClient, auth_headers):
    payload = {"drug_name": "A", "dosage": "1片", "schedule": ["08:00", "20:00"]}
    pid = (await client.post(f"{PREFIX}/plans", headers=auth_headers, json=payload)).json()["id"]

    r = await client.post(
        f"{PREFIX}/check",
        headers=auth_headers,
        json={"plan_id": pid, "scheduled_time": "08:00"},
    )
    assert r.status_code == 200
    log_id = r.json()["log_id"]
    assert log_id > 0

    today = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    by_t = {it["scheduled_time"]: it for it in today}
    assert by_t["08:00"]["checked"] is True
    assert by_t["08:00"]["log_id"] == log_id
    assert by_t["20:00"]["checked"] is False


@pytest.mark.asyncio
async def test_check_duplicate_returns_same_log(client: AsyncClient, auth_headers):
    pid = (await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A", "dosage": "1片", "schedule": ["08:00"]},
    )).json()["id"]

    r1 = await client.post(
        f"{PREFIX}/check", headers=auth_headers, json={"plan_id": pid, "scheduled_time": "08:00"}
    )
    r2 = await client.post(
        f"{PREFIX}/check", headers=auth_headers, json={"plan_id": pid, "scheduled_time": "08:00"}
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["log_id"] == r2.json()["log_id"]


@pytest.mark.asyncio
async def test_check_invalid_scheduled_time(client: AsyncClient, auth_headers):
    pid = (await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A", "dosage": "1片", "schedule": ["08:00"]},
    )).json()["id"]
    r = await client.post(
        f"{PREFIX}/check",
        headers=auth_headers,
        json={"plan_id": pid, "scheduled_time": "23:00"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_uncheck_revokes_log(client: AsyncClient, auth_headers):
    pid = (await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A", "dosage": "1片", "schedule": ["08:00"]},
    )).json()["id"]
    log_id = (await client.post(
        f"{PREFIX}/check", headers=auth_headers, json={"plan_id": pid, "scheduled_time": "08:00"}
    )).json()["log_id"]

    r = await client.post(f"{PREFIX}/uncheck", headers=auth_headers, json={"log_id": log_id})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    today = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    assert today[0]["checked"] is False


# ──────────────── 跨用户隔离 ────────────────


@pytest.mark.asyncio
async def test_cross_user_isolation(client: AsyncClient, auth_headers):
    # 用户 A：创建一条
    pid_a = (await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A药", "dosage": "1片", "schedule": ["08:00"]},
    )).json()["id"]

    # 用户 B：登录 + 拉计划列表，应该是空（不能看到 A 的）
    await client.post("/api/auth/register", json={
        "phone": "13900000099", "password": "passb", "nickname": "B"
    })
    tok_b = (await client.post("/api/auth/login", json={
        "phone": "13900000099", "password": "passb"
    })).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {tok_b}", "Client-Type": "h5-user"}

    r = await client.get(f"{PREFIX}/plans", headers=headers_b)
    assert r.status_code == 200
    assert r.json() == []

    # B 试图编辑 A 的计划：404
    r2 = await client.put(
        f"{PREFIX}/plans/{pid_a}", headers=headers_b, json={"drug_name": "黑客"}
    )
    assert r2.status_code == 404

    # B 试图删除 A 的计划：404
    r3 = await client.delete(f"{PREFIX}/plans/{pid_a}", headers=headers_b)
    assert r3.status_code == 404


# ──────────────── badge 综合 ────────────────


@pytest.mark.asyncio
async def test_badge_counts_unchecked_only(client: AsyncClient, auth_headers):
    pid = (await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A", "dosage": "1片", "schedule": ["08:00", "14:00", "20:00"]},
    )).json()["id"]

    r = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    assert r.json()["medication_unchecked"] == 3

    await client.post(
        f"{PREFIX}/check", headers=auth_headers, json={"plan_id": pid, "scheduled_time": "08:00"}
    )
    r2 = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    assert r2.json()["medication_unchecked"] == 2
    assert r2.json()["total"] == 2
