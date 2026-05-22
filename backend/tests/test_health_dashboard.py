"""[PRD-HEALTH-DASHBOARD-V1] 家人健康看板 —— 非UI自动化测试

覆盖：
  TC-001 ~ TC-003: 看板汇总 API
  TC-004 ~ TC-006: 趋势数据 API
  TC-007 ~ TC-009: 健康提醒创建/列表
  TC-010 ~ TC-011: 提醒更新/删除
  TC-012:          体检推荐
  TC-013:          异常检查
"""

from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FamilyMember,
    HealthProfile,
    User,
)

from .conftest import test_session


# ─────────────────────── helpers / fixtures ───────────────────────────


async def _create_user(phone: str, nickname: str = "测试用户") -> User:
    from app.core.security import get_password_hash

    async with test_session() as s:
        user = User(
            phone=phone,
            password_hash=get_password_hash("pass123"),
            nickname=nickname,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


async def _login(client: AsyncClient, phone: str) -> str:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pass123", "nickname": phone,
    })
    res = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pass123",
    })
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def user_and_member(client: AsyncClient, auth_headers):
    """Create a FamilyMember (is_self) + HealthProfile for the default test user."""
    async with test_session() as s:
        user = (await s.execute(
            select(User).where(User.phone == "13900000001")
        )).scalar_one()

        member = FamilyMember(
            user_id=user.id,
            relationship_type="self",
            nickname="测试本人",
            is_self=True,
            birthday=date(1980, 1, 1),
        )
        s.add(member)
        await s.flush()

        profile = HealthProfile(
            user_id=user.id,
            family_member_id=member.id,
            name="测试本人",
        )
        s.add(profile)
        await s.commit()
        await s.refresh(member)
        await s.refresh(profile)
        return user, member, profile


async def _insert_metric(s, *, rid, profile_id, metric_type, value_json, measured_at, created_by):
    """Insert HealthMetricRecord with explicit id (BigInteger PK doesn't auto-increment in SQLite)."""
    import json as _json
    from sqlalchemy import text
    await s.execute(text(
        "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
        "VALUES (:id, :pid, :mt, :vj, 'manual', :ma, :ca, :cb)"
    ), {
        "id": rid, "pid": profile_id, "mt": metric_type,
        "vj": _json.dumps(value_json), "ma": measured_at, "ca": measured_at, "cb": created_by,
    })


@pytest_asyncio.fixture
async def seed_vitals(user_and_member):
    """Insert recent HealthMetricRecord entries for trend / dashboard tests."""
    _, member, profile = user_and_member
    now = datetime.utcnow()

    async with test_session() as s:
        rid = 1000
        for i in range(7):
            ts = now - timedelta(days=i, hours=8)
            await _insert_metric(s, rid=rid, profile_id=profile.id, metric_type="blood_pressure",
                                 value_json={"systolic": 120 + i, "diastolic": 78 + i, "period": "morning"},
                                 measured_at=ts, created_by=member.user_id)
            rid += 1
            await _insert_metric(s, rid=rid, profile_id=profile.id, metric_type="blood_glucose",
                                 value_json={"value": 5.2 + i * 0.1, "period": "fasting"},
                                 measured_at=ts, created_by=member.user_id)
            rid += 1
            await _insert_metric(s, rid=rid, profile_id=profile.id, metric_type="heart_rate",
                                 value_json={"value": 72 + i, "activity": "resting"},
                                 measured_at=ts, created_by=member.user_id)
            rid += 1
        await s.commit()
    return profile


# ─────────────────────── TC-001: 正常获取看板汇总 ────────────────────


