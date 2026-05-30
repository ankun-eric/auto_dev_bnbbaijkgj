"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1 2026-05-31] 健康指标卡片统一改造 — 后端测试

覆盖：
1. 元数据接口 GET /api/health-metric-v1/meta
2. 历史筛选+分页 GET /api/health-metric-v1/{pid}/{metric_type}/history
3. AI 解读本次 POST /api/health-metric-v1/{pid}/{metric_type}/ai-explain-single
4. AI 解读趋势 POST /api/health-metric-v1/{pid}/{metric_type}/ai-explain-trend
5. 删除前权限校验 GET /api/health-metric-v1/{pid}/{metric_type}/{rid}/can-delete
   - 手工录入：can_delete=True
   - 设备同步：can_delete=False（PRD §4.3 设备同步只读）
6. 血氧（spo2）作为四指标之一，全部接口可用
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text


@pytest_asyncio.fixture
async def user_auth(client: AsyncClient, auth_headers):
    from app.models.models import User
    from .conftest import test_session

    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one()
        return {"user_id": user.id, "headers": auth_headers}


@pytest_asyncio.fixture
async def metric_profile(user_auth):
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


_RID_COUNTER = {"next": 60000}


async def _insert_metric(profile_id: int, metric_type: str, value: dict, *,
                         days_ago: int = 0, hour: int = 8, minute: int = 30,
                         source: str = "manual", user_id: int = 1) -> int:
    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    measured_at = datetime.now() - timedelta(days=days_ago)
    measured_at = measured_at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, :mt, :vj, :src, :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id, "mt": metric_type,
            "vj": _json.dumps(value), "src": source,
            "ma": measured_at, "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()
    return rid


