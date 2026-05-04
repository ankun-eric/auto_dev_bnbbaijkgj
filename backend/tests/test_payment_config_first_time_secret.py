"""[Bug 修复 2026-05-05] 支付配置敏感字段首次创建强校验回归测试。

覆盖三类场景，对应 Bug 修复方案文档 §六 的用例 1 / 用例 2：

1. 首次创建时，必填敏感字段为空 → 后端必须 422 拒绝（不再静默吞掉私钥）
2. 编辑场景下，敏感字段留空 → 仍然保留旧值（向后兼容）
3. decrypt_value 在 raise_on_error=True 时，能区分"密钥不一致"与"数据本身就空"
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import PaymentChannel, User, UserRole
from app.utils.crypto import (
    DecryptionError,
    ENC_PREFIX,
    decrypt_value,
    encrypt_value,
    is_encrypted,
)


DEFAULT_SEEDS = [
    ("wechat_miniprogram", "微信小程序支付", "微信支付", "miniprogram", "wechat", 10),
    ("wechat_app", "微信APP支付", "微信支付", "app", "wechat", 10),
    ("alipay_h5", "支付宝H5支付", "支付宝", "h5", "alipay", 10),
    ("alipay_app", "支付宝APP支付", "支付宝", "app", "alipay", 20),
]


@pytest_asyncio.fixture(autouse=True)
async def _seed_clean():
    """每个测试前清空通道，并预置 4 条空通道（首次创建场景的起点）。"""
    async with test_session() as session:
        await session.execute(delete(PaymentChannel))
        await session.commit()
    async with test_session() as session:
        for code, name, disp, platform, provider, sort_order in DEFAULT_SEEDS:
            session.add(PaymentChannel(
                channel_code=code, channel_name=name, display_name=disp,
                platform=platform, provider=provider,
                is_enabled=False, is_complete=False, sort_order=sort_order,
                config_json={},
            ))
        await session.commit()
    yield
    async with test_session() as session:
        await session.execute(delete(PaymentChannel))
        await session.commit()


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient):
    async with test_session() as session:
        session.add(User(
            phone="13800077001",
            password_hash=get_password_hash("admin123"),
            nickname="敏感字段强校验测试管理员",
            role=UserRole.admin,
        ))
        await session.commit()
    res = await client.post("/api/admin/login", json={
        "phone": "13800077001",
        "password": "admin123",
    })
    body = res.json()
    token = body.get("token") or body.get("access_token")
    return {"Authorization": f"Bearer {token}"}


# ────────────────── 用例 1：首次创建时敏感字段空值 → 422 ──────────────────


@pytest.mark.asyncio
async def test_first_time_create_blank_app_private_key_returns_422(
    client: AsyncClient, admin_headers,
):
    """首次创建 alipay_h5 时 app_private_key 为空 → 422。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000000",
                "access_mode": "public_key",
                "app_private_key": "",  # 关键：空值
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json().get("detail", "")
    assert "应用私钥" in detail or "app_private_key" in detail, detail


