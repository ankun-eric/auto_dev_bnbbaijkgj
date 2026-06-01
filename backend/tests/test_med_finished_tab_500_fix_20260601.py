"""[BUG-MED-FINISHED-500-20260601] 用药计划列表「已结束」Tab 500 修复 — 回归测试。

根因：`/api/health-plan/medications/list?tab=finished` 的查询使用了
`end_date.desc().nullslast()`，SQLAlchemy 在 MySQL 方言下会生成
`... DESC NULLS LAST`，而 MySQL **不支持 NULLS LAST 语法**，导致 1064 语法错误
→ 接口返回 500，前端弹「该列数据异常，请联系客服」。

修复：改用 `end_date IS NULL` 作为前置排序键模拟 NULLS LAST（MySQL/SQLite 均兼容）。

本测试覆盖：
 1. finished Tab 在「混合 NULL/非 NULL end_date」数据下不报错且正常返回；
 2. 排序正确：end_date 非空者按降序在前，end_date 为空（如长期 archived）排在最后；
 3. 三个 Tab（in_progress / not_started / finished）均能正常返回，无 500；
 4. finished 无数据时返回空列表（前端展示「暂无用药计划」）。

注：CI 单测使用内存 SQLite；该用例在服务器 MySQL 环境（remote-deploy-and-test 阶段）
执行时可直接捕获 NULLS LAST 语法回归。
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
        "frequency_per_day": 1,
        "custom_times": ["08:00"],
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
    return res.scalar_one().id


# ─────────── 1) finished Tab 在混合 NULL/非 NULL end_date 下不 500 且排序正确 ───────────


@pytest.mark.asyncio
async def test_finished_tab_mixed_null_end_date_no_500_and_sorted(
    client: AsyncClient, auth_headers, db_session
):
    today = date.today()
    user_id = await _get_user_id(db_session)

    # 构造 3 条已结束（archived）记录：
    #  A: end_date = today-1（最近结束）
    #  B: end_date = today-10（较早结束）
    #  C: end_date = NULL（长期药被归档，无结束日）
    a = MedicationReminder(
        user_id=user_id, medicine_name="近结束A", dosage="1 片", time_period="custom",
        remind_time="08:00", frequency_per_day=1, custom_times=["08:00"],
        start_date=today - timedelta(days=20), end_date=today - timedelta(days=1),
        long_term=False, status="archived", reminder_enabled=False,
    )
    b = MedicationReminder(
        user_id=user_id, medicine_name="早结束B", dosage="1 片", time_period="custom",
        remind_time="08:00", frequency_per_day=1, custom_times=["08:00"],
        start_date=today - timedelta(days=30), end_date=today - timedelta(days=10),
        long_term=False, status="archived", reminder_enabled=False,
    )
    c = MedicationReminder(
        user_id=user_id, medicine_name="无结束日C", dosage="1 片", time_period="custom",
        remind_time="08:00", frequency_per_day=1, custom_times=["08:00"],
        start_date=today - timedelta(days=40), end_date=None,
        long_term=False, status="archived", reminder_enabled=False,
    )
    db_session.add_all([a, b, c])
    await db_session.commit()

    res = await client.get(
        "/api/health-plan/medications/list?tab=finished", headers=auth_headers
    )
    # 核心断言：不再 500
    assert res.status_code == 200, res.text

    names = [it["medicine_name"] for it in res.json()["items"]]
    assert set(names) == {"近结束A", "早结束B", "无结束日C"}

    # 排序断言：非空 end_date 降序在前（近结束A 在 早结束B 之前），NULL（无结束日C）排在最后
    assert names.index("近结束A") < names.index("早结束B")
    assert names.index("早结束B") < names.index("无结束日C")
    assert names[-1] == "无结束日C"


# ─────────── 2) 三个 Tab 均不 500 ───────────


@pytest.mark.asyncio
async def test_all_three_tabs_no_500(client: AsyncClient, auth_headers, db_session):
    today = date.today()
    # in_progress
    await client.post("/api/health-plan/medications", json=_payload("进行中药"), headers=auth_headers)
    # not_started
    await client.post(
        "/api/health-plan/medications",
        json=_payload("未开始药", start_date=(today + timedelta(days=3)).isoformat(), duration_days=5),
        headers=auth_headers,
    )
    # finished（archived）
    fin = await client.post(
        "/api/health-plan/medications",
        json=_payload("已结束药", start_date=(today - timedelta(days=10)).isoformat(), duration_days=3),
        headers=auth_headers,
    )
    fin_r = (
        await db_session.execute(
            select(MedicationReminder).where(MedicationReminder.id == fin.json()["id"])
        )
    ).scalar_one()
    fin_r.status = "archived"
    await db_session.commit()

    for tab in ("in_progress", "not_started", "finished"):
        r = await client.get(
            f"/api/health-plan/medications/list?tab={tab}", headers=auth_headers
        )
        assert r.status_code == 200, f"tab={tab} -> {r.status_code}: {r.text}"
        assert isinstance(r.json()["items"], list)


# ─────────── 3) finished 无数据返回空列表 ───────────


@pytest.mark.asyncio
async def test_finished_tab_empty_returns_empty_list(client: AsyncClient, auth_headers):
    # 仅创建一条进行中药，finished 应为空
    await client.post("/api/health-plan/medications", json=_payload("仅进行中"), headers=auth_headers)
    res = await client.get(
        "/api/health-plan/medications/list?tab=finished", headers=auth_headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["items"] == []


# ─────────── 4) finished 含 active 且 end_date<today 的非长期记录也纳入 ───────────


@pytest.mark.asyncio
async def test_finished_tab_includes_expired_active_non_long_term(
    client: AsyncClient, auth_headers, db_session
):
    today = date.today()
    user_id = await _get_user_id(db_session)
    # active 但 end_date 已过、非长期 → 属于「已结束」
    r = MedicationReminder(
        user_id=user_id, medicine_name="过期未归档", dosage="1 片", time_period="custom",
        remind_time="08:00", frequency_per_day=1, custom_times=["08:00"],
        start_date=today - timedelta(days=10), end_date=today - timedelta(days=2),
        long_term=False, status="active", reminder_enabled=True,
    )
    db_session.add(r)
    await db_session.commit()

    res = await client.get(
        "/api/health-plan/medications/list?tab=finished", headers=auth_headers
    )
    assert res.status_code == 200, res.text
    names = [it["medicine_name"] for it in res.json()["items"]]
    assert "过期未归档" in names
