"""[PRD-MED-PLAN-OPTIM-V1 2026-05-17] 用药计划页面优化 — 非UI自动化测试。

覆盖 8 个新增验收点：
 1. long_term=True 时 end_date 强制为 null
 2. 普通计划：start_date + end_date 正确存储
 3. 服用时机老枚举写入时自动迁移到新枚举（早上→饭前等）
 4. 服用时机老枚举读取时兜底返回新枚举
 5. 更新计划：long_term 切换为 True 时 end_date 清空
 6. 更新计划：long_term 切换为 False 时 end_date 重新计算
 7. 列表接口返回的 long_term/start_date/end_date 完整
 8. guidance=None 时不报错
"""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import MedicationReminder


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
        "duration_days": 30,
        "guidance": "饭后",
        "notes": "",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_long_term_clears_end_date(client: AsyncClient, auth_headers):
    """1. long_term=True 时 end_date 强制为 null。"""
    payload = _payload("二甲双胍", long_term=True, end_date=None, duration_days=None)
    r = await client.post("/api/health-plan/medications", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["long_term"] is True
    assert body["end_date"] is None


@pytest.mark.asyncio
async def test_normal_cycle_stores_dates(client: AsyncClient, auth_headers):
    """2. 普通计划：start_date + end_date 正确存储。"""
    payload = _payload(
        "阿司匹林",
        long_term=False,
        start_date="2026-05-17",
        end_date="2026-06-15",
        duration_days=30,
    )
    r = await client.post("/api/health-plan/medications", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["long_term"] is False
    assert body["start_date"] == "2026-05-17"
    assert body["end_date"] == "2026-06-15"


@pytest.mark.asyncio
async def test_legacy_timing_migrate_on_write(client: AsyncClient, auth_headers, db_session):
    """3. 服用时机老枚举写入时自动迁移到新枚举。"""
    cases = [
        ("早上", "饭前"),
        ("中午", "饭后"),
        ("下午", "饭后"),
        ("晚上", "饭后"),
        ("睡前", "睡前"),
        ("morning", "饭前"),
        ("evening", "饭后"),
        ("bedtime", "睡前"),
    ]
    for idx, (legacy, expected) in enumerate(cases):
        payload = _payload(f"药品测试{idx}", guidance=legacy)
        r = await client.post("/api/health-plan/medications", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        res = await db_session.execute(
            select(MedicationReminder).where(MedicationReminder.id == rid)
        )
        rem = res.scalar_one()
        assert rem.guidance == expected, f"{legacy} → {rem.guidance} ≠ {expected}"


@pytest.mark.asyncio
async def test_legacy_timing_fallback_on_read(client: AsyncClient, auth_headers, db_session):
    """4. 数据库中老枚举存在时，读取接口自动兜底返回新枚举。"""
    # 直接在 DB 写入老枚举
    res = await client.post(
        "/api/health-plan/medications", json=_payload("兜底药"), headers=auth_headers
    )
    rid = res.json()["id"]
    rem = (await db_session.execute(
        select(MedicationReminder).where(MedicationReminder.id == rid)
    )).scalar_one()
    rem.guidance = "晚上"
    await db_session.flush()
    await db_session.commit()

    # 详情接口
    r = await client.get(f"/api/health-plan/medications/{rid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["guidance"] == "饭后"

    # 列表接口
    r2 = await client.get("/api/health-plan/medications/list?tab=in_progress", headers=auth_headers)
    assert r2.status_code == 200
    items = r2.json().get("items", [])
    found = [it for it in items if it["id"] == rid]
    assert found and found[0]["guidance"] == "饭后"


@pytest.mark.asyncio
async def test_update_to_long_term_clears_end_date(client: AsyncClient, auth_headers):
    """5. 更新：从普通切换为长期时 end_date 被清空。"""
    create = await client.post(
        "/api/health-plan/medications",
        json=_payload("替米沙坦", long_term=False, end_date="2026-06-15"),
        headers=auth_headers,
    )
    rid = create.json()["id"]
    r = await client.put(
        f"/api/health-plan/medications/{rid}",
        json={"long_term": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["long_term"] is True
    assert body["end_date"] is None


@pytest.mark.asyncio
async def test_update_to_finite_recomputes_end_date(client: AsyncClient, auth_headers):
    """6. 更新：从长期切换为非长期时，结合 duration 计算 end_date。"""
    create = await client.post(
        "/api/health-plan/medications",
        json=_payload("氨氯地平", long_term=True),
        headers=auth_headers,
    )
    rid = create.json()["id"]
    r = await client.put(
        f"/api/health-plan/medications/{rid}",
        json={"long_term": False, "start_date": "2026-05-17", "duration_days": 14},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["long_term"] is False
    # 2026-05-17 + 14 - 1 = 2026-05-30
    assert body["end_date"] == "2026-05-30"


@pytest.mark.asyncio
async def test_list_returns_long_term_and_dates(client: AsyncClient, auth_headers):
    """7. 列表接口正确返回 long_term/start_date/end_date。"""
    await client.post(
        "/api/health-plan/medications",
        json=_payload("非诺贝特", long_term=True),
        headers=auth_headers,
    )
    r = await client.get("/api/health-plan/medications/list?tab=in_progress", headers=auth_headers)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert any(it["medicine_name"] == "非诺贝特" and it["long_term"] is True and it["end_date"] is None for it in items)


@pytest.mark.asyncio
async def test_guidance_none_does_not_crash(client: AsyncClient, auth_headers):
    """8. guidance=None 时各接口不报错。"""
    payload = _payload("无指导药", guidance=None)
    payload.pop("guidance", None)
    r = await client.post("/api/health-plan/medications", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("guidance") in (None, "")
