"""[BUGFIX-DELETE-MEMBER-HEALTHDATA-PROMPT-V1 2026-06-02]
删除家庭成员「删不掉」提示优化 — 回归测试

原始 Bug：删除名下挂着健康档案子数据（既往病史/过敏史等）的家庭成员时，
真正执行删除会硬删 health_profiles 行 → 触发子表外键约束 → 被全局兜底翻译成
「关联数据不存在，请检查所绑定的表单/分类是否有效」这句看不懂的提示。

修复：删除前逐类统计该成员名下所有阻塞数据，存在则汇总「类别+数量」返回结构化
HAS_HEALTH_DATA 提示，阻止删除，永不再落入通用兜底报错。

覆盖：
- TC-01: 名下有既往病史 → 删除被阻断，HAS_HEALTH_DATA，提示含「X 条既往病史」
- TC-02: 同时卡多类（既往病史 + 过敏史 + 体检报告 + 用药提醒）→ 一次性全列出
- TC-03: 提示文案永不为旧兜底文案「关联数据不存在……」
- TC-04: 清空所有子数据后 → 可正常删除（reason_code=OK）
- TC-05: 名下无任何子数据的干净成员 → 直接删除成功
- TC-06: 健康记录（HealthMetricRecord）也能精确数出条数
- TC-07: 中医诊断 / 健康提醒 / 报告历史也纳入排查
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import (
    FamilyMember,
    HealthProfile,
    HealthInfoExtra,
    HealthEvent,
    MedicalRecordCard,
    CheckupReport,
    MedicationReminder,
    TCMDiagnosis,
    HealthReminder,
    ReportHistory,
    User,
    UserRole,
)


OLD_FALLBACK_MSG = "关联数据不存在，请检查所绑定的表单/分类是否有效"


async def _make_user(phone: str, nickname: str = "用户") -> int:
    async with test_session() as s:
        u = User(
            phone=phone,
            password_hash=get_password_hash("p123"),
            nickname=nickname,
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid, nickname=nickname, relationship_type="本人",
            is_self=True, avatar_color_index=0,
        ))
        await s.commit()
        return uid


async def _headers(client: AsyncClient, phone: str) -> dict:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}", "Client-Type": "h5-user"}


async def _create_member(uid: int, nickname: str = "黎明", relation: str = "父亲") -> int:
    async with test_session() as s:
        m = FamilyMember(
            user_id=uid, nickname=nickname, relationship_type=relation,
            is_self=False, avatar_color_index=1,
        )
        s.add(m)
        await s.commit()
        return m.id


async def _create_profile(uid: int, member_id: int, name: str = "黎明") -> int:
    async with test_session() as s:
        hp = HealthProfile(user_id=uid, family_member_id=member_id, name=name)
        s.add(hp)
        await s.commit()
        return hp.id


@pytest.fixture(autouse=True)
def _reset_delete_rate_limit():
    try:
        from app.api.family_member_v2 import _DELETE_RATE_BUCKET
        _DELETE_RATE_BUCKET.clear()
        yield
        _DELETE_RATE_BUCKET.clear()
    except Exception:
        yield


@pytest.mark.asyncio
async def test_tc01_medical_history_blocks_delete(client: AsyncClient):
    """名下有 3 条既往病史 → 删除被阻断，提示具体类别+数量。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)
    pid = await _create_profile(uid, mid)

    async with test_session() as s:
        s.add(HealthInfoExtra(
            profile_id=pid,
            chronic_diseases=["高血压", "糖尿病"],
            surgery_history=["阑尾切除"],
        ))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_HEALTH_DATA"
    assert "3 条既往病史" in detail["message"]
    assert detail["message"].startswith("该成员名下还有")
    assert detail["message"].endswith("请先清空后再删除。")
    assert "3 条既往病史" in detail.get("blocking_items", [])


@pytest.mark.asyncio
async def test_tc02_multiple_blockers_listed_at_once(client: AsyncClient):
    """同时卡多类 → 一次性把所有原因全列出来。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)
    pid = await _create_profile(uid, mid)

    async with test_session() as s:
        s.add(HealthInfoExtra(
            profile_id=pid,
            chronic_diseases=["高血压", "糖尿病", "冠心病"],   # 3 既往病史
            drug_allergies=["青霉素"],                          # 1 过敏史
        ))
        # 2 份体检报告
        s.add(CheckupReport(user_id=uid, family_member_id=mid, report_type="常规"))
        s.add(CheckupReport(user_id=uid, family_member_id=mid, report_type="血常规"))
        # 1 条用药提醒
        s.add(MedicationReminder(user_id=uid, medicine_name="降压药", family_member_id=mid))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_HEALTH_DATA"
    msg = detail["message"]
    # 四类卡点必须一次性全部出现
    assert "3 条既往病史" in msg
    assert "1 条过敏史" in msg
    assert "2 份体检报告" in msg
    assert "1 条用药提醒" in msg


@pytest.mark.asyncio
async def test_tc03_never_old_fallback_message(client: AsyncClient):
    """删除家庭成员场景永不再出现旧通用兜底报错。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)
    pid = await _create_profile(uid, mid)

    async with test_session() as s:
        s.add(HealthInfoExtra(profile_id=pid, chronic_diseases=["高血压"]))
        s.add(HealthEvent(user_id=uid, profile_id=pid, event_type="diary",
                          title="头疼", event_date=__import__("datetime").date.today()))
        s.add(MedicalRecordCard(user_id=uid, profile_id=pid, title="门诊病历"))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert OLD_FALLBACK_MSG not in detail["message"]
    assert detail["reason_code"] == "HAS_HEALTH_DATA"


