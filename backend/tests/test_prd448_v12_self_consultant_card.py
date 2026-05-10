"""
[PRD-448 v1.2] 增量补丁单元测试 —— AI 首页「本人态咨询人胶囊」修复

覆盖核心验收点（PRD §7.2 接口验收）：
- 7.2.1 用户没有 is_self=True 的 FamilyMember（如老用户/异常账号），
        GET /api/v1/consultant/0/profile_card 仍 200，返回基础结构体（nickname="本人"）。
- 7.2.2 本人 FamilyMember 存在但档案完全空白，仍 200，is_self=True，percent=0。
- 7.2.3 本人 FamilyMember 存在 + 档案完整，正常返回 7 项 + percent>0 + is_self=True。
- 7.2.4 未登录态调 id=0 → 401（与现有鉴权一致）。
- 7.2.5 非本人成员 id 不存在 → 仍 404（兜底仅对 id=0 生效）。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.models.models import FamilyMember, HealthProfile, User
from tests.conftest import test_session


@pytest.mark.asyncio
async def test_self_profile_card_no_self_member_returns_basic_structure(
    client: AsyncClient, auth_headers
):
    """[PRD-448 v1.2 §4.3] 用户没有 is_self=True 的 FamilyMember 时，id=0 仍 200 返回基础结构。

    模拟"老用户/异常账号"场景：先把注册时自动创建的 is_self=True FamilyMember 删除。
    """
    async with test_session() as session:
        await session.execute(
            delete(FamilyMember).where(FamilyMember.is_self == True)  # noqa: E712
        )
        await session.commit()

    resp = await client.get("/api/v1/consultant/0/profile_card", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["consultant_id"] == 0
    assert data["nickname"] == "本人"
    assert data["is_self"] is True
    assert data["fields"]["gender"]["filled"] is False
    assert data["fields"]["age"]["filled"] is False
    assert data["fields"]["height"]["filled"] is False
    assert data["fields"]["weight"]["filled"] is False
    assert data["fields"]["past_history"]["filled"] is False
    assert data["fields"]["allergy"]["filled"] is False
    assert data["fields"]["long_term_meds"]["filled"] is False
    assert data["completeness"]["percent"] == 0
    assert data["completeness"]["filled_count"] == 0
    assert data["completeness"]["total"] == 7


@pytest.mark.asyncio
async def test_self_profile_card_empty_self_member_returns_basic_structure(
    client: AsyncClient, auth_headers
):
    """[PRD-448 v1.2 §4.3] 本人 FamilyMember 已自动创建（注册流程）但所有档案字段都空白时，
    仍返回 200 + is_self=True + percent=0 + filled_count=0。"""
    resp = await client.get("/api/v1/consultant/0/profile_card", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_self"] is True
    # 注册时自动创建的本人 FamilyMember nickname 默认为 "本人"
    assert data["nickname"] in ("张三", "本人")
    assert data["completeness"]["percent"] == 0
    assert data["completeness"]["filled_count"] == 0


@pytest.mark.asyncio
async def test_self_profile_card_complete_returns_full_fields(
    client: AsyncClient, auth_headers
):
    """[PRD-448 v1.2 §7.2] 本人档案 6/7 项填全时，percent>=80 + is_self=True。"""
    from datetime import date

    async with test_session() as session:
        # 把已有的本人 FamilyMember 字段补全（不重新插入，避免主键冲突）
        result = await session.execute(
            select(FamilyMember).where(FamilyMember.is_self == True)  # noqa: E712
        )
        member = result.scalar_one()
        member.nickname = "李四"
        member.gender = "男"
        member.birthday = date(1990, 1, 1)
        member.height = 175.0
        member.weight = 70.0
        member.medical_histories = ["高血压"]
        member.allergies = ["花生"]
        await session.commit()

    resp = await client.get("/api/v1/consultant/0/profile_card", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_self"] is True
    assert data["fields"]["gender"]["filled"] is True
    assert data["fields"]["age"]["filled"] is True
    assert data["fields"]["height"]["filled"] is True
    assert data["fields"]["weight"]["filled"] is True
    assert data["fields"]["past_history"]["filled"] is True
    assert data["fields"]["allergy"]["filled"] is True
    # 6/7 项填齐（长期用药未填），至少 80% 以上
    assert data["completeness"]["percent"] >= 80


@pytest.mark.asyncio
async def test_self_profile_card_unauthorized_returns_401(client: AsyncClient):
    """[PRD-448 v1.2 §7.2] 未登录态调 id=0 必须 401/403，不能因为 id=0 兜底而泄露。"""
    resp = await client.get("/api/v1/consultant/0/profile_card")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_non_self_unknown_member_still_404(client: AsyncClient, auth_headers):
    """[PRD-448 v1.2] 非本人成员 id（>0）不存在时仍返回 404；兜底仅对 id=0 生效。"""
    resp = await client.get("/api/v1/consultant/99999/profile_card", headers=auth_headers)
    assert resp.status_code == 404
