"""[BUGFIX-MED-CROSS-PROFILE 2026-06-02] 用药提醒「串档」Bug 修复 —— 非UI自动化测试

场景：健康档案-非本人成员健康卡看板-用药提醒，原先 or_(member.id, is_None) 过滤
会把「本人（family_member_id 为空）」的用药记录混进成员看板。

修复后口径：
  - 本人看板（is_self=True） → 仅显示 family_member_id IS NULL 的本人用药
  - 成员看板（is_self=False）→ 仅显示 family_member_id == member.id 的成员用药

覆盖三处：
  TC-MED-001: get_medication_summary —— 成员看板不含本人药
  TC-MED-002: get_medication_summary —— 本人看板含全部本人药
  TC-MED-003: get_today_events       —— 成员看板时间线不含本人药
  TC-MED-004: get_today_events       —— 本人看板时间线含本人药
  TC-MED-005: _calculate_medication_score —— 成员评分不受本人药影响
  TC-MED-006: 两个不同成员之间互不串门
"""

from datetime import date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.models import FamilyMember, HealthProfile, MedicationReminder, User
from app.services import health_dashboard_service as svc

from .conftest import test_session


@pytest_asyncio.fixture
async def self_and_member(client, auth_headers):
    """为默认测试用户创建：本人成员(is_self) + 一个非本人成员，各自的 HealthProfile。"""
    async with test_session() as s:
        user = (await s.execute(
            select(User).where(User.phone == "13900000001")
        )).scalar_one()

        self_member = FamilyMember(
            user_id=user.id, relationship_type="self", nickname="账号本人",
            is_self=True, birthday=date(1980, 1, 1),
        )
        other_member = FamilyMember(
            user_id=user.id, relationship_type="parent", nickname="老爸",
            is_self=False, birthday=date(1955, 1, 1),
        )
        s.add_all([self_member, other_member])
        await s.flush()

        self_profile = HealthProfile(user_id=user.id, family_member_id=self_member.id, name="账号本人")
        other_profile = HealthProfile(user_id=user.id, family_member_id=other_member.id, name="老爸")
        s.add_all([self_profile, other_profile])
        await s.commit()
        await s.refresh(self_member)
        await s.refresh(other_member)
        return user, self_member, other_member


async def _add_reminder(*, user_id, family_member_id, name, remind_time="08:00"):
    async with test_session() as s:
        r = MedicationReminder(
            user_id=user_id,
            family_member_id=family_member_id,
            medicine_name=name,
            remind_time=remind_time,
            status="active",
            long_term=True,
        )
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return r


def _all_med_names(summary: dict) -> set:
    names = set()
    for p in summary.get("periods", []):
        for item in p.get("items", []):
            names.add(item["name"])
    return names


# ─── TC-MED-001: 成员看板用药汇总不含本人药 ──────────────────────────
@pytest.mark.asyncio
async def test_tc_med_001_member_summary_excludes_self(self_and_member):
    user, self_member, other_member = self_and_member
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人降压药")
    await _add_reminder(user_id=user.id, family_member_id=other_member.id, name="老爸降糖药")

    today = date.today()
    async with test_session() as s:
        om = (await s.execute(select(FamilyMember).where(FamilyMember.id == other_member.id))).scalar_one()
        summary = await svc.get_medication_summary(s, om, today)

    names = _all_med_names(summary)
    assert "老爸降糖药" in names
    assert "本人降压药" not in names


# ─── TC-MED-002: 本人看板用药汇总含全部本人药 ────────────────────────
@pytest.mark.asyncio
async def test_tc_med_002_self_summary_includes_self(self_and_member):
    user, self_member, other_member = self_and_member
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人降压药")
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人维生素", remind_time="12:30")
    await _add_reminder(user_id=user.id, family_member_id=other_member.id, name="老爸降糖药")

    today = date.today()
    async with test_session() as s:
        sm = (await s.execute(select(FamilyMember).where(FamilyMember.id == self_member.id))).scalar_one()
        summary = await svc.get_medication_summary(s, sm, today)

    names = _all_med_names(summary)
    assert "本人降压药" in names
    assert "本人维生素" in names
    assert "老爸降糖药" not in names


# ─── TC-MED-003: 成员看板时间线不含本人药 ────────────────────────────
@pytest.mark.asyncio
async def test_tc_med_003_member_timeline_excludes_self(self_and_member):
    user, self_member, other_member = self_and_member
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人降压药")
    await _add_reminder(user_id=user.id, family_member_id=other_member.id, name="老爸降糖药")

    today = date.today()
    async with test_session() as s:
        om = (await s.execute(select(FamilyMember).where(FamilyMember.id == other_member.id))).scalar_one()
        events = await svc.get_today_events(s, 999999, om, today)

    titles = [e["title"] for e in events if e.get("type") == "medication"]
    assert any("老爸降糖药" in t for t in titles)
    assert not any("本人降压药" in t for t in titles)


# ─── TC-MED-004: 本人看板时间线含本人药 ──────────────────────────────
@pytest.mark.asyncio
async def test_tc_med_004_self_timeline_includes_self(self_and_member):
    user, self_member, other_member = self_and_member
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人降压药")
    await _add_reminder(user_id=user.id, family_member_id=other_member.id, name="老爸降糖药")

    today = date.today()
    async with test_session() as s:
        sm = (await s.execute(select(FamilyMember).where(FamilyMember.id == self_member.id))).scalar_one()
        events = await svc.get_today_events(s, 999998, sm, today)

    titles = [e["title"] for e in events if e.get("type") == "medication"]
    assert any("本人降压药" in t for t in titles)
    assert not any("老爸降糖药" in t for t in titles)


# ─── TC-MED-005: 成员用药评分不受本人药影响 ──────────────────────────
@pytest.mark.asyncio
async def test_tc_med_005_member_score_isolated(self_and_member):
    user, self_member, other_member = self_and_member
    # 本人有药但从未打卡（若串入会拉低成员评分）；成员无药 → 应满分 20
    await _add_reminder(user_id=user.id, family_member_id=None, name="本人降压药")

    today = date.today()
    async with test_session() as s:
        om = (await s.execute(select(FamilyMember).where(FamilyMember.id == other_member.id))).scalar_one()
        score = await svc._calculate_medication_score(s, om, today)

    # 成员自己没有任何用药记录 → 满分 20，证明本人药未串入
    assert score == 20.0


# ─── TC-MED-006: 两个不同成员互不串门 ────────────────────────────────
@pytest.mark.asyncio
async def test_tc_med_006_members_isolated_from_each_other(self_and_member):
    user, self_member, other_member = self_and_member
    async with test_session() as s:
        m2 = FamilyMember(
            user_id=user.id, relationship_type="parent", nickname="老妈",
            is_self=False, birthday=date(1958, 1, 1),
        )
        s.add(m2)
        await s.commit()
        await s.refresh(m2)
    m2_id = m2.id

    await _add_reminder(user_id=user.id, family_member_id=other_member.id, name="老爸降糖药")
    await _add_reminder(user_id=user.id, family_member_id=m2_id, name="老妈钙片")

    today = date.today()
    async with test_session() as s:
        om = (await s.execute(select(FamilyMember).where(FamilyMember.id == other_member.id))).scalar_one()
        summary = await svc.get_medication_summary(s, om, today)

    names = _all_med_names(summary)
    assert "老爸降糖药" in names
    assert "老妈钙片" not in names
