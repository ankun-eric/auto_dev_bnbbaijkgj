"""三端登录接口图形验证码端到端集成测试

PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）

覆盖：
- /api/captcha/image 返回结构 + base64 PNG
- admin 登录：缺验证码 → 40103；错验证码 → 40102；过期/未知 → 40101；正确 → 200
- 验证码错误**不会**升高失败计数（不会被锁）
- 账号/密码错 5 次 → 第 6 次返回 40129
"""
import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.models import User, UserRole
from app.services import captcha_service as cs


@pytest.mark.asyncio
async def test_get_captcha_image(client: AsyncClient):
    r = await client.get("/api/captcha/image")
    assert r.status_code == 200
    body = r.json()
    assert "captcha_id" in body and len(body["captcha_id"]) > 8
    assert body["image_base64"].startswith("data:image/png;base64,")
    assert body.get("expire_seconds") == 300
    # no-store 头存在
    assert "no-store" in r.headers.get("cache-control", "").lower()


async def _get_captcha(client: AsyncClient) -> tuple[str, str]:
    """获取验证码；测试场景下绕过 IP 限流（清空限流 + 重试一次）"""
    cs._store._issue_rate.clear()
    r = await client.get("/api/captcha/image")
    if r.status_code == 429:
        cs._store._issue_rate.clear()
        r = await client.get("/api/captcha/image")
    body = r.json()
    cid = body["captcha_id"]
    code = cs._store._captcha[cid].code
    return cid, code


async def _create_admin(db_session: AsyncSession, phone="13800001234", password="admin@2026"):
    db_session.add(User(
        phone=phone,
        password_hash=get_password_hash(password),
        nickname="测试管理员",
        role=UserRole.admin,
    ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_admin_login_missing_captcha(client: AsyncClient, db_session: AsyncSession):
    """传了 captcha_id 但 captcha_code 为空，应返回 40103 请输入验证码。
    （注意：后端在 PYTEST 环境下若两个验证码字段都为空则走豁免路径，本测试显式传一个 id 触发校验）"""
    await _create_admin(db_session)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "admin@2026",
        "captcha_id": "anything",
        "captcha_code": "",
    })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == 40103
    assert "请输入验证码" in detail["msg"]


@pytest.mark.asyncio
async def test_admin_login_wrong_captcha(client: AsyncClient, db_session: AsyncSession):
    await _create_admin(db_session)
    cid, _ = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "admin@2026",
        "captcha_id": cid,
        "captcha_code": "ZZZZ",
    })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == 40102


@pytest.mark.asyncio
async def test_admin_login_expired_captcha(client: AsyncClient, db_session: AsyncSession):
    await _create_admin(db_session)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "admin@2026",
        "captcha_id": "non-exist-id",
        "captcha_code": "ABCD",
    })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == 40101


@pytest.mark.asyncio
async def test_admin_login_success_with_valid_captcha(client: AsyncClient, db_session: AsyncSession):
    await _create_admin(db_session)
    cid, code = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "admin@2026",
        "captcha_id": cid,
        "captcha_code": code,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("token") or body.get("access_token")


@pytest.mark.asyncio
async def test_admin_login_captcha_case_insensitive(client: AsyncClient, db_session: AsyncSession):
    await _create_admin(db_session)
    cid, code = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "admin@2026",
        "captcha_id": cid,
        "captcha_code": code.lower(),
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_admin_login_wrong_password_returns_40121(client: AsyncClient, db_session: AsyncSession):
    await _create_admin(db_session)
    # 清下 风控状态以保证测试干净
    cs.clear_login_failure(None, "13800001234")
    cid, code = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800001234",
        "password": "wrong-pass",
        "captcha_id": cid,
        "captcha_code": code,
    })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == 40121


@pytest.mark.asyncio
async def test_captcha_error_does_not_count_to_lockout(client: AsyncClient, db_session: AsyncSession):
    """验证码错误不应消耗风控失败次数：连续 10 次错验证码后，正确账密仍可登录"""
    await _create_admin(db_session, phone="13800002000")
    cs.clear_login_failure(None, "13800002000")
    for _ in range(10):
        cid, _ = await _get_captcha(client)
        r = await client.post("/api/admin/login", json={
            "phone": "13800002000",
            "password": "admin@2026",
            "captcha_id": cid,
            "captcha_code": "ZZZZ",
        })
        assert r.json()["detail"]["code"] in (40101, 40102)
    # 现在用正确的应仍然能登录
    cid, code = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800002000",
        "password": "admin@2026",
        "captcha_id": cid,
        "captcha_code": code,
    })
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_password_error_lock_after_5_fails(client: AsyncClient, db_session: AsyncSession):
    """账密错误 5 次 → 第 6 次返回 40129 锁定"""
    await _create_admin(db_session, phone="13800003000")
    cs.clear_login_failure(None, "13800003000")
    for i in range(5):
        cid, code = await _get_captcha(client)
        r = await client.post("/api/admin/login", json={
            "phone": "13800003000",
            "password": "wrong",
            "captcha_id": cid,
            "captcha_code": code,
        })
        assert r.json()["detail"]["code"] == 40121, f"round {i}: {r.text}"
    # 第 6 次：密码也对，但应被锁
    cid, code = await _get_captcha(client)
    r = await client.post("/api/admin/login", json={
        "phone": "13800003000",
        "password": "admin@2026",
        "captcha_id": cid,
        "captcha_code": code,
    })
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == 40129
    # 解锁
    cs.clear_login_failure(None, "13800003000")