@pytest.mark.asyncio
async def test_tc04_delete_ok_after_cleanup(client: AsyncClient):
    """清空所有子数据后可正常删除。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)
    pid = await _create_profile(uid, mid)

    async with test_session() as s:
        s.add(HealthInfoExtra(profile_id=pid, chronic_diseases=["高血压"]))
        await s.commit()

    # 第一次：被阻断
    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400

    # 清空子数据
    async with test_session() as s:
        from sqlalchemy import delete as sql_delete
        await s.execute(sql_delete(HealthInfoExtra).where(HealthInfoExtra.profile_id == pid))
        await s.commit()

    # 第二次：成功
    res2 = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res2.status_code == 200, res2.text
    data = res2.json()["data"]
    assert data["reason_code"] == "OK"
    assert "family_member" in data["deleted_tables"]


@pytest.mark.asyncio
async def test_tc05_clean_member_deletes_directly(client: AsyncClient):
    """名下无任何子数据的干净成员 → 直接删除成功。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid, "干净成员")

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["reason_code"] == "OK"


@pytest.mark.asyncio
async def test_tc08_empty_shell_info_extra_does_not_block(client: AsyncClient):
    """[BUGFIX-DELETE-MEMBER-EMPTY-SHELL-IGNORE-V1 2026-06-02]
    用户点进「档案附加信息」但未填写任何内容，生成的「空壳」记录（所有 JSON 列为空），
    不应再阻塞删除。删除成员时应直接成功，并自动把空壳行一并清掉，
    且绝不再出现旧的「健康档案附加信息」卡点提示或旧通用兜底报错。
    """
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid, "黎明")
    pid = await _create_profile(uid, mid, "黎明")

    # 制造一条空壳：点进去没填任何东西
    async with test_session() as s:
        s.add(HealthInfoExtra(profile_id=pid))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["reason_code"] == "OK"
    assert "family_member" in data["deleted_tables"]
    # 不能再出现旧的空壳卡点提示
    assert "健康档案附加信息" not in res.text
    assert OLD_FALLBACK_MSG not in res.text

    # 空壳行应已被一并清掉
    async with test_session() as s:
        from sqlalchemy import select as sql_select, func as sql_func
        cnt = await s.execute(
            sql_select(sql_func.count(HealthInfoExtra.id)).where(
                HealthInfoExtra.profile_id == pid
            )
        )
        assert int(cnt.scalar() or 0) == 0


@pytest.mark.asyncio
async def test_tc09_empty_shell_does_not_hide_real_data(client: AsyncClient):
    """空壳放行不影响真实内容拦截：附加信息里有真实条目时仍照常阻塞。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid, "黎明")
    pid = await _create_profile(uid, mid, "黎明")

    async with test_session() as s:
        s.add(HealthInfoExtra(profile_id=pid, chronic_diseases=["高血压", "糖尿病"]))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_HEALTH_DATA"
    assert "2 条既往病史" in detail["message"]


@pytest.mark.asyncio
async def test_tc06_health_metric_records_counted(client: AsyncClient):
    """健康记录（血压等）也能精确数出条数。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)
    pid = await _create_profile(uid, mid)

    try:
        from app.models.health_v3 import HealthMetricRecord
    except Exception:
        pytest.skip("HealthMetricRecord 模型不可用")

    import datetime as _dt
    async with test_session() as s:
        # HealthMetricRecord.id 为 BigInteger，在 SQLite 下不自增，需显式赋 id
        for i in range(4):
            s.add(HealthMetricRecord(
                id=900000 + i,
                profile_id=pid, metric_type="blood_pressure",
                value_json={"systolic": 128, "diastolic": 82},
                source="manual",
                measured_at=_dt.datetime.utcnow(),
                created_by=uid,
            ))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_HEALTH_DATA"
    assert "4 条健康记录" in detail["message"]


@pytest.mark.asyncio
async def test_tc07_tcm_reminder_reporthistory_counted(client: AsyncClient):
    """中医诊断 / 健康提醒 / 报告历史 也纳入排查。"""
    phone = f"199{uuid.uuid4().hex[:8]}"
    uid = await _make_user(phone, "本人")
    h = await _headers(client, phone)
    mid = await _create_member(uid)

    import datetime as _dt
    async with test_session() as s:
        s.add(TCMDiagnosis(user_id=uid, family_member_id=mid, constitution_type="阳虚质"))
        s.add(HealthReminder(
            user_id=uid, member_id=mid, reminder_type="checkup", title="复查",
            scheduled_date=_dt.date.today(), created_by=uid,
        ))
        s.add(ReportHistory(
            user_id=uid, family_member_id=mid, report_name="体检报告", source_type="体检报告",
        ))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    msg = res.json()["detail"]["message"]
    assert "1 条中医诊断记录" in msg
    assert "1 条健康提醒" in msg
    assert "1 条报告历史" in msg
