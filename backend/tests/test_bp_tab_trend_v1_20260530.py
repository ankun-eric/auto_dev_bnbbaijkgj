"""[BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 血压 Tab 页面优化 — 后端接口扩展测试

覆盖范围：
- GET /api/health-profile-v3/{pid}/metric/blood_pressure 新增字段：
  - trend_dates（YYYY-MM-DD，长度=7，最后一项为今天）
  - trend_day_labels（最后一项为「今日」）
  - trend_systolic / trend_diastolic（按日均值；无数据为 null）
- 非血压指标（heart_rate 等）trend_systolic / trend_diastolic 仍存在但全为空（向后兼容）
- 多条记录按日均值正确聚合
- 验收 DoD「6 组测试数据」前端档位判定虽在前端，但后端 records.value.systolic/diastolic 透传完整供前端判定，
  此处验证 records 返回字段无丢失
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def user_auth(client: AsyncClient, auth_headers):
    from sqlalchemy import select

    from app.models.models import User
    from .conftest import test_session

    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one()
        user_id = user.id

    return {"user_id": user_id, "headers": auth_headers}


@pytest_asyncio.fixture
async def bp_profile(client: AsyncClient, user_auth):
    """创建本人 family_member + health_profile，返回 profile_id。"""
    from app.models.models import FamilyMember, HealthProfile
    from .conftest import test_session

    user_id = user_auth["user_id"]
    async with test_session() as session:
        fm = FamilyMember(
            user_id=user_id,
            relationship_type="本人",
            nickname="测试本人",
            is_self=True,
            gender="male",
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


# 自增 ID 计数器（SQLite BigInteger PK 不自动递增，需显式指定）
_RID_COUNTER = {"next": 10000}


async def _post_bp(client: AsyncClient, headers, profile_id: int, sbp: int, dbp: int, *, days_ago: int = 0, user_id: int = 1):
    """直接 raw SQL 插入 HealthMetricRecord（SQLite BigInteger PK 不自动递增）。"""
    import json as _json

    from sqlalchemy import text

    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    measured_at = datetime.now() - timedelta(days=days_ago)
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, :mt, :vj, 'manual', :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id, "mt": "blood_pressure",
            "vj": _json.dumps({"systolic": sbp, "diastolic": dbp, "period": "晨起"}),
            "ma": measured_at, "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()


async def _post_hr(profile_id: int, value: int, *, user_id: int = 1):
    import json as _json

    from sqlalchemy import text

    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, 'heart_rate', :vj, 'manual', :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id,
            "vj": _json.dumps({"value": value, "activity": "静息"}),
            "ma": datetime.now(), "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()


# ─── TC-BP-1：BP 接口新字段存在且 dates/labels 对齐 ────────────────────────

@pytest.mark.asyncio
async def test_bp_history_returns_new_trend_fields(client: AsyncClient, user_auth, bp_profile):
    """空数据情况下，trend_dates / trend_day_labels / trend_systolic / trend_diastolic 均存在且长度=7。"""
    pid = bp_profile["profile_id"]
    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["metric_type"] == "blood_pressure"
    assert len(data["trend_7days"]) == 7
    assert len(data["trend_dates"]) == 7
    assert len(data["trend_day_labels"]) == 7
    assert len(data["trend_systolic"]) == 7
    assert len(data["trend_diastolic"]) == 7

    # 最后一项标签必须是「今日」
    assert data["trend_day_labels"][-1] == "今日"
    # 倒数第二项必须是「周X」
    assert data["trend_day_labels"][-2] in ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

    # 空数据时 sbp/dbp 全为 null
    assert all(v is None for v in data["trend_systolic"])
    assert all(v is None for v in data["trend_diastolic"])


# ─── TC-BP-2：多日数据正确聚合到 sbp/dbp ─────────────────────────────────

@pytest.mark.asyncio
async def test_bp_trend_aggregates_sbp_dbp_by_day(client: AsyncClient, user_auth, bp_profile):
    """录入 3 天数据，验证 trend_systolic / trend_diastolic 正确聚合。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    # 今天：142/92（轻度偏高）
    await _post_bp(client, user_auth["headers"], pid, 142, 92, days_ago=0, user_id=uid)
    # 昨天：120/80
    await _post_bp(client, user_auth["headers"], pid, 120, 80, days_ago=1, user_id=uid)
    # 3 天前：110/70（正常）
    await _post_bp(client, user_auth["headers"], pid, 110, 70, days_ago=3, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    sbp = data["trend_systolic"]
    dbp = data["trend_diastolic"]
    # 今天（最右）
    assert sbp[6] == 142.0
    assert dbp[6] == 92.0
    # 昨天
    assert sbp[5] == 120.0
    assert dbp[5] == 80.0
    # 3 天前（索引 3）
    assert sbp[3] == 110.0
    assert dbp[3] == 70.0
    # 2 天前 + 4~6 天前必须为空
    assert sbp[4] is None
    assert sbp[0] is None and sbp[1] is None and sbp[2] is None


# ─── TC-BP-3：同一天多条记录取均值 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_bp_trend_averages_multiple_records_same_day(client: AsyncClient, user_auth, bp_profile):
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _post_bp(client, user_auth["headers"], pid, 140, 90, days_ago=0, user_id=uid)
    await _post_bp(client, user_auth["headers"], pid, 120, 80, days_ago=0, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # 均值
    assert data["trend_systolic"][6] == 130.0
    assert data["trend_diastolic"][6] == 85.0


# ─── TC-BP-4：records 内的 sbp/dbp 字段完整（供前端判定档位） ──────────────

@pytest.mark.asyncio
async def test_bp_records_carry_full_value(client: AsyncClient, user_auth, bp_profile):
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _post_bp(client, user_auth["headers"], pid, 170, 110, days_ago=0, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure",
        headers=user_auth["headers"],
    )
    data = resp.json()
    assert data["total"] == 1
    rec = data["records"][0]
    assert rec["value"]["systolic"] == 170
    assert rec["value"]["diastolic"] == 110


# ─── TC-BP-5：非血压指标向后兼容（heart_rate） ────────────────────────────

@pytest.mark.asyncio
async def test_heart_rate_history_backward_compatible(client: AsyncClient, user_auth, bp_profile):
    """heart_rate 接口 trend_systolic/diastolic 必须为空数组或全 None，向后兼容。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    await _post_hr(pid, 72, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/heart_rate",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric_type"] == "heart_rate"
    # 老字段仍工作
    assert len(data["trend_7days"]) == 7
    assert data["trend_7days"][6] == 72.0
    # 新字段：blood_pressure 专属应为空/全 None
    assert data["trend_systolic"] == [] or all(v is None for v in data["trend_systolic"])
    assert data["trend_diastolic"] == [] or all(v is None for v in data["trend_diastolic"])
    # 通用新字段长度对齐
    assert len(data["trend_dates"]) == 7
    assert len(data["trend_day_labels"]) == 7


# ─── TC-BP-6：6 组验收数据 — records 完整保留供前端判定 ──────────────────

@pytest.mark.asyncio
async def test_bp_six_acceptance_groups_recorded(client: AsyncClient, user_auth, bp_profile):
    """验收 DoD「6 组测试数据」—— 后端只负责存储，档位判定在前端 lib/bp-level；
    这里验证：6 组数据都能正确录入并在 records 中以原始 sbp/dbp 返回，供前端判定。"""
    pid = bp_profile["profile_id"]
    uid = bp_profile["user_id"]
    groups = [
        (80, 50),    # 极低
        (110, 70),   # 正常
        (130, 85),   # 轻度偏高
        (150, 95),   # 中度偏高
        (170, 110),  # 严重偏高
        (119, 79),   # 临界值
    ]
    for sbp, dbp in groups:
        await _post_bp(client, user_auth["headers"], pid, sbp, dbp, days_ago=0, user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/metric/blood_pressure?size=100",
        headers=user_auth["headers"],
    )
    data = resp.json()
    assert data["total"] == 6
    returned = {(r["value"]["systolic"], r["value"]["diastolic"]) for r in data["records"]}
    for g in groups:
        assert g in returned, f"组 {g} 未在 records 中"