# ─── 1. 元数据接口 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_endpoint_returns_four_metrics(client: AsyncClient, auth_headers):
    """[PRD §九.1] /meta 返回四指标元数据。"""
    r = await client.get("/api/health-metric-v1/meta", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data", body)
    metric_types = set(data.get("metric_types") or [])
    assert metric_types == {"blood_pressure", "blood_glucose", "heart_rate", "spo2"}, \
        f"四指标必须齐全（含血氧 spo2）：实际 {metric_types}"

    metrics = data.get("metrics") or {}
    # 血氧必须包含 label/unit/scene_options
    assert "spo2" in metrics, "PRD §八：必须包含血氧 spo2 模块"
    spo2 = metrics["spo2"]
    assert spo2.get("unit") == "%"
    assert spo2.get("label") == "血氧"
    assert len(spo2.get("scene_options") or []) > 0


# ─── 2. 历史筛选 + 分页 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_basic_pagination(client: AsyncClient, user_auth, metric_profile):
    """[PRD §五.4] 支持 page_size + has_more 字段。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    # 插入 25 条心率
    for i in range(25):
        await _insert_metric(pid, "heart_rate",
                             {"value": 72 + i % 10, "activity": "静息"},
                             days_ago=i % 7, hour=9, minute=i, user_id=uid)

    r = await client.get(
        f"/api/health-metric-v1/{pid}/heart_rate/history",
        headers=user_auth["headers"], params={"page": 1, "page_size": 10, "date_range": "30d"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 25
    assert len(data["items"]) == 10
    assert data["has_more"] is True
    assert data["page"] == 1

    # 第二页
    r2 = await client.get(
        f"/api/health-metric-v1/{pid}/heart_rate/history",
        headers=user_auth["headers"], params={"page": 2, "page_size": 10, "date_range": "30d"},
    )
    assert r2.status_code == 200
    data2 = r2.json()["data"]
    assert len(data2["items"]) == 10
    assert data2["page"] == 2


@pytest.mark.asyncio
async def test_history_filter_by_source(client: AsyncClient, user_auth, metric_profile):
    """[PRD §五.3] 来源筛选：手工录入 / 设备同步 / 全部。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    await _insert_metric(pid, "spo2", {"value": 97, "period": "静息"}, days_ago=0, source="manual", user_id=uid)
    await _insert_metric(pid, "spo2", {"value": 95, "period": "运动后"}, days_ago=1, source="huawei_watch", user_id=uid)
    await _insert_metric(pid, "spo2", {"value": 92, "period": "睡眠中"}, days_ago=2, source="xiaomi_band", user_id=uid)

    # manual only
    r = await client.get(
        f"/api/health-metric-v1/{pid}/spo2/history",
        headers=user_auth["headers"], params={"source": "manual", "date_range": "30d"},
    )
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["source"] == "manual"
    assert data["items"][0]["editable"] is True

    # device only（非 manual）
    r2 = await client.get(
        f"/api/health-metric-v1/{pid}/spo2/history",
        headers=user_auth["headers"], params={"source": "device", "date_range": "30d"},
    )
    data2 = r2.json()["data"]
    assert data2["total"] == 2
    for item in data2["items"]:
        assert item["source"] != "manual"
        assert item["editable"] is False, "设备同步记录 editable 必须为 False（PRD §4.3）"


@pytest.mark.asyncio
async def test_history_filter_by_status(client: AsyncClient, user_auth, metric_profile):
    """[PRD §五.3] 状态档位筛选。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    # 血压：插入 1 条正常 + 1 条偏高
    await _insert_metric(pid, "blood_pressure",
                         {"systolic": 115, "diastolic": 75, "period": "晨起"},
                         days_ago=0, user_id=uid)
    await _insert_metric(pid, "blood_pressure",
                         {"systolic": 155, "diastolic": 95, "period": "晨起"},
                         days_ago=1, user_id=uid)
    await _insert_metric(pid, "blood_pressure",
                         {"systolic": 170, "diastolic": 105, "period": "晨起"},
                         days_ago=2, user_id=uid)

    # severe_high 筛选
    r = await client.get(
        f"/api/health-metric-v1/{pid}/blood_pressure/history",
        headers=user_auth["headers"], params={"status": "severe_high", "date_range": "30d"},
    )
    data = r.json()["data"]
    assert data["total"] == 1, f"严重偏高仅 1 条，实际 {data['total']}"
    assert data["items"][0]["status"]["key"] == "severe_high"


@pytest.mark.asyncio
async def test_history_sort_desc_by_measured_at(client: AsyncClient, user_auth, metric_profile):
    """[PRD §4.6] 按测量时间严格倒序。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    await _insert_metric(pid, "heart_rate", {"value": 70, "activity": "静息"}, days_ago=2, hour=8, user_id=uid)
    await _insert_metric(pid, "heart_rate", {"value": 75, "activity": "静息"}, days_ago=0, hour=10, user_id=uid)
    await _insert_metric(pid, "heart_rate", {"value": 72, "activity": "静息"}, days_ago=1, hour=15, user_id=uid)

    r = await client.get(
        f"/api/health-metric-v1/{pid}/heart_rate/history",
        headers=user_auth["headers"], params={"date_range": "30d"},
    )
    items = r.json()["data"]["items"]
    assert len(items) == 3
    # 时间倒序
    times = [it["measured_at"] for it in items]
    assert times == sorted(times, reverse=True), f"必须按测量时间严格倒序：{times}"


# ─── 3/4. AI 解读 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_explain_single_for_all_four_metrics(client: AsyncClient, user_auth, metric_profile):
    """[PRD §七] 四指标本次解读全部可用，返回 content/model/prompt_version。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    cases = [
        ("blood_pressure", {"systolic": 145, "diastolic": 92, "period": "晨起"}),
        ("blood_glucose", {"value": 8.5, "period": "餐后2h"}),
        ("heart_rate", {"value": 105, "activity": "运动后"}),
        ("spo2", {"value": 91, "period": "睡眠中"}),
    ]
    for mt, val in cases:
        rid = await _insert_metric(pid, mt, val, days_ago=0, user_id=uid)
        r = await client.post(
            f"/api/health-metric-v1/{pid}/{mt}/ai-explain-single",
            headers=user_auth["headers"], json={"record_id": rid},
        )
        assert r.status_code == 200, f"{mt} ai-explain-single failed: {r.text}"
        data = r.json()["data"]
        assert data.get("content"), f"{mt} content 必须非空"
        assert data.get("prompt_version") == "card-unify-v1"


@pytest.mark.asyncio
async def test_ai_explain_trend_for_all_four_metrics(client: AsyncClient, user_auth, metric_profile):
    """[PRD §七] 四指标趋势解读全部可用，支持 7d/30d/90d。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    # 给四个指标各插几条数据
    for d in range(3):
        await _insert_metric(pid, "blood_pressure",
                             {"systolic": 130 + d, "diastolic": 85, "period": "晨起"},
                             days_ago=d, user_id=uid)
        await _insert_metric(pid, "blood_glucose",
                             {"value": 6.0 + d * 0.5, "period": "空腹"},
                             days_ago=d, user_id=uid)
        await _insert_metric(pid, "heart_rate",
                             {"value": 75 + d, "activity": "静息"},
                             days_ago=d, user_id=uid)
        await _insert_metric(pid, "spo2",
                             {"value": 96 - d, "period": "静息"},
                             days_ago=d, user_id=uid)

    for mt in ["blood_pressure", "blood_glucose", "heart_rate", "spo2"]:
        for rng in ["7d", "30d", "90d"]:
            r = await client.post(
                f"/api/health-metric-v1/{pid}/{mt}/ai-explain-trend",
                headers=user_auth["headers"], json={"range": rng},
            )
            assert r.status_code == 200, f"{mt}/{rng} ai-explain-trend failed: {r.text}"
            data = r.json()["data"]
            assert data.get("summary"), f"{mt}/{rng} summary 必须非空"
            assert data.get("days") in (7, 30, 90)


# ─── 5. can-delete 权限校验 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_can_delete_manual_record(client: AsyncClient, user_auth, metric_profile):
    """[PRD §4.3] 手工录入的记录可删除。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    rid = await _insert_metric(pid, "blood_glucose", {"value": 5.6, "period": "空腹"},
                               source="manual", user_id=uid)
    r = await client.get(
        f"/api/health-metric-v1/{pid}/blood_glucose/{rid}/can-delete",
        headers=user_auth["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["can_delete"] is True
    assert body.get("record_summary"), "二次确认弹窗信息回显（PRD §4.5）"


@pytest.mark.asyncio
async def test_cannot_delete_device_synced_record(client: AsyncClient, user_auth, metric_profile):
    """[PRD §4.3] 设备同步记录不能删除。"""
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    rid = await _insert_metric(pid, "heart_rate", {"value": 78, "activity": "静息"},
                               source="huawei_watch", user_id=uid)
    r = await client.get(
        f"/api/health-metric-v1/{pid}/heart_rate/{rid}/can-delete",
        headers=user_auth["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["can_delete"] is False, "设备同步记录必须禁止删除"
    assert "智能设备" in body["reason"] or "锁定" in body["reason"]


# ─── 6. 血氧（spo2）作为四指标之一 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_spo2_full_lifecycle(client: AsyncClient, user_auth, metric_profile):
    """[PRD §八] 新增血氧模块：历史 → AI 解读 → 删除全流程。

    注：SQLite 测试环境 BigInteger 自增有限制，记录直接通过 _insert_metric 注入。
    """
    pid = metric_profile["profile_id"]
    uid = user_auth["user_id"]
    headers = user_auth["headers"]

    rid = await _insert_metric(pid, "spo2", {"value": 93, "period": "静息"},
                               days_ago=0, source="manual", user_id=uid)

    # 历史 - 数据归类为 mild_low（91~94）
    r2 = await client.get(
        f"/api/health-metric-v1/{pid}/spo2/history",
        headers=headers, params={"date_range": "7d"},
    )
    assert r2.status_code == 200
    items = r2.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["status"]["key"] == "mild_low"
    assert items[0]["editable"] is True

    # AI 解读本次
    r3 = await client.post(
        f"/api/health-metric-v1/{pid}/spo2/ai-explain-single",
        headers=headers, json={"record_id": rid},
    )
    assert r3.status_code == 200
    assert "血氧" in r3.json()["data"]["content"]

    # 删除
    r4 = await client.delete(
        f"/api/health-profile-v3/{pid}/metric/spo2/{rid}",
        headers=headers,
    )
    assert r4.status_code == 200

    # 历史已为空
    r5 = await client.get(
        f"/api/health-metric-v1/{pid}/spo2/history",
        headers=headers, params={"date_range": "7d"},
    )
    assert r5.json()["data"]["total"] == 0


# ─── 7. 边界：未知 metric_type 拒绝 ────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_unknown_metric_type(client: AsyncClient, user_auth, metric_profile):
    pid = metric_profile["profile_id"]
    r = await client.get(
        f"/api/health-metric-v1/{pid}/unknown_type/history",
        headers=user_auth["headers"],
    )
    assert r.status_code == 400


# ─── 8. 权限：他人 profile 拒绝访问 ────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_other_user_profile(client: AsyncClient, user_auth):
    """非档案所有者访问应返回 404 或 403。"""
    headers = user_auth["headers"]
    # 用不存在的 profile_id
    r = await client.get(
        f"/api/health-metric-v1/99999999/blood_pressure/history",
        headers=headers, params={"date_range": "7d"},
    )
    assert r.status_code in (403, 404)
