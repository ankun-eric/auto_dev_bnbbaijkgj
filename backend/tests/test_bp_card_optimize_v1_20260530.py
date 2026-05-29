"""[PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 血压卡片优化 — 后端字段透传测试

PRD 文档要求详情页的趋势图聚合（min/max/avg）以及点击数据点弹窗
需要 records 中的以下字段：
- value.systolic / value.diastolic
- value.period（测量时段：晨起 / 上午 / 下午 / 睡前 等）
- source（手工录入 / 设备）
- measured_at

本套测试验证后端 GET /api/health-profile-v3/{pid}/metric/blood_pressure
返回的 records 全量保留这些字段，供前端聚合与展示。
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


@pytest_asyncio.fixture
async def user_auth(client: AsyncClient, auth_headers):
    from sqlalchemy import select

    from app.models.models import User
    from .conftest import test_session

    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one()
        return {"user_id": user.id, "headers": auth_headers}


@pytest_asyncio.fixture
async def bp_profile(user_auth):
    from app.models.models import FamilyMember, HealthProfile

    from .conftest import test_session

    user_id = user_auth["user_id"]
    async with test_session() as session:
        fm = FamilyMember(
            user_id=user_id, relationship_type="本人", nickname="测试本人",
            is_self=True, gender="male", status="active",
        )
        session.add(fm)
        await session.flush()
        hp = HealthProfile(
            user_id=user_id, family_member_id=fm.id, name="测试本人", gender="male",
        )
        session.add(hp)
        await session.commit()
        return {"profile_id": hp.id, "user_id": user_id}


_RID_COUNTER = {"next": 50000}


async def _insert_bp_record(profile_id: int, sbp: int, dbp: int, *,
                            days_ago: int = 0, hour: int = 8, minute: int = 30,
                            period: str = "晨起", source: str = "manual",
                            user_id: int = 1):
    """直接插入一条血压记录（避开 BigInteger PK 自增问题）。"""
    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    measured_at = datetime.now() - timedelta(days=days_ago)
    measured_at = measured_at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, 'blood_pressure', :vj, :src, :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id,
            "vj": _json.dumps({"systolic": sbp, "diastolic": dbp, "period": period}),
            "src": source, "ma": measured_at, "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()
    return rid


# ─── TC-1：records 保留 period 字段（前端弹窗需要） ──────────────────────────

@pytest.mark.asyncio
async def test_bp_records_carry_period_field(client: AsyncClient, user_auth, bp_profile):
    """[PRD §5.5] 数据点弹窗需要"测量时段"字段，验证 period 透传完整。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _insert_bp_record(pid, 142, 92, period="晨起", user_id=uid)
    await _insert_bp_record(pid, 125, 80, period="睡前", user_id=uid, hour=22)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    periods = sorted([r["value"].get("period") for r in data["records"]])
    assert periods == ["晨起", "睡前"]


# ─── TC-2：records 保留 source 字段（手工录入 / 设备） ────────────────────────

@pytest.mark.asyncio
async def test_bp_records_carry_source_field(client: AsyncClient, user_auth, bp_profile):
    """[PRD §3.3 / §5.5] 来源字段需透传：手工录入 / 设备名"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _insert_bp_record(pid, 130, 85, source="manual", user_id=uid, hour=8)
    await _insert_bp_record(pid, 142, 92, source="omron", user_id=uid, hour=10)
    await _insert_bp_record(pid, 120, 80, source="device:bp_meter", user_id=uid, hour=12)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    sources = sorted([r["source"] for r in data["records"]])
    assert sources == ["device:bp_meter", "manual", "omron"]


# ─── TC-3：同一天多条记录全部保留（前端聚合 min/max/avg 需要） ──────────────

@pytest.mark.asyncio
async def test_bp_same_day_multiple_records_fully_preserved(client: AsyncClient, user_auth, bp_profile):
    """[PRD §5.3.2] 一日多测：前端需要 min/max（范围带）+ avg（平均值连线）；
    后端必须返回当天所有原始记录。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    samples = [(140, 90, 7, 0), (130, 85, 12, 0), (150, 95, 18, 0), (135, 88, 22, 0)]
    for sbp, dbp, hour, minute in samples:
        await _insert_bp_record(pid, sbp, dbp, hour=hour, minute=minute, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure?size=100",
        headers=user_auth["headers"],
    )
    data = resp.json()
    assert data["total"] == 4

    # 后端均值仍按当日聚合
    assert data["trend_systolic"][6] == round(sum(s[0] for s in samples) / 4, 2)
    assert data["trend_diastolic"][6] == round(sum(s[1] for s in samples) / 4, 2)

    # records 必须包含全部 4 条原始数据，含时间戳供前端聚合 min/max
    sbps = sorted([r["value"]["systolic"] for r in data["records"]])
    assert sbps == sorted([s[0] for s in samples])
    # 时间戳必须保留（前端按时间散点）
    assert all("measured_at" in r for r in data["records"])


# ─── TC-4：日视图所需字段完整 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bp_records_support_day_view(client: AsyncClient, user_auth, bp_profile):
    """[PRD §5.4] 日视图：当日所有测量点按时间散点。
    要求：records 含 measured_at（精确到时分）+ systolic/diastolic + source + period。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _insert_bp_record(pid, 140, 90, hour=7, minute=15, period="晨起", user_id=uid)
    await _insert_bp_record(pid, 125, 82, hour=14, minute=30, period="下午", user_id=uid)
    await _insert_bp_record(pid, 130, 85, hour=21, minute=45, period="睡前", user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    data = resp.json()
    assert data["total"] == 3
    for r in data["records"]:
        assert r["value"].get("systolic") is not None
        assert r["value"].get("diastolic") is not None
        assert r["value"].get("period") in ("晨起", "下午", "睡前")
        assert "measured_at" in r
        # measured_at 必须包含时分（即 ISO 字符串非空且至少含 'T'）
        assert "T" in r["measured_at"] or " " in r["measured_at"]


# ─── TC-5：今日小卡片所需字段（首页 today-metrics）──────────────────────────

@pytest.mark.asyncio
async def test_today_metrics_blood_pressure_carries_source_and_time(client: AsyncClient, user_auth, bp_profile):
    """[PRD §3.1] 首页小卡片需要：sbp / dbp / 严重性档位（前端判定）/ 时间 / 来源"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _insert_bp_record(pid, 142, 92, source="omron", period="晨起", user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/today-metrics",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    bp = data["blood_pressure"]
    assert bp["value"]["systolic"] == 142
    assert bp["value"]["diastolic"] == 92
    assert bp["source"] == "omron"
    assert bp["measured_at"]  # 非空
    # 异常标记沿用既有规则
    assert bp["is_abnormal"] is True
