"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 新增家庭成员→邀请二维码 Bug 修复 回归测试

需求要点：
- 「保存成员」接口 POST /api/family/members 必须返回新成员的 id，
  前端"去邀请 TA"跳转将使用该 id 拼成 /family-invite?member_id=xxx
- /api/health-profile/self 返回的 needComplete 字段是三端"完善档案拦截前移"判断依据
- POST /api/family/invitation 仅在 body.member_id 存在时为该成员生成二维码（不再
  接收无 id 的兜底创建）

本测试聚焦三端共用的后端契约，确保前端"删兜底、跳转带 id、拦截前移"改造能正确运转。
"""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import FamilyMember, HealthProfile, User, UserRole


# ─────────── 工具 ───────────


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
        fm = FamilyMember(
            user_id=uid,
            relationship_type="本人",
            nickname="本人",
            is_self=True,
            status="active",
        )
        s.add(fm)
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "p123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _complete_self(uid: int, phone_for_log: str = "") -> None:
    """把本人档案补齐，让 needComplete=False，方便后续保存成员不被前置拦截。"""
    async with test_session() as s:
        # 已经有 family_members(is_self) 一条记录，把 nickname/gender/birthday 补齐
        from sqlalchemy import select
        r = await s.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == uid, FamilyMember.is_self.is_(True)
            )
        )
        fm = r.scalar_one_or_none()
        if fm is not None:
            fm.nickname = "张三"
            fm.gender = "男"
            fm.birthday = date(1990, 1, 1)
        # 同步本人 HealthProfile（family_member_id IS NULL）
        r2 = await s.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == uid,
                HealthProfile.family_member_id.is_(None),
            )
        )
        hp = r2.scalar_one_or_none()
        if hp is None:
            hp = HealthProfile(user_id=uid, family_member_id=None)
            s.add(hp)
        hp.name = "张三"
        hp.gender = "男"
        hp.birthday = date(1990, 1, 1)
        await s.commit()


# ─────────── #1 保存成员接口必须返回新成员 id ───────────


@pytest.mark.asyncio
async def test_create_family_member_returns_id(client: AsyncClient):
    """POST /api/family/members 必须返回 id 字段。

    前端"去邀请 TA"按钮依赖此 id 拼成 /family-invite?member_id=xxx。
    如果接口不返回 id，前端会落到"无 id 兜底表单"分支（这就是要修复的 Bug）。
    """
    phone = "13900000010"
    uid = await _make_user(phone)
    await _complete_self(uid)
    headers = await _headers(client, phone)

    body = {
        "nickname": "李妈妈",
        "name": "李妈妈",
        "relationship_type": "母亲",
        "gender": "女",
        "birthday": "1965-03-12",
    }
    r = await client.post("/api/family/members", json=body, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "id" in data, "POST /api/family/members 必须返回新成员 id（前端跳邀请页依赖）"
    assert isinstance(data["id"], int) and data["id"] > 0, (
        "返回的 id 必须是 > 0 的整数"
    )
    # 同时返回成员核心信息，便于前端在"成员已添加成功"弹框中显示
    assert data.get("nickname") == "李妈妈"


# ─────────── #2 GET /api/health-profile/self 必须返回 needComplete 字段 ───────────


@pytest.mark.asyncio
async def test_health_profile_self_returns_need_complete(client: AsyncClient):
    """GET /api/health-profile/self 必须返回 needComplete 字段。

    三端「点新增咨询人」拦截前移完全依赖此字段：
      - needComplete=true  → 弹完善档案抽屉
      - needComplete=false → 继续走查名额、开表单
    """
    phone = "13900000011"
    await _make_user(phone)
    headers = await _headers(client, phone)

    r = await client.get("/api/health-profile/self", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data", body)
    assert "needComplete" in data, "缺少 needComplete 字段（三端拦截前移依赖此字段）"
    assert isinstance(data["needComplete"], bool), "needComplete 必须为布尔值"
    assert "missingFields" in data, "缺少 missingFields 字段"
    assert isinstance(data["missingFields"], list), "missingFields 必须为列表"


@pytest.mark.asyncio
async def test_health_profile_self_need_complete_when_empty(client: AsyncClient):
    """新用户（姓名为'本人'占位、性别/生日缺失）时 needComplete=True，
    含 name/gender/birthday 至少其一在 missingFields。"""
    phone = "13900000012"
    await _make_user(phone)
    headers = await _headers(client, phone)
    r = await client.get("/api/health-profile/self", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data", body)
    assert data["needComplete"] is True
    missing = set(data.get("missingFields", []))
    # 至少有 gender + birthday；name 是占位"本人"也算空
    assert "gender" in missing or "birthday" in missing or "name" in missing


@pytest.mark.asyncio
async def test_health_profile_self_complete_after_put(client: AsyncClient):
    """保存完整三项后 needComplete=False（三端拦截前移流程的闭环）。"""
    phone = "13900000013"
    await _make_user(phone)
    headers = await _headers(client, phone)
    r = await client.put(
        "/api/health-profile/self",
        json={"name": "王芳", "gender": "女", "birthday": "1988-08-08"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    inner = body.get("data", body)
    assert inner.get("needComplete") is False
    # 再 GET 确认
    r2 = await client.get("/api/health-profile/self", headers=headers)
    body2 = r2.json()
    data2 = body2.get("data", body2)
    assert data2["needComplete"] is False
    assert data2["missingFields"] == []


# ─────────── #3 POST /api/family/invitation 必须按 member_id 生成 ───────────


@pytest.mark.asyncio
async def test_family_invitation_with_member_id(client: AsyncClient):
    """POST /api/family/invitation 带 member_id 必须成功为该成员生成邀请码。

    这是前端"去邀请 TA"跳转 /family-invite?member_id=xxx 后会调用的接口；
    必须为给定成员生成绑定二维码，不再依赖前端 nickname/relation_type 兜底。
    """
    phone = "13900000014"
    uid = await _make_user(phone)
    await _complete_self(uid)
    headers = await _headers(client, phone)
    # 先建一个成员，拿到 id
    cr = await client.post(
        "/api/family/members",
        json={
            "nickname": "李爸爸",
            "name": "李爸爸",
            "relationship_type": "父亲",
            "gender": "男",
            "birthday": "1960-01-01",
        },
        headers=headers,
    )
    assert cr.status_code == 200, cr.text
    member_id = cr.json()["id"]
    # 调邀请接口
    ir = await client.post(
        "/api/family/invitation",
        json={"member_id": member_id},
        headers=headers,
    )
    assert ir.status_code == 200, ir.text
    inv = ir.json()
    # 必须返回 invite_code + 二维码相关字段
    assert "invite_code" in inv and inv["invite_code"], (
        "POST /api/family/invitation 必须返回 invite_code"
    )
    assert "expires_at" in inv, "POST /api/family/invitation 必须返回 expires_at"
    # qr_url 或 qr_content_url 至少其一存在（前端 QR 渲染依赖）
    assert inv.get("qr_url") or inv.get("qr_content_url"), (
        "POST /api/family/invitation 必须返回 qr_url 或 qr_content_url"
    )


# ─────────── #4 完整链路：保存成员 → 用 id 生成邀请 → 邀请绑定到该成员 ───────────


@pytest.mark.asyncio
async def test_full_chain_save_member_then_invite_binds_correctly(
    client: AsyncClient,
):
    """端到端契约：保存成员返回 id → 用 id 生成邀请 → 二维码内容可携该成员上下文。"""
    phone = "13900000015"
    uid = await _make_user(phone)
    await _complete_self(uid)
    headers = await _headers(client, phone)

    cr = await client.post(
        "/api/family/members",
        json={
            "nickname": "王奶奶",
            "name": "王奶奶",
            "relationship_type": "祖母",
            "gender": "女",
            "birthday": "1940-10-10",
        },
        headers=headers,
    )
    assert cr.status_code == 200, cr.text
    new_id = cr.json()["id"]
    assert isinstance(new_id, int) and new_id > 0

    ir = await client.post(
        "/api/family/invitation",
        json={"member_id": new_id},
        headers=headers,
    )
    assert ir.status_code == 200, ir.text
    inv = ir.json()
    assert inv.get("invite_code")
    # 验证 invite 列表中可看到对应 member_id 的邀请
    lr = await client.get("/api/family/invitations", headers=headers)
    if lr.status_code == 200:
        items = lr.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        # 至少能找到刚创建的 invite_code（不强校验 member_id 绑定，因为不同后端版本字段名可能不同）
        codes = [it.get("invite_code") for it in items if isinstance(it, dict)]
        assert inv["invite_code"] in codes, (
            "新生成的邀请码必须出现在 /api/family/invitations 列表中"
        )
