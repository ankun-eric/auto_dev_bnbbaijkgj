"""[Bug 修复 2026-05-05] 支付宝通道保存私钥格式校验回归测试。

覆盖 Bug 修复方案文档 §6 用例 5~7：
  - 用例 5：PUT 接口接收 PKCS#1 私钥（含/不含 PEM 头）→ 自动转 PKCS#8 落库
  - 用例 6：PUT 接口接收乱码 → 返回 422，错误文案明确指向 应用私钥PKCS8.txt
  - 用例 7：PUT 接口接收合法 PKCS#8 → 200，库内密文解密后为 PKCS#8 PEM 形态
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import delete, select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import PaymentChannel, User, UserRole
from app.utils.crypto import ENC_PREFIX, decrypt_value


DEFAULT_SEEDS = [
    ("alipay_h5", "支付宝H5支付", "支付宝", "h5", "alipay", 10),
    ("alipay_app", "支付宝APP支付", "支付宝", "app", "alipay", 20),
]


def _gen_rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _to_pkcs8_pem(key) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _to_pkcs1_pem(key) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _pem_body_to_naked_b64(pem: str) -> str:
    return "".join(
        ln for ln in pem.strip().splitlines() if not ln.startswith("-----")
    )


# 模块级生成一把 RSA 私钥（多个测试共享，避免重复生成开销）
_KEY = _gen_rsa_key()
_PKCS8_PEM = _to_pkcs8_pem(_KEY)
_PKCS1_PEM = _to_pkcs1_pem(_KEY)
_PKCS8_NAKED = _pem_body_to_naked_b64(_PKCS8_PEM)
_PKCS1_NAKED = _pem_body_to_naked_b64(_PKCS1_PEM)


@pytest_asyncio.fixture(autouse=True)
async def _seed_clean():
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
            phone="13800077002",
            password_hash=get_password_hash("admin123"),
            nickname="支付宝私钥校验测试管理员",
            role=UserRole.admin,
        ))
        await session.commit()
    res = await client.post("/api/admin/login", json={
        "phone": "13800077002",
        "password": "admin123",
    })
    body = res.json()
    token = body.get("token") or body.get("access_token")
    return {"Authorization": f"Bearer {token}"}


# ────────────────── 用例 5：PKCS#1 → 自动转 PKCS#8 落库 ──────────────────


@pytest.mark.asyncio
async def test_put_accepts_pkcs1_naked_and_normalizes_to_pkcs8(
    client: AsyncClient, admin_headers,
):
    """提交 PKCS#1 裸 base64（应用私钥RSA2048.txt 内容）→ 200，库内为 PKCS#8 PEM 密文。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000010",
                "access_mode": "public_key",
                "app_private_key": _PKCS1_NAKED,  # 关键：PKCS#1 裸 base64
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 200, res.text

    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_h5")
        )).scalar_one()
        enc = ch.config_json.get("app_private_key")
        assert isinstance(enc, str) and enc.startswith(ENC_PREFIX)
        # 解密后必须是标准化的 PKCS#8 PEM（含 BEGIN PRIVATE KEY，不含 RSA 头）
        plain = decrypt_value(enc)
        assert "-----BEGIN PRIVATE KEY-----" in plain
        assert "-----BEGIN RSA PRIVATE KEY-----" not in plain


@pytest.mark.asyncio
async def test_put_accepts_pkcs1_pem_and_normalizes_to_pkcs8(
    client: AsyncClient, admin_headers,
):
    """提交 PKCS#1 + PEM 头（含 BEGIN RSA PRIVATE KEY）→ 200，库内为 PKCS#8 PEM。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_app",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000011",
                "access_mode": "public_key",
                "app_private_key": _PKCS1_PEM,
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 200, res.text

    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_app")
        )).scalar_one()
        plain = decrypt_value(ch.config_json.get("app_private_key"))
        assert "-----BEGIN PRIVATE KEY-----" in plain
        assert "-----BEGIN RSA PRIVATE KEY-----" not in plain


# ────────────────── 用例 6：乱码 → 422，错误文案明确 ──────────────────


@pytest.mark.asyncio
async def test_put_rejects_garbage_private_key_with_friendly_message(
    client: AsyncClient, admin_headers,
):
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000012",
                "access_mode": "public_key",
                "app_private_key": "this is definitely not a valid private key !!!",
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json().get("detail", "")
    # [Bug 修复 2026-05-05·后续] 后端已支持 PKCS8/PKCS1、含/不含头尾全部合法形态，
    # 友好文案统一改为「PKCS8.txt 或 RSA2048.txt 任一即可」，不再强求两选一。
    assert (
        "应用私钥" in detail
        or "PKCS8" in detail
        or "RSA2048" in detail
        or "无法识别" in detail
    ), detail


# ────────────────── 用例 7：合法 PKCS#8 → 200，密文解密为 PKCS#8 ──────────────────


@pytest.mark.asyncio
async def test_put_accepts_pkcs8_pem_and_stores_pkcs8(
    client: AsyncClient, admin_headers,
):
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000013",
                "access_mode": "public_key",
                "app_private_key": _PKCS8_PEM,
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 200, res.text

    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_h5")
        )).scalar_one()
        plain = decrypt_value(ch.config_json.get("app_private_key"))
        assert "-----BEGIN PRIVATE KEY-----" in plain


@pytest.mark.asyncio
async def test_put_accepts_pkcs8_naked_base64(
    client: AsyncClient, admin_headers,
):
    """提交 PKCS#8 裸 base64（应用私钥PKCS8.txt 内容）→ 200。"""
    res = await client.put(
        "/api/admin/payment-channels/alipay_app",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000014",
                "access_mode": "public_key",
                "app_private_key": _PKCS8_NAKED,
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 200, res.text

    async with test_session() as session:
        ch = (await session.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_app")
        )).scalar_one()
        plain = decrypt_value(ch.config_json.get("app_private_key"))
        assert "-----BEGIN PRIVATE KEY-----" in plain
