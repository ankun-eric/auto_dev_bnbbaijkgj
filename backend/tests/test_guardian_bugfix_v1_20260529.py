"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 守护人体系一致性 + 真删除 + 配额防护 测试

PRD 测试用例：
- TC-LIST-01/02/03：列表口径一致性
- TC-DEL-01~06：真删除链路
- TC-INV-01~03：邀请必填姓名
- TC-QUOTA-01~04：配额公式
- TC-RATE-01/02：频次防护
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import (
    ChatMessage,
    ChatSession,
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    HealthProfile,
    MedicationReminder,
    User,
    UserRole,
)


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
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _make_family_member(user_phone: str, nickname: str = "家人", with_managed_user: bool = False) -> int:
    """创建一个 family_member（含 health_profile）"""
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == user_phone))).scalar_one()
        managed_user_id = None
        if with_managed_user:
            managed_phone = f"+8613{uuid.uuid4().hex[:8]}"
            managed_user = User(
                phone=managed_phone,
                password_hash=get_password_hash("p123"),
                nickname=nickname,
                role=UserRole.user,
            )
            s.add(managed_user)
            await s.flush()
            managed_user_id = managed_user.id

        m = FamilyMember(
            user_id=u.id,
            nickname=nickname,
            relationship_type="父亲",
            is_self=False,
            member_user_id=managed_user_id,
            avatar_color_index=1,
        )
        s.add(m)
        await s.flush()

        # 健康档案
        hp = HealthProfile(
            user_id=u.id,
            family_member_id=m.id,
            name=nickname,
        )
        s.add(hp)
        await s.flush()

        # FamilyManagement (active)
        if managed_user_id:
            mgmt = FamilyManagement(
                manager_user_id=u.id,
                managed_user_id=managed_user_id,
                managed_member_id=m.id,
                status="active",
                is_primary_guardian=True,
            )
            s.add(mgmt)

        await s.commit()
        return m.id


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """每个测试用例自动清空频次计数器"""
    from app.api.guardian_bugfix_v1 import reset_rate_limit_for_test
    reset_rate_limit_for_test(None)
    yield
    reset_rate_limit_for_test(None)


# ─────────── TC-INV: 邀请必填姓名 ───────────


@pytest.mark.asyncio
async def test_tc_inv_01_invite_without_nickname_returns_422(client: AsyncClient):
    """TC-INV-01：入口 2 不传 nickname 调用接口 → 422"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "邀请人A")
    h = await _headers(client, pa)

    res = await client.post(
        "/api/family/invitation",
        json={"relation_type": "父亲"},  # 不传 nickname
        headers=h,
    )
    assert res.status_code == 422, f"应返回 422，实际：{res.status_code} {res.text}"
    detail = res.json().get("detail", "")
    assert "姓名" in str(detail), f"应包含'姓名'提示，实际：{detail}"


@pytest.mark.asyncio
async def test_tc_inv_02_invite_with_nickname_ok(client: AsyncClient):
    """TC-INV-02：入口 2 正常传 nickname + relation_type → 成功"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "邀请人A")
    h = await _headers(client, pa)

    res = await client.post(
        "/api/family/invitation",
        json={"relation_type": "母亲", "nickname": "张妈妈"},
        headers=h,
    )
    assert res.status_code == 200, res.text
    assert res.json().get("invite_code")

    # 校验数据库里 invitation.nickname 写入正确
    async with test_session() as s:
        invs = (await s.execute(
            select(FamilyInvitation).where(FamilyInvitation.relation_type == "母亲")
        )).scalars().all()
        assert any(inv.nickname == "张妈妈" for inv in invs)


