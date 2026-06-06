"""[PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 成员卡片状态机 + 统一删除 测试

TC-FMV2 覆盖：
- TC-FMV2-01: 仅本人 → state=S0；列表 quota_used=1（含本人卡，v1.1 新口径）
- TC-FMV2-02: 新建未邀请档案 → state=S2，可删除
- TC-FMV2-03: S2 状态直接删除成功，reason_code=OK
- TC-FMV2-04: S1 已绑定 → 删除返回 HAS_ACTIVE_GUARDIANSHIP
- TC-FMV2-05: S3 邀请中 → 删除返回 HAS_PENDING_INVITATION
- TC-FMV2-06: 重新邀请：旧 pending → cancelled + 新增 pending
- TC-FMV2-07: 解除守护：S1 → S6，management.status=removed
- TC-FMV2-08: 配额接口：含本人=不计入，与已建档案数对齐
- TC-FMV2-09: [BUGFIX-DELETE-RATELIMIT-V1] 删除频次上限放宽到 50 次/日，仅成功才计数
- TC-FMV2-09b: [BUGFIX-DELETE-RATELIMIT-V1] 删除失败（被其他规则拦住）不计入额度
- TC-FMV2-10: 删除别人档案 → PERMISSION_DENIED
- TC-FMV2-11: 删除不存在 → NOT_FOUND
- TC-FMV2-12: 本人档案不可删
- TC-FMV2-13: S5 已过期：自动转换并允许删除
- TC-FMV2-14: 删除后 family_member.status=deleted，列表不再出现
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
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
        s.add(FamilyMember(
            user_id=uid,
            nickname=nickname,
            relationship_type="本人",
            is_self=True,
            avatar_color_index=0,
        ))
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _create_member(uid: int, nickname: str = "家人A", relation: str = "父亲") -> int:
    """直接库内插一条非本人的 family_member"""
    async with test_session() as s:
        m = FamilyMember(
            user_id=uid,
            nickname=nickname,
            relationship_type=relation,
            is_self=False,
            avatar_color_index=1,
        )
        s.add(m)
        await s.commit()
        return m.id


@pytest.fixture(autouse=True)
def _reset_delete_rate_limit():
    """清空删除频次桶"""
    try:
        from app.api.family_member_v2 import _DELETE_RATE_BUCKET
        _DELETE_RATE_BUCKET.clear()
        yield
        _DELETE_RATE_BUCKET.clear()
    except Exception:
        yield


# ─── 列表与状态机 ───

@pytest.mark.asyncio
async def test_tc_fmv2_01_only_self_s0(client: AsyncClient):
    """仅本人 → S0；[v1.1] quota_used=1（含本人卡），quota_max=数据库 max_managed 原值（含本人）"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    res = await client.get("/api/family/member/state/list", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["state"] == "S0"
    assert body["items"][0]["is_self"] is True
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] quota_used 含本人卡，仅本人=1
    assert body["quota_used"] == 1
    assert body["guarded_count"] == 0
    # quota_max 应该 >= 1，且为「含本人」上限
    assert body["quota_max"] >= 1 or body["quota_max"] == -1


@pytest.mark.asyncio
async def test_tc_fmv2_02_new_member_s2(client: AsyncClient):
    """新建未邀请档案 → state=S2，可删除"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)

    mid = await _create_member(uid, "新家人", "父亲")

    res = await client.get("/api/family/member/state/list", headers=h)
    body = res.json()
    target = next((x for x in body["items"] if x["member_id"] == mid), None)
    assert target is not None
    assert target["state"] == "S2"
    assert target["state_label"] == "未邀请"
    assert target["primary_action"] == "invite"
    assert target["can_delete"] is True


# ─── 删除接口 ───

@pytest.mark.asyncio
async def test_tc_fmv2_03_delete_s2_ok(client: AsyncClient):
    """S2 状态直接删除成功 → reason_code=OK"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "X", "父亲")

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["data"]["reason_code"] == "OK"
    assert "family_member" in body["data"]["deleted_tables"]

    # 列表中应不再出现
    res2 = await client.get("/api/family/member/state/list", headers=h)
    body2 = res2.json()
    assert not any(x["member_id"] == mid for x in body2["items"])


@pytest.mark.asyncio
async def test_tc_fmv2_04_delete_s1_blocked(client: AsyncClient):
    """S1 已绑定 → 删除返回 HAS_ACTIVE_GUARDIANSHIP"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "已绑定", "父亲")

    # 插一条 active 的 FamilyManagement
    async with test_session() as s:
        # 创建被守护人 user
        mu_phone = f"+8613{uuid.uuid4().hex[:8]}"
        mu = User(
            phone=mu_phone,
            password_hash=get_password_hash("p123"),
            nickname="被守护",
            role=UserRole.user,
        )
        s.add(mu)
        await s.flush()
        s.add(FamilyManagement(
            manager_user_id=uid,
            managed_user_id=mu.id,
            managed_member_id=mid,
            status="active",
            is_primary_guardian=True,
        ))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_ACTIVE_GUARDIANSHIP"


@pytest.mark.asyncio
async def test_tc_fmv2_05_delete_s3_blocked(client: AsyncClient):
    """S3 邀请中 → 删除返回 HAS_PENDING_INVITATION"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "邀请中", "父亲")

    async with test_session() as s:
        s.add(FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=uid,
            member_id=mid,
            status="pending",
            expires_at=datetime.now() + timedelta(hours=12),
            relation_type="父亲",
            nickname="邀请中",
        ))
        await s.commit()

    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["reason_code"] == "HAS_PENDING_INVITATION"


