"""[BUG-HEALTH-ARCHIVE-V2 2026-05-16] 健康档案 5 Bug 修复非UI自动化测试

覆盖：
- B1 + B2：用药数据源统一到 MedicationReminder
  - GET /api/health-plan/medications/list 返回扁平列表（兼容 MedicationPlan schema）
  - GET /api/health-plan/medications/summary 返回「在用药品」计数
  - 「在用药品」口径：status='active' AND (long_term=True OR end_date IS NULL OR end_date >= TODAY)
  - end_date < TODAY 且非长期 → 不计入
  - long_term=True → 计入（即使 end_date 是过去）
  - GET /api/health-profile-v3/{pid}/medication-plan 切到 MedicationReminder
- B1：GET /api/prd469/summary/{pid} 第 4 格 label 改为「在用药品」
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ───────────────────────────── 辅助 fixture ─────────────────────────────


@pytest_asyncio.fixture
async def user_auth(client: AsyncClient, auth_headers):
    """注册并返回用户的 user_id + auth_headers。"""
    from sqlalchemy import select

    from app.models.models import User
    from .conftest import test_session

    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one()
        user_id = user.id

    return {"user_id": user_id, "headers": auth_headers}


@pytest_asyncio.fixture
async def user_profile(client: AsyncClient, user_auth):
    """为用户创建 HealthProfile，返回 profile_id。"""
    from app.models.models import FamilyMember, HealthProfile
    from .conftest import test_session

    user_id = user_auth["user_id"]
    async with test_session() as session:
        # 先创建本人 family member
        fm = FamilyMember(
            user_id=user_id,
            relationship_type="本人",
            nickname="测试本人",
            is_self=True,
            gender="male",  # 故意用英文，测试 B3 前端展示映射（前端测试在 H5）
            status="active",
        )
        session.add(fm)
        await session.flush()

        hp = HealthProfile(
            user_id=user_id,
            family_member_id=fm.id,
            name="测试本人",
            gender="male",
        )
        session.add(hp)
        await session.commit()
        return {"profile_id": hp.id, "member_id": fm.id, "user_id": user_id}


def _create_med_payload(
    name: str,
    *,
    long_term: bool = True,
    end_date: str | None = None,
    custom_times: list[str] | None = None,
) -> dict:
    return {
        "medicine_name": name,
        "dosage": "1片",
        "time_period": "custom",
        "remind_time": (custom_times or ["08:00"])[0],
        "notes": "测试",
        "frequency_per_day": len(custom_times or ["08:00"]),
        "custom_times": custom_times or ["08:00"],
        "long_term": long_term,
        "end_date": end_date,
        "reminder_enabled": True,
    }


# ───────────────────────────── B1 / B2 核心测试 ─────────────────────────────


@pytest.mark.asyncio
async def test_b1_b2_medications_list_returns_active_meds(client: AsyncClient, user_auth):
    """新增用药后 /api/health-plan/medications/list 应包含该药。"""
    headers = user_auth["headers"]
    # 新增一条长期用药
    res = await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("阿司匹林"),
        headers=headers,
    )
    assert res.status_code == 200, res.text
    new_id = res.json()["id"]

    # 列表应包含该条
    list_res = await client.get("/api/health-plan/medications/list", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert "items" in data and "total" in data
    ids = [it["id"] for it in data["items"]]
    assert new_id in ids
    # 字段兼容性检查（前端依赖）
    item = next(it for it in data["items"] if it["id"] == new_id)
    assert item["drug_name"] == "阿司匹林"
    assert isinstance(item["schedule"], list) and len(item["schedule"]) >= 1
    assert item["enabled"] is True
    assert item["long_term"] is True


@pytest.mark.asyncio
async def test_b1_b2_summary_count_matches_list_count(client: AsyncClient, user_auth):
    """「在用药品」摘要计数 = 列表条数（保持 Hero ↔ 列表一致）。"""
    headers = user_auth["headers"]
    # 新增 2 条长期用药
    for n in ["药A", "药B"]:
        r = await client.post(
            "/api/health-plan/medications",
            json=_create_med_payload(n),
            headers=headers,
        )
        assert r.status_code == 200

    list_res = await client.get("/api/health-plan/medications/list", headers=headers)
    summary_res = await client.get("/api/health-plan/medications/summary", headers=headers)
    assert list_res.status_code == 200 and summary_res.status_code == 200
    assert summary_res.json()["active_count"] == list_res.json()["total"] == 2
    assert summary_res.json()["label"] == "在用药品"


@pytest.mark.asyncio
async def test_b1_b2_expired_med_excluded(client: AsyncClient, user_auth):
    """end_date < TODAY 且非长期的药不计入「在用药品」。"""
    headers = user_auth["headers"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("已停服药", long_term=False, end_date=yesterday),
        headers=headers,
    )
    assert r.status_code == 200

    list_res = await client.get("/api/health-plan/medications/list", headers=headers)
    summary_res = await client.get("/api/health-plan/medications/summary", headers=headers)
    assert list_res.json()["total"] == 0
    assert summary_res.json()["active_count"] == 0


@pytest.mark.asyncio
async def test_b1_b2_future_end_date_included(client: AsyncClient, user_auth):
    """end_date >= TODAY 的非长期药也计入「在用药品」。"""
    headers = user_auth["headers"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("短期药", long_term=False, end_date=tomorrow),
        headers=headers,
    )
    assert r.status_code == 200

    list_res = await client.get("/api/health-plan/medications/list", headers=headers)
    summary_res = await client.get("/api/health-plan/medications/summary", headers=headers)
    assert list_res.json()["total"] == 1
    assert summary_res.json()["active_count"] == 1


@pytest.mark.asyncio
async def test_b1_b2_long_term_overrides_end_date(client: AsyncClient, user_auth):
    """long_term=True 时即使 end_date 过期也算「在用药品」。"""
    headers = user_auth["headers"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("长期药", long_term=True, end_date=yesterday),
        headers=headers,
    )
    assert r.status_code == 200

    summary_res = await client.get("/api/health-plan/medications/summary", headers=headers)
    assert summary_res.json()["active_count"] == 1


@pytest.mark.asyncio
async def test_b2_today_segment_filter(client: AsyncClient, user_auth):
    """segment=today 仅返回今日命中的用药（schedule 非空 → 每日都需服用）。"""
    headers = user_auth["headers"]
    await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("每日药", custom_times=["08:00", "20:00"]),
        headers=headers,
    )
    res_today = await client.get(
        "/api/health-plan/medications/list?segment=today", headers=headers
    )
    res_all = await client.get(
        "/api/health-plan/medications/list?segment=all", headers=headers
    )
    assert res_today.status_code == 200 and res_all.status_code == 200
    assert res_today.json()["total"] == 1
    assert res_all.json()["total"] == 1


@pytest.mark.asyncio
async def test_b1_health_profile_v3_medication_plan_uses_reminder(
    client: AsyncClient, user_auth, user_profile
):
    """/api/health-profile-v3/{pid}/medication-plan 切到 MedicationReminder 数据源。"""
    headers = user_auth["headers"]
    profile_id = user_profile["profile_id"]
    # 创建一条长期用药（写入 MedicationReminder）
    r = await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("健康档案用药", custom_times=["09:00", "21:00"]),
        headers=headers,
    )
    assert r.status_code == 200

    res = await client.get(
        f"/api/health-profile-v3/{profile_id}/medication-plan", headers=headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    items = data["items"]
    assert len(items) == 1
    item = items[0]
    assert item["drug_name"] == "健康档案用药"
    assert item["schedule"] == ["09:00", "21:00"]
    assert len(item["time_chips"]) == 2


@pytest.mark.asyncio
async def test_b1_prd469_summary_label_in_use(client: AsyncClient, user_auth, user_profile):
    """/api/prd469/summary/{pid} 第 4 格 label 应为「在用药品」并使用统一口径计数。"""
    headers = user_auth["headers"]
    profile_id = user_profile["profile_id"]
    # 新增 1 条长期用药 + 1 条已过期非长期药（后者不应被计入）
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("长期药2"),
        headers=headers,
    )
    await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("已停药", long_term=False, end_date=yesterday),
        headers=headers,
    )

    res = await client.get(f"/api/prd469/summary/{profile_id}", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    metrics = body.get("hero_metrics") or []
    assert len(metrics) == 4
    fourth = metrics[3]
    assert fourth["label"] == "在用药品"
    assert fourth["count"] == 1  # 仅长期药计入
    assert fourth["unit"] == "种"


@pytest.mark.asyncio
async def test_b1_summary_stats_active_med_count(client: AsyncClient, user_auth, user_profile):
    """/api/prd469/summary-stats/{pid} 返回 active_med_count 字段（与 hero_metrics 一致口径）。"""
    headers = user_auth["headers"]
    profile_id = user_profile["profile_id"]
    await client.post(
        "/api/health-plan/medications",
        json=_create_med_payload("药A"),
        headers=headers,
    )
    res = await client.get(f"/api/prd469/summary-stats/{profile_id}", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "active_med_count" in body
    assert body["active_med_count"] == 1
    # 兼容字段
    assert body["long_term_med_count"] == 1


@pytest.mark.asyncio
async def test_endpoints_require_auth(client: AsyncClient):
    """新增的两个端点必须鉴权（未带 token → 401）。"""
    res1 = await client.get("/api/health-plan/medications/list")
    res2 = await client.get("/api/health-plan/medications/summary")
    assert res1.status_code == 401
    assert res2.status_code == 401