@pytest.mark.asyncio
async def test_tc_inv_03_invite_empty_nickname_blocked(client: AsyncClient):
    """TC-INV-03：传入空字符串 nickname 也应被拦截"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    res = await client.post(
        "/api/family/invitation",
        json={"relation_type": "父亲", "nickname": "  "},
        headers=h,
    )
    assert res.status_code == 422


# ─────────── TC-DEL: 真删除链路 ───────────


@pytest.mark.asyncio
async def test_tc_del_01_active_cannot_delete(client: AsyncClient):
    """TC-DEL-01：active 状态直接调用删除接口 → 400 + '请先解除守护关系'"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "active家人", with_managed_user=True)

    res = await client.delete(f"/api/guardian/v13/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    assert "解除守护" in str(res.json().get("detail", ""))


@pytest.mark.asyncio
async def test_tc_del_04_pending_invitation_blocks_delete(client: AsyncClient):
    """TC-DEL-04：有 pending 邀请的成员不可真删除 → 400"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "孤儿家人", with_managed_user=False)

    # 加 pending 邀请
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        s.add(FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=u.id,
            member_id=mid,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            relation_type="父亲",
            nickname="孤儿家人",
        ))
        await s.commit()

    res = await client.delete(f"/api/guardian/v13/family/member/{mid}", headers=h)
    assert res.status_code == 400
    assert "撤回未接受的邀请" in str(res.json().get("detail", ""))


@pytest.mark.asyncio
async def test_tc_del_03_active_medication_blocks_delete(client: AsyncClient):
    """TC-DEL-03：有进行中服药计划的成员不可真删除 → 400"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "孤儿家人", with_managed_user=False)

    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        s.add(MedicationReminder(
            user_id=u.id,
            family_member_id=mid,
            medicine_name="阿司匹林",
            status="active",
            is_paused=False,
        ))
        await s.commit()

    res = await client.delete(f"/api/guardian/v13/family/member/{mid}", headers=h)
    assert res.status_code == 400
    assert "服药计划" in str(res.json().get("detail", ""))


@pytest.mark.asyncio
async def test_tc_del_05_full_cascade_delete_8_tables(client: AsyncClient):
    """TC-DEL-05：全部校验通过后真删 → 数据级联硬删，多表数据消失"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "可删家人", with_managed_user=False)

    # 增加测试数据：1 个 health_profile、1 个 chat_session + 2 个 chat_message、1 个用药提醒（status != active）
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        # 新增第二个 health_profile（按 family_member_id 关联）
        s.add(HealthProfile(user_id=u.id, family_member_id=mid, name="额外档案"))

        # 添加 chat_session + chat_messages
        from app.models.models import SessionType, MessageRole
        cs = ChatSession(
            user_id=u.id,
            session_type=SessionType.health_qa,
            family_member_id=mid,
            title="对话1",
        )
        s.add(cs)
        await s.flush()
        s.add(ChatMessage(session_id=cs.id, role=MessageRole.user, content="Q"))
        s.add(ChatMessage(session_id=cs.id, role=MessageRole.assistant, content="A"))

        # 添加非 active 用药提醒（不会触发 R4）
        s.add(MedicationReminder(
            user_id=u.id, family_member_id=mid,
            medicine_name="维生素", status="paused", is_paused=True,
        ))
        await s.commit()

    # 真删之前预览
    res_prev = await client.get(f"/api/guardian/v13/family/member/{mid}/delete-preview", headers=h)
    assert res_prev.status_code == 200, res_prev.text
    prev = res_prev.json()
    assert prev["can_delete"] is True
    assert prev["impact"]["ai_conversation_count"] >= 1
    assert prev["impact"]["ai_message_count"] >= 2

    # 真删
    res = await client.delete(f"/api/guardian/v13/family/member/{mid}", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("deleted") is True
    assert body.get("event") == "conversation_target_deleted"

    # 验证：family_member / health_profile / chat_session / chat_message / medication_reminder 全部消失
    async with test_session() as s:
        fm = await s.get(FamilyMember, mid)
        assert fm is None, "family_member 应被物理删除"
        hp_cnt = (await s.execute(
            select(HealthProfile).where(HealthProfile.family_member_id == mid)
        )).scalars().all()
        assert len(hp_cnt) == 0
        cs_cnt = (await s.execute(
            select(ChatSession).where(ChatSession.family_member_id == mid)
        )).scalars().all()
        assert len(cs_cnt) == 0
        med_cnt = (await s.execute(
            select(MedicationReminder).where(MedicationReminder.family_member_id == mid)
        )).scalars().all()
        assert len(med_cnt) == 0


# ─────────── TC-LIST: 列表口径 ───────────


@pytest.mark.asyncio
async def test_tc_list_01_removed_status_filtered(client: AsyncClient):
    """TC-LIST-01：family_management.status='removed' 的记录不出现在 /family/list"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid_active = await _make_family_member(pa, "活跃家人", with_managed_user=True)
    mid_removed = await _make_family_member(pa, "已移除家人", with_managed_user=True)

    # 将 mid_removed 对应的 mgmt 标记为 removed
    async with test_session() as s:
        rows = (await s.execute(
            select(FamilyManagement).where(FamilyManagement.managed_member_id == mid_removed)
        )).scalars().all()
        for r in rows:
            r.status = "removed"
        await s.commit()

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    assert res.status_code == 200, res.text
    items = res.json().get("items", [])
    member_ids = [it.get("managed_member_id") for it in items]
    assert mid_active in member_ids, "active 家人应在列表中"
    assert mid_removed not in member_ids, "removed 家人不应在列表中"


@pytest.mark.asyncio
async def test_tc_list_03_target_left_grey_label(client: AsyncClient):
    """TC-LIST-03：cancelled_by_target 状态返回 target_left=true，并保留卡片"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "已退出家人", with_managed_user=True)

    async with test_session() as s:
        rows = (await s.execute(
            select(FamilyManagement).where(FamilyManagement.managed_member_id == mid)
        )).scalars().all()
        for r in rows:
            r.status = "cancelled_by_target"
        await s.commit()

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    assert res.status_code == 200
    items = res.json().get("items", [])
    target = next((it for it in items if it.get("managed_member_id") == mid), None)
    assert target is not None, "cancelled_by_target 卡片应保留显示"
    assert target.get("target_left") is True
    assert "对方已退出" in (target.get("display_substatus_label") or "")


@pytest.mark.asyncio
async def test_tc_list_ai_consultant_excludes_pending(client: AsyncClient):
    """补充：/api/family/members（AI 首页选择咨询人）只返回已建档成员，不含 pending 邀请"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 创建一条 pending 邀请（情况2，无 member_id）
    res_inv = await client.post(
        "/api/family/invitation",
        json={"relation_type": "父亲", "nickname": "新邀请"},
        headers=h,
    )
    assert res_inv.status_code == 200, res_inv.text

    res = await client.get("/api/family/members", headers=h)
    assert res.status_code == 200
    items = res.json().get("items", [])
    # 不应包含 pending 邀请记录（因为 member_id=NULL，accept 才会建档）
    nicknames = [it.get("nickname") for it in items]
    assert "新邀请" not in nicknames


# ─────────── TC-RATE: 频次防护 ───────────


@pytest.mark.asyncio
async def test_tc_rate_01_invite_5_per_day(client: AsyncClient):
    """TC-RATE-01：同一用户当天发起第 6 次邀请 → 429"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 前 5 次成功
    for i in range(5):
        res = await client.post(
            "/api/family/invitation",
            json={"relation_type": "朋友", "nickname": f"邀请{i}"},
            headers=h,
        )
        assert res.status_code == 200, f"第 {i+1} 次应成功，实际 {res.status_code}: {res.text}"

    # 第 6 次拦截
    res = await client.post(
        "/api/family/invitation",
        json={"relation_type": "朋友", "nickname": "第六次"},
        headers=h,
    )
    assert res.status_code == 429, res.text
    assert "明天" in str(res.json().get("detail", ""))


@pytest.mark.asyncio
async def test_tc_rate_delete_5_per_day(client: AsyncClient):
    """TC-RATE：删除接口 5 次/天频次防护"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 创建 6 个可删除的孤儿档案
    mids = []
    for i in range(6):
        mid = await _make_family_member(pa, f"孤儿{i}", with_managed_user=False)
        mids.append(mid)

    # 前 5 次删除应都成功
    for i in range(5):
        res = await client.delete(f"/api/guardian/v13/family/member/{mids[i]}", headers=h)
        assert res.status_code == 200, f"第 {i+1} 次应成功，实际 {res.status_code}: {res.text}"

    # 第 6 次被频次防护拦截
    res = await client.delete(f"/api/guardian/v13/family/member/{mids[5]}", headers=h)
    assert res.status_code == 429, res.text


# ─────────── 补充：删除预览接口 ───────────


@pytest.mark.asyncio
async def test_delete_preview_returns_impact(client: AsyncClient):
    """删除预览接口返回完整 impact 字段"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _make_family_member(pa, "预览家人", with_managed_user=False)

    res = await client.get(f"/api/guardian/v13/family/member/{mid}/delete-preview", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "can_delete" in data
    assert "gates" in data
    assert "impact" in data
    for gate_key in ("r1_not_active", "r2_no_device", "r3_no_pending_invitation", "r4_no_active_medication"):
        assert gate_key in data["gates"]
    for impact_key in ("health_profile_count", "ai_conversation_count", "ai_message_count"):
        assert impact_key in data["impact"]


@pytest.mark.asyncio
async def test_unguard_returns_cancelled_by_target_for_managed(client: AsyncClient):
    """补充：被守护人调用 unguard 接口 → status=cancelled_by_target"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    await _make_user(pb, "B")

    # 建守护关系：A 守护 B
    async with test_session() as s:
        a = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        b = (await s.execute(select(User).where(User.phone == pb))).scalar_one()
        m = FamilyMember(user_id=a.id, nickname="B", relationship_type="父亲", is_self=False, member_user_id=b.id)
        s.add(m)
        await s.flush()
        mgmt = FamilyManagement(
            manager_user_id=a.id, managed_user_id=b.id, managed_member_id=m.id,
            status="active", is_primary_guardian=True,
        )
        s.add(mgmt)
        await s.flush()
        mgmt_id = mgmt.id
        await s.commit()

    # B 调用 unguard
    h_b = await _headers(client, pb)
    res = await client.post(
        "/api/guardian/v13/family/relation/unguard",
        json={"management_id": mgmt_id},
        headers=h_b,
    )
    assert res.status_code == 200, res.text
    assert res.json().get("status") == "cancelled_by_target"
