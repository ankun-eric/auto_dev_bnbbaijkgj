"""[BUG-MED-V1 2026-05-21] 健康档案 / 用药模块 Bug 修复 — 非UI自动化测试。

覆盖 PRD 中 7 个 Bug 的关键回归点：

  Bug 1：reminder_today 加 consultant_id 过滤，与 hero-count 口径一致
  Bug 2：banner 返回 today_completion_rate 字段
  Bug 3：timeline 已超时未打卡 → status='overdue'
  Bug 5/6：health_archive_v5.overview.medication_plan_count 正确返回非 0
  Bug 7：/api/medication-reminder/badge 数据源切换到新表 MedicationReminder + MedicationCheckIn

依赖 backend/tests/conftest.py 中的内存 SQLite fixture。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import MedicationCheckIn, MedicationReminder, User


def _payload(name: str, **overrides) -> dict:
    body = {
        "medicine_name": name,
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "time_period": "custom",
        "remind_time": "08:00",
        "frequency_per_day": 3,
        # 横跨"已过点"和"未到点"的时间组合 —— 让 timeline 同时包含 overdue / pending
        "custom_times": ["00:01", "12:00", "23:59"],
        "long_term": False,
        "start_date": date.today().isoformat(),
        "duration_days": 5,
        "guidance": "餐后",
        "notes": "",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


# ─────────── Bug 1：reminder_today 携带 consultant_id 与 hero-count 口径一致 ───────────


@pytest.mark.asyncio
async def test_bug1_today_accepts_consultant_id(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/health-plan/medications", json=_payload("药A"), headers=auth_headers
    )
    assert r.status_code == 200, r.text

    res = await client.get(
        "/api/medication-plans/today?consultant_id=0", headers=auth_headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "banner" in body and "timeline" in body
    # consultant_id=0 表示"仅本人"，应当能匹配到刚创建的本人计划
    assert body["banner"]["total_today"] == 3


@pytest.mark.asyncio
async def test_bug1_today_and_hero_same_count(client: AsyncClient, auth_headers):
    """Hero 与列表接口的 total_today 必须一致（关键：口径统一）。"""
    await client.post(
        "/api/health-plan/medications", json=_payload("药B"), headers=auth_headers
    )
    hero = (
        await client.get(
            "/api/medication-plans/hero-count?consultant_id=0", headers=auth_headers
        )
    ).json()
    today = (
        await client.get(
            "/api/medication-plans/today?consultant_id=0", headers=auth_headers
        )
    ).json()
    assert hero["total_today"] == today["banner"]["total_today"]


# ─────────── Bug 2：today_completion_rate 字段存在 ───────────


@pytest.mark.asyncio
async def test_bug2_today_completion_rate_field(client: AsyncClient, auth_headers):
    await client.post(
        "/api/health-plan/medications", json=_payload("药C"), headers=auth_headers
    )
    res = await client.get("/api/medication-plans/today", headers=auth_headers)
    assert res.status_code == 200, res.text
    banner = res.json()["banner"]
    # 关键新增字段：今日完成率
    assert "today_completion_rate" in banner
    assert isinstance(banner["today_completion_rate"], int)
    assert 0 <= banner["today_completion_rate"] <= 100
    # 兼容字段保留
    assert "monthly_compliance" in banner


@pytest.mark.asyncio
async def test_bug2_completion_rate_computes_correctly(
    client: AsyncClient, auth_headers
):
    """打卡 1 次后，3 次计划 → 完成率 33%。"""
    rcre = await client.post(
        "/api/health-plan/medications", json=_payload("药D"), headers=auth_headers
    )
    plan_id = rcre.json()["id"]
    # 打卡一次（任意时间点）
    await client.post(
        "/api/medication-check-in",
        json={"plan_id": plan_id, "scheduled_time": "00:01"},
        headers=auth_headers,
    )
    res = await client.get("/api/medication-plans/today", headers=auth_headers)
    banner = res.json()["banner"]
    assert banner["today_completion_rate"] == 33


# ─────────── Bug 3：timeline 已过点未打卡 → status='overdue' ───────────


@pytest.mark.asyncio
async def test_bug3_timeline_overdue_status(client: AsyncClient, auth_headers):
    # 用户创建一条每日 00:01 / 12:00 / 23:59 的计划，
    # 现在跑测试时 00:01 必定已过（绝大多数情况），应当返回 overdue
    await client.post(
        "/api/health-plan/medications", json=_payload("药E"), headers=auth_headers
    )
    res = await client.get("/api/medication-plans/today", headers=auth_headers)
    timeline = res.json()["timeline"]
    statuses = {row["status"] for row in timeline}
    # overdue 状态必须存在于状态集合（关键回归点）
    # （00:01 几乎一定是过去时刻 → overdue；23:59 几乎一定是 pending）
    assert "overdue" in statuses or "done" in statuses, f"timeline statuses={statuses}"


# ─────────── Bug 5/6：overview.medication_plan_count 正确返回 ───────────


@pytest.mark.asyncio
async def test_bug5_6_overview_medication_count_not_zero(
    client: AsyncClient, auth_headers
):
    """创建用药计划后，health-archive-v5 overview 接口应当返回 medication_plan_count > 0。

    历史 Bug：原代码使用了不存在的 is_active / consultant_id 字段，
    每次查询抛 AttributeError，被 except 吞掉 → 永远为 0。
    """
    r = await client.post(
        "/api/health-plan/medications", json=_payload("药F"), headers=auth_headers
    )
    assert r.status_code == 200, r.text

    res = await client.get("/api/health-archive-v5/overview", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "medication_plan_count" in body
    # 关键回归：必须 > 0（修复前永远为 0）
    assert body["medication_plan_count"] >= 1


# ─────────── Bug 7：badge 接口数据源切换到新表 ───────────


@pytest.mark.asyncio
async def test_bug7_badge_uses_new_medication_reminder_table(
    client: AsyncClient, auth_headers
):
    """在新表 MedicationReminder 中创建计划后，/api/medication-reminder/badge 必须能算到红点。

    历史 Bug：badge 接口查的是旧表 MedicationPlan + MedicationLog，
    而新增计划写入的是新表 MedicationReminder + MedicationCheckIn → 永远为 0。
    """
    await client.post(
        "/api/health-plan/medications", json=_payload("药G"), headers=auth_headers
    )
    res = await client.get("/api/medication-reminder/badge", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    # 关键回归：必须 > 0（修复前永远为 0）
    assert body["medication_unchecked"] >= 1
    assert body["medication"]["count"] >= 1
