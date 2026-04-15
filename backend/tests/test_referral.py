"""Tests for user_no generation, referral binding, share links, landing page, and admin referral management."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.models import User, UserRole, VerificationCode


# ── helpers ──


async def register_user(client: AsyncClient, phone: str, password: str = "test1234", nickname: str | None = None, referrer_no: str | None = None) -> dict:
    payload: dict = {"phone": phone, "password": password}
    if nickname:
        payload["nickname"] = nickname
    if referrer_no:
        payload["referrer_no"] = referrer_no
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def get_user_token(client: AsyncClient, phone: str, password: str = "test1234") -> str:
    resp = await client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def create_superadmin_headers(client: AsyncClient, db_session: AsyncSession, phone: str = "13800000099") -> dict:
    admin = User(
        phone=phone,
        password_hash=get_password_hash("admin1234"),
        nickname="超级管理员",
        role=UserRole.admin,
        is_superuser=True,
    )
    db_session.add(admin)
    await db_session.commit()
    resp = await client.post("/api/admin/login", json={"phone": phone, "password": "admin1234"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def create_normal_admin_headers(client: AsyncClient, db_session: AsyncSession, phone: str = "13800000088") -> dict:
    admin = User(
        phone=phone,
        password_hash=get_password_hash("admin1234"),
        nickname="普通管理员",
        role=UserRole.admin,
        is_superuser=False,
    )
    db_session.add(admin)
    await db_session.commit()
    resp = await client.post("/api/admin/login", json={"phone": phone, "password": "admin1234"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ════════════════════════════════════════════
# 1. 用户编号生成
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_register_generates_8_digit_user_no(client: AsyncClient):
    """TC-001: 新用户注册后自动生成8位 user_no"""
    data = await register_user(client, "13700010001", nickname="编号用户")
    user_no = data["user"]["user_no"]
    assert user_no is not None
    assert len(user_no) == 8
    assert user_no.isdigit()


@pytest.mark.asyncio
async def test_tc002_sms_login_new_user_generates_user_no(client: AsyncClient, latest_sms_code):
    """TC-002: SMS 登录新用户自动生成 user_no"""
    await client.post("/api/auth/sms-code", json={"phone": "13700010002", "type": "login"})
    code = await latest_sms_code("13700010002")
    resp = await client.post("/api/auth/sms-login", json={"phone": "13700010002", "code": code})
    assert resp.status_code == 200
    user_no = resp.json()["user"]["user_no"]
    assert user_no is not None
    assert len(user_no) == 8
    assert user_no.isdigit()


@pytest.mark.asyncio
async def test_tc003_user_no_globally_unique(client: AsyncClient):
    """TC-003: user_no 全局唯一（多次注册不重复）"""
    user_nos = set()
    for i in range(5):
        phone = f"1370001{i:04d}"
        data = await register_user(client, phone)
        user_nos.add(data["user"]["user_no"])
    assert len(user_nos) == 5


# ════════════════════════════════════════════
# 2. 推荐人绑定
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc004_register_with_valid_referrer_no(client: AsyncClient):
    """TC-004: 注册时携带有效 referrer_no 成功绑定"""
    referrer_data = await register_user(client, "13700020001", nickname="推荐人")
    referrer_no = referrer_data["user"]["user_no"]

    new_user_data = await register_user(client, "13700020002", nickname="被推荐人", referrer_no=referrer_no)
    assert new_user_data["user"]["referrer_no"] == referrer_no


@pytest.mark.asyncio
async def test_tc005_register_with_invalid_referrer_no_silent_fail(client: AsyncClient):
    """TC-005: 注册时携带无效 referrer_no 静默失败（不阻断注册）"""
    data = await register_user(client, "13700020003", nickname="无效推荐码", referrer_no="99999999")
    assert data["user"]["referrer_no"] is None
    assert "access_token" in data


@pytest.mark.asyncio
async def test_tc006_register_without_referrer_no(client: AsyncClient):
    """TC-006: 注册时不携带 referrer_no 正常注册"""
    data = await register_user(client, "13700020004", nickname="无推荐人")
    assert data["user"]["referrer_no"] is None
    assert "access_token" in data


@pytest.mark.asyncio
async def test_tc007_self_referral_not_allowed(client: AsyncClient, db_session: AsyncSession):
    """TC-007: 不允许自推荐 — 注册后绑定自己的 user_no 作为推荐人应被忽略"""
    first = await register_user(client, "13700020005", nickname="自推荐A")
    own_user_no = first["user"]["user_no"]

    second = await register_user(client, "13700020006", nickname="自推荐B", referrer_no=own_user_no)
    assert second["user"]["referrer_no"] == own_user_no  # different user, should work

    # For true self-referral: use admin PUT endpoint
    headers = await create_superadmin_headers(client, db_session, phone="13700020099")
    user_id = first["user"]["id"]
    resp = await client.put(f"/api/admin/users/{user_id}/referrer", json={"referrer_no": own_user_no}, headers=headers)
    assert resp.status_code == 400
    assert "自推荐" in resp.json()["detail"]


# ════════════════════════════════════════════
# 3. GET /api/auth/me
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc008_me_returns_user_no_and_referrer_no(client: AsyncClient):
    """TC-008: GET /api/auth/me 返回 user_no 和 referrer_no"""
    referrer_data = await register_user(client, "13700030001", nickname="推荐人ME")
    referrer_no = referrer_data["user"]["user_no"]

    new_data = await register_user(client, "13700030002", nickname="被推荐ME", referrer_no=referrer_no)
    token = await get_user_token(client, "13700030002")

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["user_no"] is not None
    assert len(me["user_no"]) == 8
    assert me["referrer_no"] == referrer_no


# ════════════════════════════════════════════
# 4. GET /api/users/share-link
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc009_share_link_success(client: AsyncClient):
    """TC-009: 已登录用户获取分享链接成功"""
    data = await register_user(client, "13700040001", nickname="分享用户")
    token = await get_user_token(client, "13700040001")
    user_no = data["user"]["user_no"]

    resp = await client.get("/api/users/share-link", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert "share_link" in body
    assert user_no in body["share_link"]
    assert body["user_no"] == user_no


@pytest.mark.asyncio
async def test_tc010_share_link_unauthorized(client: AsyncClient):
    """TC-010: 未登录用户返回401"""
    resp = await client.get("/api/users/share-link")
    assert resp.status_code == 401


# ════════════════════════════════════════════
# 5. GET /api/landing
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_landing_page_public(client: AsyncClient):
    """TC-011: 公开接口返回落地页数据"""
    resp = await client.get("/api/landing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["brand_name"] == "宾尼小康"
    assert body["tagline"] == "AI智能健康管家"
    assert isinstance(body["features"], list)
    assert len(body["features"]) > 0


# ════════════════════════════════════════════
# 6. GET /api/admin/users
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc012_admin_users_returns_referral_fields(client: AsyncClient, db_session: AsyncSession):
    """TC-012: 管理员用户列表返回 user_no/referrer_no/referrer_nickname"""
    referrer_data = await register_user(client, "13700060001", nickname="推荐人Admin")
    referrer_no = referrer_data["user"]["user_no"]
    await register_user(client, "13700060002", nickname="被推荐Admin", referrer_no=referrer_no)

    headers = await create_superadmin_headers(client, db_session, phone="13700060099")
    resp = await client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2

    referred_user = next((u for u in items if u["phone"] == "13700060002"), None)
    assert referred_user is not None
    assert referred_user["user_no"] is not None
    assert referred_user["referrer_no"] == referrer_no
    assert referred_user["referrer_nickname"] == "推荐人Admin"


@pytest.mark.asyncio
async def test_tc013_admin_users_keyword_search_by_user_no(client: AsyncClient, db_session: AsyncSession):
    """TC-013: keyword 搜索支持 user_no"""
    data = await register_user(client, "13700060003", nickname="搜索用户")
    user_no = data["user"]["user_no"]

    headers = await create_superadmin_headers(client, db_session, phone="13700060098")
    resp = await client.get(f"/api/admin/users?keyword={user_no}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(u["user_no"] == user_no for u in items)


# ════════════════════════════════════════════
# 7. PUT /api/admin/users/{user_id}/referrer
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc014_superadmin_update_referrer_success(client: AsyncClient, db_session: AsyncSession):
    """TC-014: 超级管理员修改推荐人成功"""
    user_data = await register_user(client, "13700070001", nickname="待修改用户")
    referrer_data = await register_user(client, "13700070002", nickname="新推荐人")

    headers = await create_superadmin_headers(client, db_session, phone="13700070099")
    resp = await client.put(
        f"/api/admin/users/{user_data['user']['id']}/referrer",
        json={"referrer_no": referrer_data["user"]["user_no"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "已更新" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc015_non_superadmin_update_referrer_403(client: AsyncClient, db_session: AsyncSession):
    """TC-015: 非超级管理员修改推荐人返回403"""
    user_data = await register_user(client, "13700070003", nickname="用户15")
    referrer_data = await register_user(client, "13700070004", nickname="推荐人15")

    headers = await create_normal_admin_headers(client, db_session, phone="13700070088")
    resp = await client.put(
        f"/api/admin/users/{user_data['user']['id']}/referrer",
        json={"referrer_no": referrer_data["user"]["user_no"]},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tc016_self_referral_returns_400(client: AsyncClient, db_session: AsyncSession):
    """TC-016: 自推荐返回400"""
    user_data = await register_user(client, "13700070005", nickname="自推荐16")
    headers = await create_superadmin_headers(client, db_session, phone="13700070097")

    resp = await client.put(
        f"/api/admin/users/{user_data['user']['id']}/referrer",
        json={"referrer_no": user_data["user"]["user_no"]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "自推荐" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tc017_referrer_not_found_returns_400(client: AsyncClient, db_session: AsyncSession):
    """TC-017: 推荐人不存在返回400"""
    user_data = await register_user(client, "13700070006", nickname="用户17")
    headers = await create_superadmin_headers(client, db_session, phone="13700070096")

    resp = await client.put(
        f"/api/admin/users/{user_data['user']['id']}/referrer",
        json={"referrer_no": "00000000"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


# ════════════════════════════════════════════
# 8. GET /api/admin/referral/stats
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc018_admin_referral_stats_success(client: AsyncClient, db_session: AsyncSession):
    """TC-018: 管理员获取推荐统计数据成功"""
    referrer_data = await register_user(client, "13700080001", nickname="统计推荐人")
    referrer_no = referrer_data["user"]["user_no"]
    await register_user(client, "13700080002", nickname="统计被推荐1", referrer_no=referrer_no)
    await register_user(client, "13700080003", nickname="统计被推荐2", referrer_no=referrer_no)

    headers = await create_superadmin_headers(client, db_session, phone="13700080099")
    resp = await client.get("/api/admin/referral/stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_referrals" in body
    assert body["total_referrals"] >= 2
    assert "today_referrals" in body
    assert "month_referrals" in body
    assert "ranking" in body
    assert isinstance(body["ranking"], list)


@pytest.mark.asyncio
async def test_tc019_non_admin_referral_stats_403(client: AsyncClient):
    """TC-019: 非管理员获取推荐统计返回403"""
    data = await register_user(client, "13700080010", nickname="普通用户19")
    token = await get_user_token(client, "13700080010")

    resp = await client.get("/api/admin/referral/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