@pytest.mark.asyncio
async def test_first_time_create_blank_wechat_secrets_returns_422(
    client: AsyncClient, admin_headers,
):
    """首次创建 wechat_miniprogram 时 api_v3_key 为空 → 422。"""
    res = await client.put(
        "/api/admin/payment-channels/wechat_miniprogram",
        headers=admin_headers,
        json={
            "config": {
                "appid": "wxabcdef1234567890",
                "mch_id": "1900000000",
                "api_v3_key": "",  # 关键：空值
                "cert_serial_no": "ABCDEF0123",
                "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
            }
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json().get("detail", "")
    assert "API V3" in detail or "api_v3_key" in detail, detail


# ────────────────── 用例 2：编辑场景留空保留旧值 → 200 ──────────────────


@pytest.mark.asyncio
async def test_edit_blank_secret_keeps_old_value(
    client: AsyncClient, admin_headers,
):
    """先完整保存，然后再次提交时敏感字段留空 → 应保留旧密文，不被吞掉。"""
    payload_full = {
        "config": {
            "app_id": "2021999999999999",
            "access_mode": "public_key",
            "app_private_key": "-----BEGIN RSA PRIVATE KEY-----\nFIRST_KEY_VALUE\n-----END RSA PRIVATE KEY-----",
            "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nFIRST_PUB_KEY\n-----END PUBLIC KEY-----",
        }
    }
    r1 = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers, json=payload_full,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_complete"] is True

    # 记录第一次保存后的密文
    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_h5")
        )).scalar_one()
        old_priv = ch.config_json.get("app_private_key")
        assert isinstance(old_priv, str) and old_priv.startswith(ENC_PREFIX)

    # 第二次提交：敏感字段全部留空（编辑场景）
    payload_edit = {
        "config": {
            "app_id": "2021999999999999",
            "access_mode": "public_key",
            "app_private_key": "",  # 留空表示保留旧值
            "alipay_public_key": "",
        }
    }
    r2 = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers, json=payload_edit,
    )
    assert r2.status_code == 200, r2.text  # 不应再 422
    assert r2.json()["is_complete"] is True

    # 验证密文未被改动
    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_h5")
        )).scalar_one()
        new_priv = ch.config_json.get("app_private_key")
        assert new_priv == old_priv, "编辑场景下留空的敏感字段不应被覆盖"


# ────────────────── 用例 3：解密失败错因区分 ──────────────────


def test_decrypt_value_raise_on_error_for_corrupt_ciphertext():
    """伪造一段 ENC:: 密文，在 raise_on_error=True 时应抛 DecryptionError。"""
    bogus = ENC_PREFIX + "bm90X3JlYWxseV9hbl9hZXNfY2lwaGVydGV4dA=="  # 不可解
    with pytest.raises(DecryptionError):
        decrypt_value(bogus, raise_on_error=True)
    # 默认行为（不传参）应保持向后兼容：返回空字符串，不抛
    assert decrypt_value(bogus) == ""


def test_decrypt_value_normal_roundtrip_no_error():
    """正常加密的数据应正常解密，无论 raise_on_error 如何。"""
    plain = "MyTestPrivateKeyForRoundtrip!!"
    enc = encrypt_value(plain)
    assert is_encrypted(enc)
    assert decrypt_value(enc) == plain
    assert decrypt_value(enc, raise_on_error=True) == plain


def test_decrypt_value_passthrough_for_plain_text():
    """非 ENC:: 前缀的字符串应原样返回，不报错。"""
    assert decrypt_value("plain_value") == "plain_value"
    assert decrypt_value("plain_value", raise_on_error=True) == "plain_value"
    assert decrypt_value(None) is None
    assert decrypt_value(None, raise_on_error=True) is None


# ────────────────── 用例 4：cert 模式条件必填 ──────────────────


@pytest.mark.asyncio
async def test_first_time_cert_mode_blank_root_cert_returns_422(
    client: AsyncClient, admin_headers,
):
    """access_mode=cert 时，alipay_root_cert 等条件必填字段为空 → 422。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000001",
                "access_mode": "cert",
                "app_private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
                "app_public_cert": "",  # 关键：空值
                "alipay_root_cert": "-----BEGIN CERT-----\nroot\n-----END CERT-----",
                "alipay_public_cert": "-----BEGIN CERT-----\npub\n-----END CERT-----",
            }
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json().get("detail", "")
    assert "应用公钥证书" in detail or "app_public_cert" in detail, detail


# ────────────────── 用例 5：仅传部分字段不会误触发校验 ──────────────────


@pytest.mark.asyncio
async def test_partial_payload_without_secret_does_not_trigger_strict_check(
    client: AsyncClient, admin_headers,
):
    """只更新非敏感字段（如 access_mode）不应被强校验拦截。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000002",  # 非敏感字段
            }
        },
    )
    # 只要 payload 中没有显式提交空的敏感字段，就不应被 422 拦截
    assert res.status_code == 200, res.text
    body = res.json()
    # 因为 app_private_key 等仍未填，is_complete 应保持 false
    assert body["is_complete"] is False
