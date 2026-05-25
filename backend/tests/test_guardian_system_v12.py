"""[守护人体系 PRD v1.2 2026-05-25] 自动化测试

覆盖：
1. 我守护的人列表 v1.2 直筒列表 - 含 relation_label 与 role_badge
2. 守护管理抽屉：列出某被守护人的全部守护人 + 当前用户角色
3. 主守护人转让 v1.2 流程：接收者同意（不是被守护人）
4. 被守护人上帝视角直改：set_primary / remove_guardian
5. 主守护人代付开关：开启/关闭
6. AI 外呼额度查询 / 紧急 AI 呼叫额度查询 / 会员中心配额概览
7. AI 外呼提醒列表的权限过滤（主守护人可管所有 / 普通守护人仅自己）
8. 紧急 AI 呼叫串行外呼：扣主守护人额度（v1.2 统一规则）
9. 紧急呼叫触发源管理：内置不可删 / 自定义可增删
10. 邀请记录列表（含我发起的 + 别人邀请我的）
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from app.models.models import (
    AiCallReminder,
    EmergencyCallSource,
    FamilyManagement,
    FamilyMember,
    GuardianProxyPay,
    User,
    UserRole,
)


# ─────────── 工具 ───────────


async def _make_user(phone: str, nickname: str = "用户", role: UserRole = UserRole.user) -> int:
    async with test_session() as s:
        u = User(
            phone=phone,
            password_hash=get_password_hash("p123"),
            nickname=nickname,
            role=role,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
        return uid


async def _ensure_builtin_sources():
    """测试环境下手动 seed 4 条内置触发源（生产由 schema_sync 自动注入）"""
    async with test_session() as s:
        existing = (await s.execute(select(EmergencyCallSource))).scalars().all()
        existing_codes = {e.source_code for e in existing}
        seeds = [
            ('health_data_abnormal', '健康数据异常', '心率/血压/血氧/体温异常', 1),
            ('smoke_alarm', '烟雾报警器', '火灾隐患', 2),
            ('water_alarm', '水位报警器', '漏水/水浸', 3),
            ('emergency_button', '紧急呼叫器', '一键呼救', 4),
        ]
        for code, name, desc, order in seeds:
            if code in existing_codes:
                continue
            s.add(EmergencyCallSource(
                source_code=code, source_name=name, description=desc,
                is_enabled=True, is_builtin=True, sort_order=order,
            ))
        await s.commit()


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "p123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _make_management(
    manager_phone: str,
    managed_phone: str,
    is_primary: bool = False,
    priority: int = 100,
    delta_seconds: int = 0,
) -> int:
    """构造守护关系"""
    async with test_session() as s:
        manager = (await s.execute(select(User).where(User.phone == manager_phone))).scalar_one()
        managed = (await s.execute(select(User).where(User.phone == managed_phone))).scalar_one()
        m = FamilyMember(
            user_id=managed.id,
            nickname=managed.nickname or "本人",
            relationship_type="本人",
            is_self=True,
            member_user_id=managed.id,
        )
        s.add(m)
        await s.flush()
        mgmt = FamilyManagement(
            manager_user_id=manager.id,
            managed_user_id=managed.id,
            managed_member_id=m.id,
            status="active",
            is_primary_guardian=is_primary,
            priority_order=priority,
            created_at=datetime.utcnow() + timedelta(seconds=delta_seconds),
        )
        s.add(mgmt)
        await s.flush()
        mid = mgmt.id
        await s.commit()
        return mid


# ─────────── T1: i-guard v1.2 ───────────


@pytest.mark.asyncio
async def test_v12_i_guard_returns_relation_label_and_role_badge(client: AsyncClient):
    await _make_user("13800000001", "张三")
    await _make_user("13800000002", "妈妈李梅")
    await _make_management("13800000001", "13800000002", is_primary=True, priority=0)

    headers = await _headers(client, "13800000001")
    r = await client.get("/api/guardian/v12/i-guard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["role_badge"] == "primary"
    assert item["is_primary_guardian"] is True
    assert "max_managed" in data
    assert item["proxy_pay_enabled"] is False


# ─────────── T2: 守护管理抽屉 ───────────


@pytest.mark.asyncio
async def test_v12_all_guardians_drawer(client: AsyncClient):
    await _make_user("13810000001", "妈妈")
    await _make_user("13810000002", "女儿(主)")
    await _make_user("13810000003", "弟弟")

    await _make_management("13810000002", "13810000001", is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13810000003", "13810000001", is_primary=False, priority=10, delta_seconds=10)

    # 女儿（主守护人）调用
    headers = await _headers(client, "13810000002")
    r = await client.get("/api/guardian/v12/managed/1/all-guardians", headers=headers)
    # managed_user_id 用妈妈的 user_id
    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13810000001"))).scalar_one()
        mama_uid = mama.id
    r = await client.get(f"/api/guardian/v12/managed/{mama_uid}/all-guardians", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert data["caller_role"] == "guardian"
    assert data["caller_is_primary"] is True


# ─────────── T3: v1.2 主守护人转让（接收者同意） ───────────


@pytest.mark.asyncio
async def test_v12_transfer_approved_by_receiver(client: AsyncClient):
    await _make_user("13820000001", "妈妈")
    await _make_user("13820000002", "女儿(主)")
    await _make_user("13820000003", "弟弟")

    await _make_management("13820000002", "13820000001", is_primary=True, priority=0, delta_seconds=0)
    target_mid = await _make_management("13820000003", "13820000001",
                                         is_primary=False, priority=10, delta_seconds=10)

    # 现任主守护人（女儿）发起
    h_origin = await _headers(client, "13820000002")
    r = await client.post(
        "/api/guardian/v12/transfer/initiate",
        json={"target_management_id": target_mid},
        headers=h_origin,
    )
    assert r.status_code == 200, r.text
    transfer_id = r.json()["transfer_id"]

    # v1.2: 被守护人不能同意（应返回 403）
    h_managed = await _headers(client, "13820000001")
    r = await client.post(f"/api/guardian/v12/transfer/{transfer_id}/approve", headers=h_managed)
    assert r.status_code == 403

    # v1.2: 接收者同意（成功）
    h_recv = await _headers(client, "13820000003")
    r = await client.post(f"/api/guardian/v12/transfer/{transfer_id}/approve", headers=h_recv)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


# ─────────── T4: 被守护人上帝视角直改 ───────────


@pytest.mark.asyncio
async def test_v12_owner_direct_adjust_set_primary(client: AsyncClient):
    await _make_user("13830000001", "妈妈")
    await _make_user("13830000002", "女儿(主)")
    await _make_user("13830000003", "弟弟")

    await _make_management("13830000002", "13830000001", is_primary=True, priority=0, delta_seconds=0)
    target_mid = await _make_management("13830000003", "13830000001",
                                         is_primary=False, priority=10, delta_seconds=10)

    # 妈妈（被守护人）直接把弟弟设为主
    h_owner = await _headers(client, "13830000001")
    r = await client.post(
        "/api/guardian/v12/owner/direct-adjust",
        json={"action": "set_primary", "target_management_id": target_mid},
        headers=h_owner,
    )
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "set_primary"

    # 验证：弟弟现在是主
    r = await client.get("/api/guardian/list", headers=h_owner)
    items = r.json()["items"]
    primary = next(i for i in items if i["is_primary_guardian"])
    assert primary["manager_nickname"] == "弟弟"


@pytest.mark.asyncio
async def test_v12_owner_direct_adjust_remove(client: AsyncClient):
    await _make_user("13830100001", "妈妈")
    await _make_user("13830100002", "女儿(主)")
    await _make_user("13830100003", "弟弟")

    await _make_management("13830100002", "13830100001", is_primary=True, priority=0, delta_seconds=0)
    bro_mid = await _make_management("13830100003", "13830100001",
                                      is_primary=False, priority=10, delta_seconds=10)

    h_owner = await _headers(client, "13830100001")
    r = await client.post(
        "/api/guardian/v12/owner/direct-adjust",
        json={"action": "remove_guardian", "target_management_id": bro_mid},
        headers=h_owner,
    )
    assert r.status_code == 200
    # 验证：剩 1 个守护人
    r = await client.get("/api/guardian/list", headers=h_owner)
    assert r.json()["total"] == 1


# ─────────── T5: 主守护人代付开关 ───────────


@pytest.mark.asyncio
async def test_v12_primary_guardian_proxy_pay_switch(client: AsyncClient):
    await _make_user("13840000001", "妈妈")
    await _make_user("13840000002", "女儿(主)")

    await _make_management("13840000002", "13840000001", is_primary=True, priority=0, delta_seconds=0)

    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13840000001"))).scalar_one()
        mama_uid = mama.id

    h_primary = await _headers(client, "13840000002")
    # 开启代付
    r = await client.post(
        f"/api/guardian/v12/managed/{mama_uid}/proxy-pay",
        json={"enabled": True},
        headers=h_primary,
    )
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True

    # 列表中能看到 proxy_pay_enabled=True
    r = await client.get("/api/guardian/v12/i-guard", headers=h_primary)
    item = r.json()["items"][0]
    assert item["proxy_pay_enabled"] is True

    # 关闭
    r = await client.post(
        f"/api/guardian/v12/managed/{mama_uid}/proxy-pay",
        json={"enabled": False},
        headers=h_primary,
    )
    assert r.json()["enabled"] is False


@pytest.mark.asyncio
async def test_v12_proxy_pay_only_by_primary(client: AsyncClient):
    """非主守护人不能设置代付"""
    await _make_user("13841000001", "妈妈")
    await _make_user("13841000002", "女儿(主)")
    await _make_user("13841000003", "弟弟(普通)")

    await _make_management("13841000002", "13841000001", is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13841000003", "13841000001", is_primary=False, priority=10, delta_seconds=10)

    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13841000001"))).scalar_one()
        mama_uid = mama.id

    h_normal = await _headers(client, "13841000003")
    r = await client.post(
        f"/api/guardian/v12/managed/{mama_uid}/proxy-pay",
        json={"enabled": True},
        headers=h_normal,
    )
    assert r.status_code == 403


# ─────────── T6: 配额查询 ───────────


@pytest.mark.asyncio
async def test_v12_ai_call_quota_and_emergency_quota_for_free_user(client: AsyncClient):
    await _make_user("13850000001", "免费用户")
    # 确保有 free quota 行
    async with test_session() as s:
        q = await s.get(FreeMemberQuota, 1)
        if not q:
            q = FreeMemberQuota(id=1)
            s.add(q)
        q.ai_remind_quota = 10
        q.emergency_ai_call_count = 3
        q.max_managed = 5
        await s.commit()

    h = await _headers(client, "13850000001")
    r = await client.get("/api/guardian/v12/ai-call-quota", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_paid_member"] is False
    assert data["total"] == 10
    assert data["used"] == 0
    assert data["remaining"] == 10

    r = await client.get("/api/guardian/v12/emergency-quota", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 3

    r = await client.get("/api/guardian/v12/managed-quota-summary", headers=h)
    assert r.status_code == 200
    s = r.json()
    assert s["ai_remind"]["total"] == 10
    assert s["emergency_ai_call"]["total"] == 3
    assert s["max_managed"]["total"] == 5


# ─────────── T7: AI 外呼提醒列表权限过滤 ───────────


@pytest.mark.asyncio
async def test_v12_reminders_permission_filter(client: AsyncClient):
    await _make_user("13860000001", "妈妈")
    await _make_user("13860000002", "女儿(主)")
    await _make_user("13860000003", "弟弟(普通)")
    await _make_management("13860000002", "13860000001", is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13860000003", "13860000001", is_primary=False, priority=10, delta_seconds=10)

    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13860000001"))).scalar_one()
        daughter = (await s.execute(select(User).where(User.phone == "13860000002"))).scalar_one()
        brother = (await s.execute(select(User).where(User.phone == "13860000003"))).scalar_one()
        mama_uid = mama.id
        # 各自创建提醒
        s.add(AiCallReminder(setter_user_id=mama.id, target_user_id=mama.id, title="妈妈自己设置"))
        s.add(AiCallReminder(setter_user_id=daughter.id, target_user_id=mama.id, title="女儿设置"))
        s.add(AiCallReminder(setter_user_id=brother.id, target_user_id=mama.id, title="弟弟设置"))
        await s.commit()

    # 弟弟（普通守护人）查询：只有自己的 can_edit=True
    h_bro = await _headers(client, "13860000003")
    r = await client.get(f"/api/guardian/v12/reminders/{mama_uid}", headers=h_bro)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    edits = {it["title"]: it["can_edit"] for it in data["items"]}
    assert edits["弟弟设置"] is True
    assert edits["女儿设置"] is False
    assert edits["妈妈自己设置"] is False

    # 女儿（主守护人）查询：全部 can_edit=True
    h_dau = await _headers(client, "13860000002")
    r = await client.get(f"/api/guardian/v12/reminders/{mama_uid}", headers=h_dau)
    edits = {it["title"]: it["can_edit"] for it in r.json()["items"]}
    assert all(edits.values())


# ─────────── T8: 紧急 AI 呼叫扣主守护人 ───────────


@pytest.mark.asyncio
async def test_v12_emergency_call_charges_primary_guardian(client: AsyncClient):
    await _ensure_builtin_sources()
    await _make_user("13870000001", "妈妈")
    await _make_user("13870000002", "女儿(主)")
    await _make_user("13870000003", "弟弟")
    await _make_management("13870000002", "13870000001", is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13870000003", "13870000001", is_primary=False, priority=10, delta_seconds=10)

    # 给免费免费配额加 emergency_ai_call_count=5
    async with test_session() as s:
        q = await s.get(FreeMemberQuota, 1)
        if not q:
            q = FreeMemberQuota(id=1)
            s.add(q)
        q.emergency_ai_call_count = 5
        await s.commit()
        mama = (await s.execute(select(User).where(User.phone == "13870000001"))).scalar_one()
        mama_uid = mama.id
        daughter = (await s.execute(select(User).where(User.phone == "13870000002"))).scalar_one()
        daughter_uid = daughter.id

    h = await _headers(client, "13870000002")
    r = await client.post(
        "/api/guardian/v12/emergency/simulate-serial-call",
        json={"managed_user_id": mama_uid, "source_code": "smoke_alarm"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fallback_to_push_sms"] is False
    assert data["charged_user_id"] == daughter_uid  # 扣主守护人
    assert data["charged_count"] == 1
    assert len(data["call_plan"]) == 2


# ─────────── T9: 紧急呼叫触发源管理 ───────────


async def _admin_headers(client: AsyncClient, phone: str) -> dict:
    """admin 用户走 /api/admin/login 路由"""
    res = await client.post(
        "/api/admin/login", json={"phone": phone, "password": "p123"}
    )
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}", "Client-Type": "admin-web"}


@pytest.mark.asyncio
async def test_v12_emergency_sources_seed_and_admin_crud(client: AsyncClient):
    await _ensure_builtin_sources()
    # 准备 admin 用户
    await _make_user("13880000001", "admin1", role=UserRole.admin)
    h_admin = await _admin_headers(client, "13880000001")

    # 列表（应该有 4 条内置）
    r = await client.get("/api/admin/emergency-sources", headers=h_admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    codes = {i["source_code"] for i in items}
    assert "health_data_abnormal" in codes
    assert "smoke_alarm" in codes
    assert "water_alarm" in codes
    assert "emergency_button" in codes

    # 新增自定义
    r = await client.post(
        "/api/admin/emergency-sources",
        json={
            "source_code": "gas_alarm",
            "source_name": "燃气报警器",
            "description": "燃气泄漏",
            "is_enabled": True,
            "sort_order": 5,
        },
        headers=h_admin,
    )
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]

    # 不能删内置
    builtin = next(i for i in items if i["source_code"] == "smoke_alarm")
    r = await client.delete(f"/api/admin/emergency-sources/{builtin['id']}", headers=h_admin)
    assert r.status_code == 400

    # 可删自定义
    r = await client.delete(f"/api/admin/emergency-sources/{new_id}", headers=h_admin)
    assert r.status_code == 200


# ─────────── T10: 邀请记录 v1.2 ───────────


@pytest.mark.asyncio
async def test_v12_invitation_records_combined(client: AsyncClient):
    await _make_user("13890000001", "张三")
    h = await _headers(client, "13890000001")
    r = await client.get("/api/guardian/v12/invitations/records", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert "sent_count" in data
    assert "received_count" in data


# ─────────── T11: max_managed 字段返回 ───────────


@pytest.mark.asyncio
async def test_v12_membership_plan_has_max_managed_field(client: AsyncClient):
    await _make_user("13891100001", "admin2", role=UserRole.admin)
    h_admin = await _admin_headers(client, "13891100001")

    # 创建一个套餐
    r = await client.post(
        "/api/admin/membership/plans",
        json={
            "plan_code": "test_v12_plan",
            "name": "测试 v1.2 套餐",
            "price_monthly": 10,
            "ai_remind_quota": 100,
            "emergency_ai_call_count": 50,
            "max_guardians": 10,
            "max_managed": 20,
            "point_multiplier": 2.0,
            "discount_rate": 0.9,
        },
        headers=h_admin,
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["max_managed"] == 20
    assert p["emergency_ai_call_count"] == 50
    assert p["point_multiplier"] == 2.0


# ─────────── T12: 代付开启后被守护人查询提醒抽屉看到代付人 ───────────


@pytest.mark.asyncio
async def test_v12_owner_sees_proxy_pay_payer(client: AsyncClient):
    await _make_user("13892200001", "妈妈")
    await _make_user("13892200002", "女儿(主)")
    await _make_management("13892200002", "13892200001", is_primary=True, priority=0, delta_seconds=0)

    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13892200001"))).scalar_one()
        daughter = (await s.execute(select(User).where(User.phone == "13892200002"))).scalar_one()
        s.add(GuardianProxyPay(
            primary_guardian_user_id=daughter.id,
            managed_user_id=mama.id,
            enabled=True,
        ))
        await s.commit()
        mama_uid = mama.id

    h_owner = await _headers(client, "13892200001")
    r = await client.get(f"/api/guardian/v12/reminders/{mama_uid}", headers=h_owner)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["caller_is_owner"] is True
    assert data["proxy_pay_payer_nickname"] == "女儿(主)"
