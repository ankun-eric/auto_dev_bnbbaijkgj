"""积分商城 H5 详情页"立即兑换"按钮置灰 Bug 修复回归测试.

Bug：H5 端 /points/product-detail 页面底部"立即兑换"按钮始终为灰色禁用态，
长按 / 点击均无响应；列表页"兑换"按钮可正常点击。

根因：后端 GET /api/points/mall/items/{id} 的 button_state 默认初始值是 "normal"，
缺少 "exchangeable"，且没有积分不足("insufficient")态判定；H5 详情页又把
disabled 严格绑定到 `button_state !== 'exchangeable'`，导致正常情况按钮永久 disabled。

本测试覆盖修复后的 5 态：
  exchangeable / offline / sold_out / limit_reached / insufficient
以及前端需要的 user_available_points / user_exchanged_count / service_product 字段。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FulfillmentType,
    PointsMallItem,
    PointsRecord,
    PointsType,
    Product,
    ProductCategory,
    User,
)
from tests.conftest import test_session


# ────────────────────────── 工具函数 ──────────────────────────


async def _create_item(
    *,
    name: str = "测试积分商品",
    type_: str = "physical",
    price_points: int = 100,
    stock: int = 10,
    status: str = "active",
    limit_per_user: int = 0,
    ref_service_id: int | None = None,
) -> int:
    async with test_session() as s:
        it = PointsMallItem(
            name=name,
            type=type_,
            price_points=price_points,
            stock=stock,
            status=status,
            limit_per_user=limit_per_user,
            ref_service_id=ref_service_id,
            description="",
            images=[],
            detail_html="<p>desc</p>",
        )
        s.add(it)
        await s.commit()
        await s.refresh(it)
        return it.id


async def _set_user_points(phone: str, amount: int) -> int:
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
        s.add(
            PointsRecord(
                user_id=u.id,
                points=amount,
                type=PointsType.signin,
                description="测试加积分",
            )
        )
        await s.commit()
        return u.id


# ────────────────────────── 用例 1：登录后正常商品默认 exchangeable（Bug 修复关键回归） ──────────────────────────


@pytest.mark.asyncio
async def test_detail_default_state_is_exchangeable_not_normal(
    client: AsyncClient, auth_headers
):
    """**Bug 修复关键回归**：登录用户 + 库存充足 + 在架 + 积分够 → button_state='exchangeable'.

    Bug 现象：之前默认值 'normal'，导致 H5 详情页 `disabled = state !== 'exchangeable'`
    永远为 true，按钮永远置灰、点击长按完全无响应。本用例守护此修复永不回退。
    """
    await _set_user_points("13900000001", 1000)
    iid = await _create_item(price_points=50, stock=5)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "exchangeable", (
        f"正常商品 button_state 必须为 'exchangeable'，实际={data.get('button_state')}; "
        f"若返回 'normal' 说明 bug 已回退！"
    )
    assert data["button_state"] != "normal"
    assert "立即兑换" in (data.get("button_text") or "")


# ────────────────────────── 用例 2：登录态 + 积分充足 → exchangeable ──────────────────────────


@pytest.mark.asyncio
async def test_detail_authed_enough_points_exchangeable(
    client: AsyncClient, auth_headers, user_token
):
    """登录用户 + 积分充足：button_state='exchangeable'，user_available_points>=price."""
    # 给用户充 1000 积分
    await _set_user_points("13900000001", 1000)
    iid = await _create_item(price_points=100, stock=5)

    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "exchangeable"
    assert data["user_available_points"] >= 100
    assert data["user_exchanged_count"] == 0


# ────────────────────────── 用例 3：积分不足 → insufficient ──────────────────────────


@pytest.mark.asyncio
async def test_detail_insufficient_points(client: AsyncClient, auth_headers):
    """登录用户积分不足：button_state='insufficient'，文案含'差 X 分'."""
    await _set_user_points("13900000001", 30)  # 只有 30 积分
    iid = await _create_item(price_points=100, stock=5)

    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "insufficient"
    assert "差" in data["button_text"] and "70" in data["button_text"]


# ────────────────────────── 用例 4：商品下架 → offline ──────────────────────────


@pytest.mark.asyncio
async def test_detail_offline_status(client: AsyncClient, auth_headers):
    iid = await _create_item(status="off_sale", price_points=50, stock=5)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "offline"
    assert data["button_text"] == "已下架"


# ────────────────────────── 用例 5：库存为 0（非 coupon）→ sold_out ──────────────────────────


@pytest.mark.asyncio
async def test_detail_sold_out_when_stock_zero(client: AsyncClient, auth_headers):
    iid = await _create_item(type_="physical", price_points=50, stock=0)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "sold_out"
    assert data["button_text"] == "已兑完"


# ────────────────────────── 用例 6：达到限兑次数 → limit_reached ──────────────────────────


@pytest.mark.asyncio
async def test_detail_limit_reached(client: AsyncClient, auth_headers):
    """每人限兑 1 次，写一条 success 记录后再访问详情应返回 limit_reached."""
    from datetime import datetime

    from app.models.models import PointExchangeRecord

    user_id = await _set_user_points("13900000001", 1000)
    iid = await _create_item(price_points=100, stock=10, limit_per_user=1)

    async with test_session() as s:
        s.add(
            PointExchangeRecord(
                user_id=user_id,
                goods_id=iid,
                goods_type="physical",
                goods_name="测试积分商品",
                points_cost=100,
                quantity=1,
                status="success",
                order_no=f"EX{datetime.utcnow().strftime('%Y%m%d')}999999",
                exchange_time=datetime.utcnow(),
            )
        )
        await s.commit()

    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["button_state"] == "limit_reached"
    assert data["user_exchanged_count"] == 1


# ────────────────────────── 用例 7：button_state 优先级（offline 优先于 sold_out 优先于 insufficient） ──────────────────────────


@pytest.mark.asyncio
async def test_detail_button_state_priority(client: AsyncClient, auth_headers):
    """商品下架 + 库存为 0 + 积分不足 → 仍应返回 'offline'（最高优先级）."""
    iid = await _create_item(status="off_sale", type_="physical", stock=0, price_points=99999)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["button_state"] == "offline"


# ────────────────────────── 用例 8：service 类型详情应返回 service_product 字段 ──────────────────────────


@pytest.mark.asyncio
async def test_detail_service_product_field_present(client: AsyncClient, auth_headers):
    """service 类型积分商品 → 详情接口必须返回 service_product，给前端展示关联服务卡片."""
    await _set_user_points("13900000001", 10000)
    async with test_session() as s:
        cat = ProductCategory(name="测试分类")
        s.add(cat)
        await s.commit()
        await s.refresh(cat)
        prod = Product(
            name="测试关联服务",
            category_id=cat.id,
            sale_price=199.0,
            images=["https://example.com/p.png"],
            description="服务",
            fulfillment_type=FulfillmentType.on_site,
        )
        s.add(prod)
        await s.commit()
        await s.refresh(prod)
        prod_id = prod.id

    iid = await _create_item(type_="service", ref_service_id=prod_id, stock=0, price_points=10)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "service"
    assert data["service_product"] is not None
    assert data["service_product"]["id"] == prod_id
    assert data["service_product"]["name"] == "测试关联服务"
    # service 类型 stock=0 不应被判定为 sold_out（stock=0 视为无限）
    # 列表页/详情页都应认为可兑换
    assert data["button_state"] == "exchangeable"


# ────────────────────────── 用例 9：button_text 在可兑换态下展示"立即兑换" ──────────────────────────


@pytest.mark.asyncio
async def test_detail_button_text_includes_li_ji_dui_huan(
    client: AsyncClient, auth_headers
):
    """正常可兑换态下 button_text 应当为「立即兑换」（与列表页保持一致，避免空文案）."""
    await _set_user_points("13900000001", 1000)
    iid = await _create_item(price_points=10, stock=5)
    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["button_text"] == "立即兑换"


# ────────────────────────── 用例 10：响应字段完整性回归 ──────────────────────────


@pytest.mark.asyncio
async def test_detail_response_required_fields(client: AsyncClient, auth_headers):
    """详情接口必须返回 H5 详情页所需的全部字段."""
    await _set_user_points("13900000001", 200)
    iid = await _create_item(price_points=100, stock=3, limit_per_user=2)

    r = await client.get(f"/api/points/mall/items/{iid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()

    required = {
        "id",
        "name",
        "type",
        "price_points",
        "stock",
        "status",
        "limit_per_user",
        "button_state",
        "button_text",
        "user_exchanged_count",
        "user_available_points",
        "service_product",
    }
    missing = required - set(data.keys())
    assert not missing, f"详情接口缺失字段: {missing}"