# ─── 重新邀请 ───

@pytest.mark.asyncio
async def test_tc_fmv2_06_reinvite_cancels_old(client: AsyncClient):
    """重新邀请：旧 rejected → cancelled + 新增一条 pending"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "已拒绝", "父亲")

    # 插一条 rejected
    async with test_session() as s:
        s.add(FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=uid,
            member_id=mid,
            status="rejected",
            expires_at=datetime.now() + timedelta(hours=12),
            relation_type="父亲",
            nickname="已拒绝",
        ))
        await s.commit()

    res = await client.post(f"/api/family/member/{mid}/invite", json={}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cancelled_count"] == 1
    assert body["invite_code"]
    new_code = body["invite_code"]

    # 校验库内：rejected 已变 cancelled，新 pending 存在
    async with test_session() as s:
        all_invs = (await s.execute(
            select(FamilyInvitation).where(FamilyInvitation.member_id == mid)
        )).scalars().all()
        statuses = sorted([i.status for i in all_invs])
        assert statuses == ["cancelled", "pending"], f"实际: {statuses}"
        new_inv = next(i for i in all_invs if i.invite_code == new_code)
        assert new_inv.status == "pending"


# ─── 解除守护 ───

@pytest.mark.asyncio
async def test_tc_fmv2_07_unbind_s1_to_s6(client: AsyncClient):
    """解除守护：S1 → S6"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "已绑定", "父亲")

    async with test_session() as s:
        mu_phone = f"+8613{uuid.uuid4().hex[:8]}"
        mu = User(
            phone=mu_phone,
            password_hash=get_password_hash("p123"),
            nickname="被守护",
            role=UserRole.user,
        )
        s.add(mu)
        await s.flush()
        s.add(FamilyManagement(
            manager_user_id=uid,
            managed_user_id=mu.id,
            managed_member_id=mid,
            status="active",
            is_primary_guardian=True,
        ))
        await s.commit()

    res = await client.post(f"/api/family/member/{mid}/unbind", json={}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["data"]["new_state"] == "S6"

    # 列表中应为 S6
    res2 = await client.get("/api/family/member/state/list", headers=h)
    target = next((x for x in res2.json()["items"] if x["member_id"] == mid), None)
    assert target["state"] == "S6"


# ─── 配额 ───

@pytest.mark.asyncio
async def test_tc_fmv2_08_quota_endpoint(client: AsyncClient):
    """配额接口：[v1.1] 含本人卡，已建档案数=本人(1)+非本人(2)=3"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    await _create_member(uid, "X1", "父亲")
    await _create_member(uid, "X2", "母亲")

    res = await client.get("/api/family/member/quota", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] quota_used 含本人卡：1（本人）+ 2（家人）= 3
    assert body["quota_used"] == 3
    assert body["quota_max"] >= 3 or body["quota_max"] == -1
    assert body["guarded_count"] == 0
    assert body["self_member_id"] is not None


# ─── 频次限制 ───

@pytest.mark.asyncio
async def test_tc_fmv2_09_delete_rate_limit(client: AsyncClient):
    """[BUGFIX-DELETE-RATELIMIT-V1] 删除频次上限放宽到 50 次/日，第 51 次才拦截。
    用直接灌额度的方式逼近上限，避免真删 50 个档案。"""
    from app.api.family_member_v2 import (
        DELETE_RATE_LIMIT_PER_DAY,
        _record_delete_success,
        reset_delete_rate_limit_for_test,
    )

    assert DELETE_RATE_LIMIT_PER_DAY == 50

    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    reset_delete_rate_limit_for_test(None)

    # 先成功删 1 个，确认成功才计数
    mid0 = await _create_member(uid, "X0", "父亲")
    r = await client.delete(f"/api/family/member/{mid0}", headers=h)
    assert r.status_code == 200, r.text

    # 把额度灌到 50（含刚才那 1 次）
    for _ in range(50 - 1):
        _record_delete_success(uid)

    # 已达 50，第 51 次删除应被拦截
    mid_last = await _create_member(uid, "X-last", "父亲")
    r = await client.delete(f"/api/family/member/{mid_last}", headers=h)
    assert r.status_code == 429, r.text
    assert r.json()["detail"]["reason_code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_tc_fmv2_09b_failed_delete_not_counted(client: AsyncClient):
    """[BUGFIX-DELETE-RATELIMIT-V1] 删除失败（被其他规则拦住）不计入额度：
    反复尝试删一个 S1 已绑定成员（会被拦），额度始终为 0，
    之后删一个可删的孤儿档案仍能成功。"""
    from app.api.family_member_v2 import (
        _peek_delete_rate_limit,
        _DELETE_RATE_BUCKET,
        reset_delete_rate_limit_for_test,
    )

    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    uid_b = await _make_user(pb, "B")
    h = await _headers(client, pa)
    reset_delete_rate_limit_for_test(None)

    # 建一个 S1 已绑定成员（删除会被 HAS_ACTIVE_GUARDIANSHIP 拦）
    async with test_session() as s:
        m = FamilyMember(user_id=uid, nickname="绑定家人", relationship_type="父亲",
                         is_self=False, member_user_id=uid_b, status="active")
        s.add(m)
        await s.flush()
        mgmt = FamilyManagement(
            manager_user_id=uid, managed_user_id=uid_b, managed_member_id=m.id,
            status="active", is_primary_guardian=True,
        )
        s.add(mgmt)
        await s.flush()
        bound_mid = m.id
        await s.commit()

    # 连点 10 次删除，全部被拦（400），不应计入额度
    for _ in range(10):
        r = await client.delete(f"/api/family/member/{bound_mid}", headers=h)
        assert r.status_code == 400, r.text

    # 额度桶应仍为空
    assert len(_DELETE_RATE_BUCKET.get(str(uid), [])) == 0
    assert _peek_delete_rate_limit(uid) is True

    # 删一个可删孤儿档案，仍应成功
    orphan = await _create_member(uid, "孤儿", "父亲")
    r = await client.delete(f"/api/family/member/{orphan}", headers=h)
    assert r.status_code == 200, r.text


# ─── 权限 ───

@pytest.mark.asyncio
async def test_tc_fmv2_10_permission_denied(client: AsyncClient):
    """删除别人档案 → PERMISSION_DENIED"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    uid_a = await _make_user(pa, "A")
    uid_b = await _make_user(pb, "B")
    h_a = await _headers(client, pa)

    # B 创建一个档案
    mid_b = await _create_member(uid_b, "B的家人", "父亲")

    # A 用 A 的 token 尝试删 B 的档案
    res = await client.delete(f"/api/family/member/{mid_b}", headers=h_a)
    assert res.status_code == 403, res.text
    assert res.json()["detail"]["reason_code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_tc_fmv2_11_not_found(client: AsyncClient):
    """删除不存在 → NOT_FOUND"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    res = await client.delete("/api/family/member/999999", headers=h)
    assert res.status_code == 404, res.text
    assert res.json()["detail"]["reason_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_tc_fmv2_12_self_undeletable(client: AsyncClient):
    """本人档案不可删"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 获取本人 member_id
    async with test_session() as s:
        self_mb = (await s.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == uid,
                FamilyMember.is_self == True,  # noqa: E712
            )
        )).scalars().first()
        self_mid = self_mb.id

    res = await client.delete(f"/api/family/member/{self_mid}", headers=h)
    assert res.status_code == 400
    assert res.json()["detail"]["reason_code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_tc_fmv2_13_s5_expired_deletable(client: AsyncClient):
    """S5 已过期：列表自动展示为 S5，可删除"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "过期", "父亲")

    # 插一条 pending 但已过期
    async with test_session() as s:
        s.add(FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=uid,
            member_id=mid,
            status="pending",
            expires_at=datetime.now() - timedelta(hours=1),
            relation_type="父亲",
            nickname="过期",
        ))
        await s.commit()

    res = await client.get("/api/family/member/state/list", headers=h)
    body = res.json()
    target = next((x for x in body["items"] if x["member_id"] == mid), None)
    assert target["state"] == "S5", f"应为 S5，实际: {target}"
    assert target["can_delete"] is True

    # 删除应成功
    res2 = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res2.status_code == 200, res2.text
    assert res2.json()["data"]["reason_code"] == "OK"


@pytest.mark.asyncio
async def test_tc_fmv2_14_delete_removes_from_list(client: AsyncClient):
    """删除后 family_member.status=deleted，列表不再出现"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)
    mid = await _create_member(uid, "待删", "父亲")

    # 删除前 list 包含
    res0 = await client.get("/api/family/member/state/list", headers=h)
    assert any(x["member_id"] == mid for x in res0.json()["items"])

    # 删除
    res = await client.delete(f"/api/family/member/{mid}", headers=h)
    assert res.status_code == 200

    # 删除后 list 不再包含
    res2 = await client.get("/api/family/member/state/list", headers=h)
    assert not any(x["member_id"] == mid for x in res2.json()["items"])

    # 数据库中 status=deleted
    async with test_session() as s:
        mb = await s.get(FamilyMember, mid)
        assert mb.status == "deleted"
