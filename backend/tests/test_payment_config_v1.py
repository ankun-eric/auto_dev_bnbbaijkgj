"""[支付配置 PRD v1.0] 自动化测试

覆盖：
1. 启动后预置 4 条通道，is_enabled 全 0
2. GET 列表，敏感字段掩码
3. PUT 缺字段时 is_complete=0
4. PUT 完整字段后 is_complete=1
5. 未完整 PATCH toggle enabled=true → 400
6. 完整 PATCH toggle enabled=true → 成功
7. AES-256-GCM 加解密往返一致
8. /api/pay/available-methods?platform=app 返回顺序固定 微信→支付宝
9. /api/admin/payment-channels/{code}/default-notify-url 返回正确 URL
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import insert, select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import PaymentChannel, User, UserRole
from app.utils.crypto import (
    decrypt_value,
    encrypt_value,
    is_encrypted,
    mask_value,
)


# 与 backend/app/api/payment_config.py / schema_sync 保持一致的 4 条种子
DEFAULT_SEEDS = [
    ("wechat_miniprogram", "微信小程序支付", "微信支付", "miniprogram", "wechat", 10),
    ("wechat_app", "微信APP支付", "微信支付", "app", "wechat", 10),
    ("alipay_h5", "支付宝H5支付", "支付宝", "h5", "alipay", 10),
    ("alipay_app", "支付宝APP支付", "支付宝", "app", "alipay", 20),
]


@pytest_asyncio.fixture(autouse=True)
async def _seed_channels():
    """每个测试前确保 4 条种子存在（schema_sync 不会在 conftest 的 create_all 后自动插入）。"""
    async with test_session() as session:
        for code, name, disp, platform, provider, sort_order in DEFAULT_SEEDS:
            res = await session.execute(
                select(PaymentChannel).where(PaymentChannel.channel_code == code)
            )
            if res.scalar_one_or_none() is None:
                session.add(PaymentChannel(
                    channel_code=code, channel_name=name, display_name=disp,
                    platform=platform, provider=provider,
                    is_enabled=False, is_complete=False, sort_order=sort_order,
                    config_json={},
                ))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient):
    async with test_session() as session:
        session.add(User(
            phone="13800000088",
            password_hash=get_password_hash("admin123"),
            nickname="支付配置管理员",
            role=UserRole.admin,
        ))
        await session.commit()
    response = await client.post("/api/admin/login", json={
        "phone": "13800000088",
        "password": "admin123",
    })
    body = response.json()
    return body.get("token") or body.get("access_token")


@pytest_asyncio.fixture
async def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ────────────────────────── 用例 1 ──────────────────────────


@pytest.mark.asyncio
async def test_seed_four_channels_disabled(client: AsyncClient, admin_headers):
    """1. 启动后存在 4 条预置通道，is_enabled 全 0。"""
    res = await client.get("/api/admin/payment-channels", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 4
    codes = {x["channel_code"] for x in data}
    assert codes == {"wechat_miniprogram", "wechat_app", "alipay_h5", "alipay_app"}
    assert all(x["is_enabled"] is False for x in data)
    assert all(x["is_complete"] is False for x in data)


# ────────────────────────── 用例 2 ──────────────────────────


@pytest.mark.asyncio
async def test_list_masks_sensitive_fields(client: AsyncClient, admin_headers):
    """2. GET 列表/详情时敏感字段返回掩码（****+末4位 或 全 ****）。"""
    # 先把 wechat_miniprogram 配齐
    payload = {
        "config": {
            "appid": "wxabcdef1234567890",
            "mch_id": "1234567890",
            "api_v3_key": "ThisIsApiV3SecretKey32CharsLong!!",
            "cert_serial_no": "ABCDEF0123456789",
            "private_key": "-----BEGIN PRIVATE KEY-----\nfakekeycontent==\n-----END PRIVATE KEY-----",
        }
    }
    r1 = await client.put("/api/admin/payment-channels/wechat_miniprogram",
                          headers=admin_headers, json=payload)
    assert r1.status_code == 200, r1.text

    r2 = await client.get("/api/admin/payment-channels/wechat_miniprogram",
                          headers=admin_headers)
    assert r2.status_code == 200
    data = r2.json()
    masked = data["config_masked"]
    # 敏感字段应是 ****xxxx 形式
    for k in ("api_v3_key", "private_key"):
        assert masked[k].startswith("****") and len(masked[k]) <= 8, masked[k]
    # 非敏感字段也尾 4 位掩码
    assert masked["appid"].startswith("****") and masked["appid"].endswith("7890"), masked["appid"]
    assert masked["mch_id"].endswith("7890")


# ────────────────────────── 用例 3 ──────────────────────────


@pytest.mark.asyncio
async def test_put_missing_fields_is_incomplete(client: AsyncClient, admin_headers):
    """3. 缺字段时 PUT 返回 200，但 is_complete=0。"""
    # 仅传 appid，缺 mch_id / api_v3_key 等
    res = await client.put(
        "/api/admin/payment-channels/wechat_app",
        headers=admin_headers,
        json={"config": {"app_id": "wx1234"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["is_complete"] is False
    assert body["is_enabled"] is False  # 未完整 → 强制禁用


# ────────────────────────── 用例 4 ──────────────────────────


@pytest.mark.asyncio
async def test_put_complete_fields_is_complete(client: AsyncClient, admin_headers):
    """4. 字段齐全时 is_complete=1。"""
    payload = {
        "config": {
            "app_id": "wxapp1234567890",
            "mch_id": "1900000000",
            "api_v3_key": "AnotherTestApiV3Key32CharsXXXX!!",
            "cert_serial_no": "1A2B3C4D5E6F",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEv\n-----END PRIVATE KEY-----",
        }
    }
    res = await client.put("/api/admin/payment-channels/wechat_app",
                           headers=admin_headers, json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["is_complete"] is True


# ────────────────────────── 用例 5 ──────────────────────────


@pytest.mark.asyncio
async def test_toggle_enable_when_incomplete_rejects(client: AsyncClient, admin_headers):
    """5. 未配置完整时启用通道 → 400。"""
    res = await client.patch(
        "/api/admin/payment-channels/alipay_h5/toggle",
        headers=admin_headers, json={"enabled": True},
    )
    assert res.status_code == 400


# ────────────────────────── 用例 6 ──────────────────────────


@pytest.mark.asyncio
async def test_toggle_enable_when_complete_succeeds(client: AsyncClient, admin_headers):
    """6. 完整配置后可启用。"""
    payload = {
        "config": {
            "app_id": "20210000000xxx",
            "access_mode": "public_key",
            "app_private_key": "-----BEGIN RSA PRIVATE KEY-----\nfakekey\n-----END RSA PRIVATE KEY-----",
            "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfakepub\n-----END PUBLIC KEY-----",
        }
    }
    r1 = await client.put("/api/admin/payment-channels/alipay_h5",
                          headers=admin_headers, json=payload)
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_complete"] is True

    r2 = await client.patch(
        "/api/admin/payment-channels/alipay_h5/toggle",
        headers=admin_headers, json={"enabled": True},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_enabled"] is True


# ────────────────────────── 用例 7 ──────────────────────────


def test_aes256_gcm_roundtrip():
    """7. AES-256-GCM 加解密往返一致 + 加密前缀正确 + 同一明文两次加密密文不同（GCM 随机 nonce）。"""
    plain = "MySuperSecretApiKey-32CharsLong!!"
    enc1 = encrypt_value(plain)
    enc2 = encrypt_value(plain)
    assert is_encrypted(enc1)
    assert is_encrypted(enc2)
    assert enc1.startswith("ENC::AES256::")
    assert enc1 != enc2  # 不同 nonce
    assert decrypt_value(enc1) == plain
    assert decrypt_value(enc2) == plain
    # 空值/None
    assert encrypt_value(None) is None
    assert encrypt_value("") == ""
    # mask_value 边界
    assert mask_value("ab") == "****"
    assert mask_value("abcdef") == "****cdef"


# ────────────────────────── 用例 8 ──────────────────────────


@pytest.mark.asyncio
async def test_available_methods_app_order(client: AsyncClient, admin_headers):
    """8. /api/pay/available-methods?platform=app 仅返回已启用且完整的通道，按 微信(10) → 支付宝(20)。"""
    # 启用 wechat_app（先配齐）
    we_payload = {
        "config": {
            "app_id": "wx_app_id_xxx",
            "mch_id": "1900111111",
            "api_v3_key": "ApiV3KeyABCDEFGHIJKLMNOPQRSTUVWX",
            "cert_serial_no": "WX_SERIAL_001",
            "private_key": "-----BEGIN PRIVATE KEY-----\nA\n-----END PRIVATE KEY-----",
        }
    }
    r1 = await client.put("/api/admin/payment-channels/wechat_app",
                          headers=admin_headers, json=we_payload)
    assert r1.status_code == 200
    r1t = await client.patch("/api/admin/payment-channels/wechat_app/toggle",
                             headers=admin_headers, json={"enabled": True})
    assert r1t.status_code == 200, r1t.text

    # 启用 alipay_app（公钥模式）
    al_payload = {
        "config": {
            "app_id": "2021000111223344",
            "access_mode": "public_key",
            "app_private_key": "-----BEGIN PRIVATE KEY-----\nB\n-----END PRIVATE KEY-----",
            "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nC\n-----END PUBLIC KEY-----",
        }
    }
    r2 = await client.put("/api/admin/payment-channels/alipay_app",
                          headers=admin_headers, json=al_payload)
    assert r2.status_code == 200
    r2t = await client.patch("/api/admin/payment-channels/alipay_app/toggle",
                             headers=admin_headers, json={"enabled": True})
    assert r2t.status_code == 200

    # 查询 APP 端可用支付方式
    r3 = await client.get("/api/pay/available-methods?platform=app")
    assert r3.status_code == 200, r3.text
    items = r3.json()
    codes = [x["channel_code"] for x in items]
    assert codes == ["wechat_app", "alipay_app"], codes


# ────────────────────────── 用例 9 ──────────────────────────


@pytest.mark.asyncio
async def test_default_notify_url(client: AsyncClient, admin_headers):
    """9. /api/admin/payment-channels/{code}/default-notify-url 返回正确格式 URL。"""
    res = await client.get(
        "/api/admin/payment-channels/wechat_miniprogram/default-notify-url",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    url = body["notify_url"]
    assert url.endswith("/api/pay/notify/wechat_miniprogram"), url
    assert url.startswith("http://") or url.startswith("https://")