@pytest.mark.asyncio
async def test_tc001_dashboard_summary(client: AsyncClient, auth_headers, user_and_member, seed_vitals):
    _, member, _ = user_and_member
    res = await client.get(f"/api/health-dashboard/{member.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == member.id
    assert "health_score" in data
    assert "latest_vitals" in data
    assert "medication_summary" in data
    assert "checkup_summary" in data


# ─────────────────────── TC-002: 无权限访问他人看板（403）─────────────


@pytest.mark.asyncio
async def test_tc002_dashboard_forbidden(client: AsyncClient, user_and_member):
    _, member, _ = user_and_member
    other_token = await _login(client, "13900000099")
    headers = {"Authorization": f"Bearer {other_token}", "Client-Type": "h5-user"}
    res = await client.get(f"/api/health-dashboard/{member.id}", headers=headers)
    assert res.status_code == 403


# ─────────────────────── TC-003: 不存在的 member_id（404 / 403）──────


@pytest.mark.asyncio
async def test_tc003_dashboard_nonexistent_member(client: AsyncClient, auth_headers):
    res = await client.get("/api/health-dashboard/999999", headers=auth_headers)
    assert res.status_code in (403, 404)


# ─────────────────────── TC-004: 获取趋势数据-默认7天 ────────────────


@pytest.mark.asyncio
async def test_tc004_trends_default_7days(client: AsyncClient, auth_headers, user_and_member, seed_vitals):
    _, member, _ = user_and_member
    res = await client.get(f"/api/health-dashboard/{member.id}/trends", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["days"] == 7
    assert isinstance(data["blood_pressure"], list)
    assert isinstance(data["blood_sugar"], list)
    assert isinstance(data["heart_rate"], list)
    assert len(data["blood_pressure"]) > 0
    assert "normal_ranges" in data


# ─────────────────────── TC-005: 获取趋势数据-切换30天 ───────────────


@pytest.mark.asyncio
async def test_tc005_trends_30days(client: AsyncClient, auth_headers, user_and_member, seed_vitals):
    _, member, _ = user_and_member
    res = await client.get(
        f"/api/health-dashboard/{member.id}/trends?days=30", headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["days"] == 30


# ─────────────────────── TC-006: 获取趋势数据-无数据时返回空数组 ─────


@pytest.mark.asyncio
async def test_tc006_trends_empty(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    res = await client.get(f"/api/health-dashboard/{member.id}/trends", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["blood_pressure"] == []
    assert data["blood_sugar"] == []
    assert data["heart_rate"] == []


# ─────────────────────── TC-007: 创建复诊提醒（成功）─────────────────


@pytest.mark.asyncio
async def test_tc007_create_reminder(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    payload = {
        "member_id": member.id,
        "reminder_type": "followup",
        "title": "心内科复诊",
        "hospital": "北京协和医院",
        "department": "心内科",
        "scheduled_date": (date.today() + timedelta(days=14)).isoformat(),
        "notes": "带上次检查报告",
    }
    res = await client.post("/api/health-reminders", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] > 0
    assert data["title"] == "心内科复诊"
    assert data["reminder_type"] == "followup"
    assert data["status"] == "pending"
    assert data["source"] == "manual"


# ─────────────────────── TC-008: 创建提醒-缺少必填字段（422）────────


@pytest.mark.asyncio
async def test_tc008_create_reminder_missing_fields(client: AsyncClient, auth_headers):
    res = await client.post("/api/health-reminders", json={}, headers=auth_headers)
    assert res.status_code == 422


# ─────────────────────── TC-009: 获取提醒列表 ────────────────────────


@pytest.mark.asyncio
async def test_tc009_list_reminders(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    for i in range(3):
        await client.post("/api/health-reminders", json={
            "member_id": member.id,
            "reminder_type": "checkup",
            "title": f"体检{i+1}",
            "scheduled_date": (date.today() + timedelta(days=30 + i)).isoformat(),
        }, headers=auth_headers)

    res = await client.get("/api/health-reminders", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3
    assert data["page"] == 1


# ─────────────────────── TC-010: 更新提醒-标记完成 ───────────────────


@pytest.mark.asyncio
async def test_tc010_update_reminder_complete(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    create_res = await client.post("/api/health-reminders", json={
        "member_id": member.id,
        "reminder_type": "followup",
        "title": "待完成提醒",
        "scheduled_date": date.today().isoformat(),
    }, headers=auth_headers)
    reminder_id = create_res.json()["id"]

    upd_res = await client.put(
        f"/api/health-reminders/{reminder_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert upd_res.status_code == 200
    data = upd_res.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


# ─────────────────────── TC-011: 删除提醒 ────────────────────────────


@pytest.mark.asyncio
async def test_tc011_delete_reminder(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    create_res = await client.post("/api/health-reminders", json={
        "member_id": member.id,
        "reminder_type": "checkup",
        "title": "待删除提醒",
        "scheduled_date": (date.today() + timedelta(days=60)).isoformat(),
    }, headers=auth_headers)
    reminder_id = create_res.json()["id"]

    del_res = await client.delete(
        f"/api/health-reminders/{reminder_id}", headers=auth_headers,
    )
    assert del_res.status_code == 200
    assert "删除" in del_res.json().get("message", "")

    list_res = await client.get("/api/health-reminders", headers=auth_headers)
    ids = [r["id"] for r in list_res.json()["items"]]
    assert reminder_id not in ids


# ─────────────────────── TC-012: 获取体检推荐 ────────────────────────


@pytest.mark.asyncio
async def test_tc012_checkup_recommendations(client: AsyncClient, auth_headers, user_and_member):
    _, member, _ = user_and_member
    res = await client.get(
        f"/api/health-reminders/recommendations?member_id={member.id}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "recommended_frequency" in data
    assert "age_group" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) > 0
    assert data["recommended_interval_months"] > 0


# ─────────────────────── TC-013: 触发异常检查 ────────────────────────


@pytest.mark.asyncio
async def test_tc013_alert_check(client: AsyncClient, auth_headers, user_and_member):
    """Insert an abnormal BP record then trigger /api/health-alerts/check."""
    _, member, profile = user_and_member

    async with test_session() as s:
        await _insert_metric(s, rid=9000, profile_id=profile.id, metric_type="blood_pressure",
                             value_json={"systolic": 160, "diastolic": 100, "period": "morning"},
                             measured_at=datetime.utcnow(), created_by=member.user_id)
        await s.commit()

    res = await client.post("/api/health-alerts/check", json={
        "member_id": member.id,
        "metric_type": "blood_pressure",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["checked"] is True
    assert data["abnormal_found"] is True
    assert isinstance(data["details"], list)
    assert len(data["details"]) > 0
    assert data["details"][0]["is_abnormal"] is True
