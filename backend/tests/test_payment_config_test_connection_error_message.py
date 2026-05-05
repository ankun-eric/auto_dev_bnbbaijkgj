"""[Bug 修复 2026-05-05] 支付宝测试连接接口报错文案友好化回归测试。

覆盖 Bug 修复方案文档 §6 用例 8：
  - 当底层抛 RSA key format is not supported 时，
    test 接口应返回友好文案。

[Bug 修复 2026-05-05·后续] 后端已支持 PKCS8/PKCS1、含/不含头尾等全部合法形态，
  友好文案不再要求用户分辨 PKCS8.txt 与 RSA2048.txt，而是统一提示
  "PKCS8.txt 或 RSA2048.txt 任一即可"。本回归用例的断言也相应放宽。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import delete, select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import PaymentChannel, User, UserRole


def _gen_pkcs8_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


_TEST_PKCS8_PEM = _gen_pkcs8_pem()


@pytest_asyncio.fixture(autouse=True)
async def _seed_clean():
    async with test_session() as session:
        await session.execute(delete(PaymentChannel))
        await session.commit()
    yield
    async with test_session() as session:
        await session.execute(delete(PaymentChannel))
        await session.commit()


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient):
    async with test_session() as session:
        session.add(User(
            phone="13800077003",
            password_hash=get_password_hash("admin123"),
            nickname="支付宝测试连接文案测试管理员",
            role=UserRole.admin,
        ))
        await session.commit()
    res = await client.post("/api/admin/login", json={
        "phone": "13800077003",
        "password": "admin123",
    })
    body = res.json()
    token = body.get("token") or body.get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def alipay_h5_complete(client: AsyncClient, admin_headers):
    """先把 alipay_h5 通道置为完整状态（用合法 PKCS#8 私钥），方便后续 mock。"""
    async with test_session() as session:
        session.add(PaymentChannel(
            channel_code="alipay_h5", channel_name="支付宝H5支付",
            display_name="支付宝", platform="h5", provider="alipay",
            is_enabled=False, is_complete=False, sort_order=10,
            config_json={},
        ))
        await session.commit()
    res = await client.put(
        "/api/admin/payment-channels/alipay_h5",
        headers=admin_headers,
        json={
            "config": {
                "app_id": "2021000000000099",
                "access_mode": "public_key",
                "app_private_key": _TEST_PKCS8_PEM,
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
            }
        },
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_test_connection_returns_friendly_message_for_rsa_format_error(
    client: AsyncClient, admin_headers, alipay_h5_complete,
):
    """mock _build_client_from_config 抛 RSA key format is not supported 错误，
    /test 接口应返回友好文案而不是原始异常文本。"""

    def _raise_rsa_format(*args, **kwargs):
        raise ValueError("RSA key format is not supported")

    # _build_client_from_config 在 payment_config.py 中是 lazy import，
    # 模块级别没有该属性，因此只 patch 同名 alipay_service 中的函数即可
    with patch(
        "app.services.alipay_service._build_client_from_config",
        side_effect=_raise_rsa_format,
    ):
        res = await client.post(
            "/api/admin/payment-channels/alipay_h5/test",
            headers=admin_headers,
        )
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", "")
    # 友好文案必须包含「应用私钥」相关引导（PKCS8/RSA2048/无法识别 任一即可）
    assert (
        "应用私钥" in detail
        or "PKCS8" in detail
        or "RSA2048" in detail
        or "无法识别" in detail
    ), detail
    # 不能是裸的「调用支付宝异常：RSA key format is not supported」
    assert "调用支付宝异常：RSA key format is not supported" not in detail


@pytest.mark.asyncio
async def test_test_connection_returns_friendly_message_for_could_not_deserialize(
    client: AsyncClient, admin_headers, alipay_h5_complete,
):
    """mock 抛 Could not deserialize key data，应同样返回友好文案。"""

    def _raise_deserialize(*args, **kwargs):
        raise ValueError("Could not deserialize key data")

    with patch(
        "app.services.alipay_service._build_client_from_config",
        side_effect=_raise_deserialize,
    ):
        res = await client.post(
            "/api/admin/payment-channels/alipay_h5/test",
            headers=admin_headers,
        )
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", "")
    assert (
        "应用私钥" in detail
        or "PKCS8" in detail
        or "RSA2048" in detail
        or "无法识别" in detail
    ), detail
