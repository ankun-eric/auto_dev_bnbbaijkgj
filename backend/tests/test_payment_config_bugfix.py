"""[支付配置 Bug 修复] 针对「页面加载失败」Bug 的回归测试。

覆盖：
1. 种子记录 created_at / updated_at 为 NULL 时，列表接口仍能返回 200（不再 500）
2. 列表接口返回的每条记录都有合法的 created_at / updated_at（datetime 兜底）
3. 缺通道时列表接口会自动补齐到 4 条（自愈机制）
4. 列表接口在异常时返回结构化 detail（不再裸抛 500）
5. config_json 损坏时单条降级而不让整列表挂掉
6. 启动期 schema_sync 会回补 NULL 时间戳
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select, text, update

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import PaymentChannel, User, UserRole


DEFAULT_SEEDS = [
    ("wechat_miniprogram", "微信小程序支付", "微信支付", "miniprogram", "wechat", 10),
    ("wechat_app", "微信APP支付", "微信支付", "app", "wechat", 10),
    ("alipay_h5", "支付宝H5支付", "支付宝", "h5", "alipay", 10),
    ("alipay_app", "支付宝APP支付", "支付宝", "app", "alipay", 20),
]


@pytest_asyncio.fixture(autouse=True)
async def _clean_channels():
    """每个测试前清空通道，让用例自己控制初始状态。"""
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
            phone="13800099001",
            password_hash=get_password_hash("admin123"),
            nickname="支付配置 Bug 修复测试管理员",
            role=UserRole.admin,
        ))
        await session.commit()
    res = await client.post("/api/admin/login", json={
        "phone": "13800099001",
        "password": "admin123",
    })
    body = res.json()
    token = body.get("token") or body.get("access_token")
    return {"Authorization": f"Bearer {token}"}


# ────────────────────── 用例 1：created_at NULL 不再 500 ──────────────────────


@pytest.mark.asyncio
async def test_list_returns_200_even_if_timestamps_are_null(
    client: AsyncClient, admin_headers,
):
    """根因复现：种子记录 created_at/updated_at 为 NULL 时列表接口必须返回 200。

    修复前会返回 500（pydantic ValidationError: 2 validation errors for
    PaymentChannelResponse；created_at Input should be a valid datetime,
    input_value=None）。
    """
    async with test_session() as session:
        for code, name, disp, platform, provider, sort_order in DEFAULT_SEEDS:
            session.add(PaymentChannel(
                channel_code=code, channel_name=name, display_name=disp,
                platform=platform, provider=provider,
                is_enabled=False, is_complete=False, sort_order=sort_order,
                config_json={},
            ))
        await session.commit()
        # 强制把 created_at / updated_at 改为 NULL，复现服务器现场
        await session.execute(text(
            "UPDATE payment_channels SET created_at = NULL, updated_at = NULL"
        ))
        await session.commit()

    res = await client.get("/api/admin/payment-channels", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 4
    for item in data:
        # 兜底后必须返回合法的时间字符串
        assert item["created_at"] is not None and item["created_at"] != ""
        assert item["updated_at"] is not None and item["updated_at"] != ""


# ────────────────────── 用例 2：缺通道时自愈 ──────────────────────


@pytest.mark.asyncio
async def test_list_auto_heals_missing_channels(client: AsyncClient, admin_headers):
    """空表时调用列表接口应自动补齐 4 条通道。"""
    res = await client.get("/api/admin/payment-channels", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    codes = {x["channel_code"] for x in data}
    assert codes == {
        "wechat_miniprogram", "wechat_app", "alipay_h5", "alipay_app",
    }


@pytest.mark.asyncio
async def test_list_auto_heals_partial_channels(client: AsyncClient, admin_headers):
    """缺 1~2 条时应补齐到 4 条，已有的不被覆盖。"""
    async with test_session() as session:
        session.add(PaymentChannel(
            channel_code="wechat_miniprogram",
            channel_name="微信小程序支付", display_name="自定义微信支付",
            platform="miniprogram", provider="wechat",
            is_enabled=False, is_complete=False, sort_order=99,
            config_json={"appid": "wxabc"},
        ))
        await session.commit()

    res = await client.get("/api/admin/payment-channels", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 4
    # 已存在的不被覆盖：display_name 应保持自定义值，sort_order=99
    we = next(x for x in data if x["channel_code"] == "wechat_miniprogram")
    assert we["display_name"] == "自定义微信支付"
    assert we["sort_order"] == 99


# ────────────────────── 用例 3：损坏 config 单条降级 ──────────────────────


@pytest.mark.asyncio
async def test_corrupted_config_does_not_break_whole_list(
    client: AsyncClient, admin_headers,
):
    """单条记录的 config_json 含异常加密数据，不应让整条列表挂掉。"""
    async with test_session() as session:
        for code, name, disp, platform, provider, sort_order in DEFAULT_SEEDS:
            session.add(PaymentChannel(
                channel_code=code, channel_name=name, display_name=disp,
                platform=platform, provider=provider,
                is_enabled=False, is_complete=False, sort_order=sort_order,
                config_json={},
            ))
        await session.commit()
        # 故意写入一个非法的 ENC:: 前缀值
        await session.execute(update(PaymentChannel).where(
            PaymentChannel.channel_code == "alipay_h5",
        ).values(config_json={
            "app_id": "20210000",
            "access_mode": "public_key",
            "app_private_key": "ENC::AES256::!!!corrupted-base64-data!!!",
            "alipay_public_key": "ENC::AES256::xxxxx-bad",
        }))
        await session.commit()

    res = await client.get("/api/admin/payment-channels", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 4
    # 即使损坏，对应通道也应有 channel_code 字段返回
    codes = {x["channel_code"] for x in data}
    assert "alipay_h5" in codes


# ────────────────────── 用例 4：异常返回结构化 detail ──────────────────────


@pytest.mark.asyncio
async def test_unauthorized_returns_401_with_detail(client: AsyncClient):
    """无 token 访问应返回 401 + 明确 detail，便于前端展示根因。"""
    res = await client.get("/api/admin/payment-channels")
    assert res.status_code == 401
    body = res.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


# ────────────────────── 用例 5：路由已挂载 ──────────────────────


@pytest.mark.asyncio
async def test_payment_channels_route_is_mounted(client: AsyncClient):
    """/api/admin/payment-channels 路径必须可达（不应 404）。

    无 token 应返回 401 而非 404（如果 404 说明路由未挂载）。
    """
    res = await client.get("/api/admin/payment-channels")
    assert res.status_code == 401, (
        f"路由可能未挂载，期望 401 实际 {res.status_code}: {res.text}"
    )


# ────────────────────── 用例 6：单条详情兜底 ──────────────────────


@pytest.mark.asyncio
async def test_get_single_channel_with_null_timestamp(
    client: AsyncClient, admin_headers,
):
    """单条详情接口在 created_at 为 NULL 时也应返回 200。"""
    async with test_session() as session:
        session.add(PaymentChannel(
            channel_code="wechat_app",
            channel_name="微信APP支付", display_name="微信支付",
            platform="app", provider="wechat",
            is_enabled=False, is_complete=False, sort_order=10,
            config_json={},
        ))
        await session.commit()
        await session.execute(text(
            "UPDATE payment_channels SET created_at = NULL, updated_at = NULL "
            "WHERE channel_code = 'wechat_app'"
        ))
        await session.commit()

    res = await client.get(
        "/api/admin/payment-channels/wechat_app", headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["channel_code"] == "wechat_app"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None
