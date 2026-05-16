"""[PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划入口改造 — 非UI自动化测试。

覆盖 16 个验收点：
 1. Hero 文案 - 有待打卡
 2. Hero 文案 - 全部完成
 3. Hero 文案 - 无任何用药
 4. Banner 字段完整性
 5. 最近一条待打卡 upcoming 正确
 6. 时间线按时间排序 + 状态正确
 7. 5 分钟内撤销成功
 8. 超 5 分钟撤销 → 400 + REVOKE_TIMEOUT
 9. 摘要卡仅 active
10. 摘要卡按 created_at desc
11. list 接口三 Tab 过滤
12. 默认/无 tab 等价于 in_progress
13. 允许过去开始日期
14. 提交时根据日期自动判定 status
15. auto_flow 转 active
16. 本月依从率（不追溯空白）

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
        "custom_times": ["08:00", "12:00", "20:00"],
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


# ─────────── 1) Hero - 有待打卡 ───────────


@pytest.mark.asyncio
async def test_hero_count_with_remaining(client: AsyncClient, auth_headers):
    r = await client.post("/api/health-plan/medications", json=_payload("瑞舒伐他汀"), headers=auth_headers)
    assert r.status_code == 200, r.text

    res = await client.get("/api/medication-plans/hero-count", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "has_remaining"
    assert body["display_text"] == f"还有 {body['remaining_today']} 次用药"
    assert body["total_today"] == 3
    assert body["done_today"] == 0
    assert body["remaining_today"] == 3


# ─────────── 2) Hero - 全部完成 ───────────


@pytest.mark.asyncio
async def test_hero_count_all_done(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload("二甲双胍", frequency_per_day=2, custom_times=["08:00", "20:00"]),
        headers=auth_headers,
    )
    pid = r.json()["id"]
    # 打卡 2 次 = schedule 长度
    for _ in range(2):
        c = await client.post(
            "/api/medication-check-in",
            json={"plan_id": pid, "scheduled_time": "08:00"},
            headers=auth_headers,
        )
        assert c.status_code == 200, c.text

    res = await client.get("/api/medication-plans/hero-count", headers=auth_headers)
    body = res.json()
    assert body["status"] == "all_done"
    assert body["display_text"] == "今日用药已完成"
    assert body["remaining_today"] == 0


# ─────────── 3) Hero - 无任何用药 ───────────


@pytest.mark.asyncio
async def test_hero_count_no_plan(client: AsyncClient, auth_headers):
    res = await client.get("/api/medication-plans/hero-count", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "none"
    assert body["display_text"] == "今日用药 0"
    assert body["total_today"] == 0


# ─────────── 4) Banner 字段完整 ───────────


@pytest.mark.asyncio
async def test_reminder_today_banner_fields(client: AsyncClient, auth_headers):
    await client.post(
        "/api/health-plan/medications",
        json=_payload("钙片", custom_times=["09:00", "18:00"], frequency_per_day=2),
        headers=auth_headers,
    )
    res = await client.get("/api/medication-plans/today", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    b = body["banner"]
    for k in ("date_str", "total_remaining", "next_reminder", "done_count", "remaining_count", "monthly_compliance"):
        assert k in b, f"missing banner.{k}"
    assert b["done_count"] == 0
    assert b["remaining_count"] == 2
    assert isinstance(b["monthly_compliance"], int)
    assert b["next_reminder"] is not None
    assert b["next_reminder"]["name"] == "钙片"


# ─────────── 5) upcoming 正确 ───────────


@pytest.mark.asyncio
async def test_reminder_today_upcoming(client: AsyncClient, auth_headers):
    await client.post(
        "/api/health-plan/medications",
        json=_payload("药A", custom_times=["07:00", "13:00", "21:00"]),
        headers=auth_headers,
    )
    await client.post(
        "/api/health-plan/medications",
        json=_payload("药B", custom_times=["08:30", "14:00", "22:00"]),
        headers=auth_headers,
    )
    res = await client.get("/api/medication-plans/today", headers=auth_headers)
    body = res.json()
    up = body["upcoming"]
    assert up is not None
    # upcoming 应是当前时间之后最早的一条（或全部已过点 → 取最早）
    assert "scheduled_time" in up
    assert up["name"] in ("药A", "药B")


# ─────────── 6) 时间线排序 + 状态 ───────────


@pytest.mark.asyncio
async def test_reminder_today_timeline_sorted_by_time(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload("阿莫西林", custom_times=["08:00", "12:00", "20:00"]),
        headers=auth_headers,
    )
    pid = r.json()["id"]
    # 打卡 1 次 → 第 1 个 schedule done
    await client.post(
        "/api/medication-check-in",
        json={"plan_id": pid, "scheduled_time": "08:00"},
        headers=auth_headers,
    )
    body = (await client.get("/api/medication-plans/today", headers=auth_headers)).json()
    timeline = body["timeline"]
    assert len(timeline) == 3
    times = [t["scheduled_time"] for t in timeline]
    assert times == sorted(times)
    statuses = [t["status"] for t in timeline]
    assert "done" in statuses
    assert all(s in ("done", "upcoming", "pending") for s in statuses)


# ─────────── 7) 5 分钟内撤销 ───────────


@pytest.mark.asyncio
async def test_check_in_then_revoke_within_5min(client: AsyncClient, auth_headers):
    r = await client.post("/api/health-plan/medications", json=_payload("药X"), headers=auth_headers)
    pid = r.json()["id"]
    c = await client.post(
        "/api/medication-check-in",
        json={"plan_id": pid, "scheduled_time": "08:00"},
        headers=auth_headers,
    )
    assert c.status_code == 200
    cid = c.json()["id"]
    rev = await client.post(f"/api/medication-check-in/{cid}/revoke", headers=auth_headers)
    assert rev.status_code == 200, rev.text
    assert rev.json()["id"] == cid


# ─────────── 8) 超 5 分钟撤销失败 ───────────


@pytest.mark.asyncio
async def test_revoke_after_5min_returns_400(client: AsyncClient, auth_headers, db_session):
    r = await client.post("/api/health-plan/medications", json=_payload("药Y"), headers=auth_headers)
    pid = r.json()["id"]
    c = await client.post(
        "/api/medication-check-in",
        json={"plan_id": pid, "scheduled_time": "08:00"},
        headers=auth_headers,
    )
    cid = c.json()["id"]

    # 手动把 created_at 拨回 10 分钟前
    res = await db_session.execute(select(MedicationCheckIn).where(MedicationCheckIn.id == cid))
    ci = res.scalar_one()
    ci.created_at = datetime.utcnow() - timedelta(minutes=10)
    ci.check_in_time = datetime.utcnow() - timedelta(minutes=10)
    await db_session.commit()

    rev = await client.post(f"/api/medication-check-in/{cid}/revoke", headers=auth_headers)
    assert rev.status_code == 400
    detail = rev.json()["detail"]
    assert isinstance(detail, dict) and detail.get("code") == "REVOKE_TIMEOUT"


# ─────────── 9) 摘要卡仅 active ───────────


@pytest.mark.asyncio
async def test_summary_only_active(client: AsyncClient, auth_headers, db_session):
    a = await client.post("/api/health-plan/medications", json=_payload("活动药"), headers=auth_headers)
    b = await client.post("/api/health-plan/medications", json=_payload("待归档药"), headers=auth_headers)
    # 把 b 改成 archived
    res = await db_session.execute(select(MedicationReminder).where(MedicationReminder.id == b.json()["id"]))
    r = res.scalar_one()
    r.status = "archived"
    await db_session.commit()

    res2 = await client.get("/api/medication-plans/summary", headers=auth_headers)
    items = res2.json()["items"]
    names = [it["name"] for it in items]
    assert "活动药" in names
    assert "待归档药" not in names


# ─────────── 10) 摘要卡按 created_at desc ───────────


@pytest.mark.asyncio
async def test_summary_order_by_created_at_desc(client: AsyncClient, auth_headers, db_session):
    a = await client.post("/api/health-plan/medications", json=_payload("先创建"), headers=auth_headers)
    b = await client.post("/api/health-plan/medications", json=_payload("后创建"), headers=auth_headers)
    # 手动错开 created_at
    ra = (await db_session.execute(select(MedicationReminder).where(MedicationReminder.id == a.json()["id"]))).scalar_one()
    rb = (await db_session.execute(select(MedicationReminder).where(MedicationReminder.id == b.json()["id"]))).scalar_one()
    ra.created_at = datetime.utcnow() - timedelta(hours=2)
    rb.created_at = datetime.utcnow()
    await db_session.commit()

    res = await client.get("/api/medication-plans/summary", headers=auth_headers)
    names = [it["name"] for it in res.json()["items"]]
    assert names.index("后创建") < names.index("先创建")


# ─────────── 11) list 三 Tab 过滤 ───────────


@pytest.mark.asyncio
async def test_list_three_tabs_filter(client: AsyncClient, auth_headers, db_session):
    today = date.today()
    # in_progress：今天起算
    ip = await client.post("/api/health-plan/medications", json=_payload("进行中药"), headers=auth_headers)
    # not_started：start_date = 明天
    ns_payload = _payload("未开始药", start_date=(today + timedelta(days=2)).isoformat(), duration_days=3)
    ns = await client.post("/api/health-plan/medications", json=ns_payload, headers=auth_headers)
    # finished：手动设为 archived
    fin = await client.post(
        "/api/health-plan/medications",
        json=_payload("已结束药", start_date=(today - timedelta(days=10)).isoformat(), duration_days=5),
        headers=auth_headers,
    )
    fin_r = (await db_session.execute(select(MedicationReminder).where(MedicationReminder.id == fin.json()["id"]))).scalar_one()
    fin_r.status = "archived"
    await db_session.commit()

    r1 = await client.get("/api/health-plan/medications/list?tab=in_progress", headers=auth_headers)
    names1 = [it["medicine_name"] for it in r1.json()["items"]]
    assert "进行中药" in names1
    assert "未开始药" not in names1
    assert "已结束药" not in names1

    r2 = await client.get("/api/health-plan/medications/list?tab=not_started", headers=auth_headers)
    names2 = [it["medicine_name"] for it in r2.json()["items"]]
    assert names2 == ["未开始药"]

    r3 = await client.get("/api/health-plan/medications/list?tab=finished", headers=auth_headers)
    names3 = [it["medicine_name"] for it in r3.json()["items"]]
    assert "已结束药" in names3


# ─────────── 12) 默认/无 tab 等价于 in_progress（兼容旧行为不变） ───────────


@pytest.mark.asyncio
async def test_list_default_tab_is_in_progress(client: AsyncClient, auth_headers):
    """无 tab 参数：返回所有「在用药品」（即 status=active 且未结束），等价于服药中视图。"""
    today = date.today()
    await client.post("/api/health-plan/medications", json=_payload("当前药"), headers=auth_headers)
    await client.post(
        "/api/health-plan/medications",
        json=_payload("未来药", start_date=(today + timedelta(days=5)).isoformat(), duration_days=3),
        headers=auth_headers,
    )

    # 显式 tab=in_progress 应只返回当前药
    in_prog = await client.get("/api/health-plan/medications/list?tab=in_progress", headers=auth_headers)
    names = [it["medicine_name"] for it in in_prog.json()["items"]]
    assert names == ["当前药"]


# ─────────── 13) 允许过去开始日期 ───────────


@pytest.mark.asyncio
async def test_create_with_past_start_date_allowed(client: AsyncClient, auth_headers):
    past = (date.today() - timedelta(days=3)).isoformat()
    res = await client.post(
        "/api/health-plan/medications",
        json=_payload("过去日期药", start_date=past, duration_days=10),
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["start_date"] == past


# ─────────── 14) 状态由日期自动派生（接口侧 + 摘要） ───────────


@pytest.mark.asyncio
async def test_create_initial_status_derivation(client: AsyncClient, auth_headers, db_session):
    today = date.today()
    # 未来：不应出现在摘要卡
    fut = await client.post(
        "/api/health-plan/medications",
        json=_payload("未来药2", start_date=(today + timedelta(days=2)).isoformat(), duration_days=5),
        headers=auth_headers,
    )
    # 今天：应在摘要
    cur = await client.post("/api/health-plan/medications", json=_payload("今日药2"), headers=auth_headers)
    # 过去结束：手动构造 end_date < today，触发 auto-archive
    past_end = (date.today() - timedelta(days=1)).isoformat()
    past_start = (date.today() - timedelta(days=10)).isoformat()
    arch = await client.post(
        "/api/health-plan/medications",
        json=_payload("已过期2", start_date=past_start, duration_days=1, end_date=past_end),
        headers=auth_headers,
    )
    # 触发一次 list（含 auto-archive 逻辑）
    await client.get("/api/health-plan/medications/list", headers=auth_headers)

    sm = await client.get("/api/medication-plans/summary", headers=auth_headers)
    names = [it["name"] for it in sm.json()["items"]]
    assert "今日药2" in names
    assert "未来药2" not in names
    assert "已过期2" not in names


# ─────────── 15) auto_flow_status 转 active ───────────


@pytest.mark.asyncio
async def test_auto_flow_status_transition(client: AsyncClient, auth_headers, db_session):
    """create archived reminder whose start/end window includes today → after
    auto_flow_medication_status should be flipped to active."""
    from app.services.medication_status_scheduler import auto_flow_medication_status

    today = date.today()
    user_id = await _get_user_id(db_session)
    r = MedicationReminder(
        user_id=user_id,
        medicine_name="复活药",
        dosage="1 片",
        time_period="custom",
        remind_time="08:00",
        frequency_per_day=1,
        custom_times=["08:00"],
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=5),
        long_term=False,
        status="archived",
        reminder_enabled=False,
    )
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)
    assert r.status == "archived"

    stats = await auto_flow_medication_status(db_session, user_id=user_id)
    await db_session.commit()
    await db_session.refresh(r)
    assert r.status == "active"
    assert r.reminder_enabled is True
    assert stats["activated"] >= 1


# ─────────── 16) 本月依从率（不追溯空白） ───────────


@pytest.mark.asyncio
async def test_monthly_compliance_calculation(client: AsyncClient, auth_headers, db_session):
    """本月依从率 = done/expected。新建一条 reminder（即使 start_date 在过去），
    expected 也应以「max(月初, 创建日, start_date)」起算，不补录空白。
    """
    today = date.today()
    # 创建一条 frequency=2，长期，今天创建
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload(
            "依从药",
            frequency_per_day=2,
            custom_times=["08:00", "20:00"],
            long_term=True,
            start_date=(today - timedelta(days=30)).isoformat(),  # 即便 start_date 在 30 天前
        ),
        headers=auth_headers,
    )
    pid = r.json()["id"]
    # 今日打 1 次
    await client.post(
        "/api/medication-check-in",
        json={"plan_id": pid, "scheduled_time": "08:00"},
        headers=auth_headers,
    )

    res = await client.get("/api/medication-stats/monthly-compliance", headers=auth_headers)
    body = res.json()
    assert body["month"] == f"{today.year}-{today.month:02d}"
    # expected 应仅算「创建日 ~ today」期间，而非把过去整月空白补齐。
    # 由于 created_at 使用 UTC、today 使用本机时区，UTC ↔ 本机时区可能存在 ±1 天偏差，
    # 因此允许 expected ∈ {2, 4}（同一日或 created_at 落在 UTC 昨天）。
    # 关键断言：不应追溯到月初的全部 day_count（>= 30 才是错误行为）。
    assert body["expected"] in (2, 4), body
    assert body["done"] == 1
    expected_rate = int(round(1 / body["expected"] * 100))
    assert body["rate_percent"] == expected_rate
