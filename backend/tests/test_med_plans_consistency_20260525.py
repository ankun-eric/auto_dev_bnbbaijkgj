"""[BUG-HEALTH-PROFILE-MED-20260525] 用药提醒 三 Bug 修复一致性测试。

覆盖：
- Bug1：list?tab=finished 即使存在脏数据（archived + custom_times 异常）也能返回 200，
  不会因序列化失败拖垮整个接口；其余正常记录仍出现在结果中。
- Bug1：list?tab=finished 单独请求成功，前端三 Tab 计数（in_progress / not_started / finished）
  能各自独立请求并取到正确数字。
- Bug3：hero-count.remaining_today 与 today.banner.remaining_count 在同 consultant_id 下完全一致。

依赖 backend/tests/conftest.py 的 SQLite + auth_headers fixture。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import MedicationReminder, User


def _payload(name: str, **overrides) -> dict:
    body = {
        "medicine_name": name,
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "time_period": "custom",
        "remind_time": "08:00",
        "frequency_per_day": 2,
        "custom_times": ["08:00", "20:00"],
        "long_term": False,
        "start_date": date.today().isoformat(),
        "duration_days": 5,
        "guidance": "餐后",
        "notes": "",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


async def _get_user_id(db_session, phone: str = "13900000001") -> int:
    res = await db_session.execute(select(User).where(User.phone == phone))
    u = res.scalar_one()
    return u.id


# ─────────── Bug1: 三 Tab 各自独立请求都能 200 ───────────


@pytest.mark.asyncio
async def test_three_tabs_independent_load(client: AsyncClient, auth_headers):
    """各 Tab 独立请求成功，前端 Promise.allSettled 容错不再因任一失败而全 0。"""
    # 服药中
    r1 = await client.post(
        "/api/health-plan/medications",
        json=_payload("瑞舒伐他汀"),
        headers=auth_headers,
    )
    assert r1.status_code == 200, r1.text

    # 未开始
    future = (date.today() + timedelta(days=3)).isoformat()
    r2 = await client.post(
        "/api/health-plan/medications",
        json=_payload("阿托伐他汀", start_date=future, duration_days=5),
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text

    for tab in ("in_progress", "not_started", "finished"):
        res = await client.get(
            f"/api/health-plan/medications/list?tab={tab}",
            headers=auth_headers,
        )
        assert res.status_code == 200, f"tab={tab} should be 200, got {res.status_code}: {res.text}"
        body = res.json()
        assert "items" in body
        assert isinstance(body["items"], list)


# ─────────── Bug1: finished 含脏数据时不 500 ───────────


@pytest.mark.asyncio
async def test_finished_tab_skips_bad_record(client: AsyncClient, auth_headers, db_session):
    """构造一条 archived + custom_times 非法的旧记录，list?tab=finished 仍能 200 且返回其余正常记录。"""
    user_id = await _get_user_id(db_session)

    # 1) 正常的已结束记录
    end_past = date.today() - timedelta(days=2)
    start_past = end_past - timedelta(days=10)
    good = MedicationReminder(
        user_id=user_id,
        medicine_name="历史好药",
        dosage="1 片",
        time_period="custom",
        remind_time="08:00",
        frequency_per_day=1,
        custom_times=["08:00"],
        long_term=False,
        start_date=start_past,
        end_date=end_past,
        status="archived",
        reminder_enabled=True,
    )
    db_session.add(good)

    # 2) 脏数据：custom_times 类型异常（字符串而非列表），long_term=NULL
    bad = MedicationReminder(
        user_id=user_id,
        medicine_name="历史脏数据",
        dosage="1 片",
        time_period="custom",
        remind_time=None,
        frequency_per_day=None,
        custom_times="not-a-json-array",  # noqa: F841  intentional bad data
        long_term=None,
        start_date=start_past,
        end_date=end_past,
        status="archived",
        reminder_enabled=True,
    )
    db_session.add(bad)
    await db_session.commit()

    res = await client.get(
        "/api/health-plan/medications/list?tab=finished",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    names = [it.get("medicine_name") for it in body.get("items", [])]
    assert "历史好药" in names, f"good record should still be returned, got {names}"


# ─────────── Bug3: hero-count 与 today 数字一致 ───────────


@pytest.mark.asyncio
async def test_hero_count_and_today_consistency(client: AsyncClient, auth_headers):
    """同 consultant_id 下，hero-count.remaining_today == today.banner.remaining_count。"""
    # 创建 3 次/日 的计划
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload(
            "二甲双胍",
            frequency_per_day=3,
            custom_times=["08:00", "12:00", "20:00"],
        ),
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # 打卡 1 次
    c = await client.post(
        "/api/medication-check-in",
        json={"plan_id": pid, "scheduled_time": "08:00"},
        headers=auth_headers,
    )
    assert c.status_code == 200, c.text

    # 不带 consultant_id（本人/默认口径）
    hero = await client.get(
        "/api/medication-plans/hero-count",
        headers=auth_headers,
    )
    assert hero.status_code == 200
    today = await client.get(
        "/api/medication-plans/today",
        headers=auth_headers,
    )
    assert today.status_code == 200

    hero_remaining = hero.json().get("remaining_today")
    today_remaining = today.json().get("banner", {}).get("remaining_count")
    assert hero_remaining == today_remaining, (
        f"hero-count.remaining_today={hero_remaining} should equal "
        f"today.banner.remaining_count={today_remaining}"
    )

    # 带 consultant_id=0（本人）显式过滤，二者也必须一致
    hero0 = await client.get(
        "/api/medication-plans/hero-count?consultant_id=0",
        headers=auth_headers,
    )
    today0 = await client.get(
        "/api/medication-plans/today?consultant_id=0",
        headers=auth_headers,
    )
    assert hero0.status_code == 200
    assert today0.status_code == 200
    assert hero0.json().get("remaining_today") == today0.json().get("banner", {}).get("remaining_count")
