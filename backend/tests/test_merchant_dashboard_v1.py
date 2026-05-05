"""
[门店预约看板与改期能力升级 v1.0] 看板接口与时段切片单元测试

覆盖：
1. SLOT_HOURS 配置正确性（9 段，每段 2h，从 06:00 开始）
2. slot_label 标签生成
3. appointment_to_slot 时段归属（边界 + 凌晨段）
4. slot_window 起止时间窗
5. /api/merchant/dashboard/time-slots 接口公开返回
"""
import pytest
from datetime import datetime, date

from app.api.merchant_dashboard import (
    SLOT_HOURS,
    appointment_to_slot,
    slot_label,
    slot_window,
)


# ───────── SLOT_HOURS 配置 ─────────

def test_slot_hours_count_is_9():
    assert len(SLOT_HOURS) == 9


def test_slot_hours_each_two_hours():
    for start, end in SLOT_HOURS:
        assert end - start == 2


def test_slot_hours_start_at_6_end_at_24():
    assert SLOT_HOURS[0][0] == 6
    assert SLOT_HOURS[-1][1] == 24


def test_slot_hours_continuous():
    for i in range(len(SLOT_HOURS) - 1):
        assert SLOT_HOURS[i][1] == SLOT_HOURS[i + 1][0]


# ───────── slot_label ─────────

def test_slot_label_first():
    assert slot_label(1) == "06:00-08:00"


def test_slot_label_last_uses_24():
    assert slot_label(9) == "22:00-24:00"


def test_slot_label_invalid_returns_empty():
    assert slot_label(0) == ""
    assert slot_label(10) == ""


# ───────── appointment_to_slot ─────────

def test_appt_slot_morning():
    dt = datetime(2026, 5, 5, 7, 30)  # 07:30 → slot 1
    assert appointment_to_slot(dt) == 1


def test_appt_slot_boundary_inclusive_start():
    dt = datetime(2026, 5, 5, 8, 0)  # 08:00 → slot 2 (含起点)
    assert appointment_to_slot(dt) == 2


def test_appt_slot_boundary_exclusive_end():
    dt = datetime(2026, 5, 5, 9, 59)  # 09:59 → slot 2
    assert appointment_to_slot(dt) == 2


def test_appt_slot_late_night():
    dt = datetime(2026, 5, 5, 22, 30)  # 22:30 → slot 9
    assert appointment_to_slot(dt) == 9


def test_appt_slot_dawn_returns_none():
    dt = datetime(2026, 5, 5, 3, 0)  # 凌晨 → None
    assert appointment_to_slot(dt) is None


def test_appt_slot_none_input():
    assert appointment_to_slot(None) is None


# ───────── slot_window ─────────

def test_slot_window_first():
    s, e = slot_window(date(2026, 5, 5), 1)
    assert s == datetime(2026, 5, 5, 6, 0)
    assert e == datetime(2026, 5, 5, 8, 0)


def test_slot_window_last_crosses_midnight():
    s, e = slot_window(date(2026, 5, 5), 9)
    assert s == datetime(2026, 5, 5, 22, 0)
    # slot 9 = 22:00-24:00 → 24:00 = 次日 00:00
    assert e == datetime(2026, 5, 6, 0, 0)


# ───────── time-slots 公开接口 ─────────

@pytest.mark.asyncio
async def test_time_slots_endpoint(client):
    resp = await client.get("/api/merchant/dashboard/time-slots")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["slots"]) == 9
    assert data["slots"][0] == {
        "slot_no": 1,
        "label": "06:00-08:00",
        "start_hour": 6,
        "end_hour": 8,
    }
    assert data["slots"][-1]["label"] == "22:00-24:00"


# ───────── 看板接口需鉴权 ─────────

@pytest.mark.asyncio
async def test_dashboard_day_requires_auth(client):
    resp = await client.get("/api/merchant/dashboard/day?date=2026-05-05")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_week_requires_auth(client):
    resp = await client.get("/api/merchant/dashboard/week?date=2026-05-05")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_month_requires_auth(client):
    resp = await client.get("/api/merchant/dashboard/month?year=2026&month=5")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_slot_requires_auth(client):
    resp = await client.get("/api/merchant/dashboard/slot/2026-05-05/3")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_month_day_requires_auth(client):
    resp = await client.get("/api/merchant/dashboard/month-day?date=2026-05-05")
    assert resp.status_code in (401, 403)
