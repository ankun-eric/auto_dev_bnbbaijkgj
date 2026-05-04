"""BUG-B 修复测试：积分商城 /api/points/mall?tab=exchangeable 严格 5 条件过滤

覆盖判定矩阵（节选交叉用例）：
- C1 库存=0          → 不可兑换 (SOLD_OUT)
- C2 积分不足        → 不可兑换 (INSUFFICIENT_POINTS)
- C3 goods_status=off_sale → 不可兑换 (OFF_SHELF)
- C4 status=draft（未发布）→ 不可兑换 (OFF_SHELF)
- C5 已达 limit_per_user → 不可兑换 (LIMIT_REACHED)
- C6 5 条件全满足    → 可兑换 (None)

注意：
- 模型当前无 start_at / end_at 字段，相关分支已通过 getattr 兼容；
  此处不构造时间维度用例（与 BUG-B 修复指令"不改 model"保持一致）。
- 用例不依赖 v11 既有兜底，验证"严格保留"语义（包括返回空数组）。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    PointExchangeRecord,
    PointsMallItem,
    PointsRecord,
    PointsType,
    User,
)
from tests.conftest import test_session


async def _create_and_publish(
    client: AsyncClient,
    admin_headers: dict,
    *,
    name: str,
    price: int,
    stock: int,
    limit_per_user: int = 0,
    publish: bool = True,
    item_type: str = "physical",
) -> dict:
    payload = {
        "name": name,
        "type": item_type,
        "price_points": price,
        "stock": stock,
        "description": "",
        "images": [],
        "limit_per_user": limit_per_user,
        "sort_weight": 0,
    }
    r = await client.post("/api/admin/points/mall", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    g = r.json()
    if publish:
        r2 = await client.post(
            f"/api/admin/points/mall/{g['id']}/publish", headers=admin_headers
        )
        assert r2.status_code == 200, r2.text
        g = r2.json()
    return g


async def _set_user_points(phone: str, amount: int):
    async with test_session() as session:
        user = (
            await session.execute(select(User).where(User.phone == phone))
        ).scalar_one()
        session.add(
            PointsRecord(
                user_id=user.id,
                points=amount,
                type=PointsType.signin,
                description="测试充积分",
            )
        )
        await session.commit()


async def _force_offline(goods_id: int):
    """绕过 admin offline 接口，直接把 goods_status 改为 off_sale。"""
    async with test_session() as session:
        item = (
            await session.execute(
                select(PointsMallItem).where(PointsMallItem.id == goods_id)
            )
        ).scalar_one()
        item.goods_status = "off_sale"
        await session.commit()


async def _add_exchange_record(user_phone: str, goods_id: int, count: int = 1):
    """模拟用户已兑换 N 次（用于 LIMIT_REACHED 场景）。"""
    async with test_session() as session:
        user = (
            await session.execute(select(User).where(User.phone == user_phone))
        ).scalar_one()
        for n in range(count):
            session.add(
                PointExchangeRecord(
                    order_no=f"EX_TEST_{goods_id}_{n}",
                    user_id=user.id,
                    goods_id=goods_id,
                    goods_type="physical",
                    goods_name=f"goods_{goods_id}",
                    points_cost=1,
                    quantity=1,
                    status="success",
                )
            )
        await session.commit()


# ─────────────────────────────────────────────────────────────
# 单条件参数化：除 1 条违例外其余满足，验证该商品被 exchangeable 过滤掉
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,price,stock,publish,limit,prior_used,expected_reason",
    [
        ("C1_no_stock", 10, 0, True, 0, 0, "SOLD_OUT"),
        ("C2_no_points", 9999, 5, True, 0, 0, "INSUFFICIENT_POINTS"),
        ("C4_draft_unpublished", 10, 5, False, 0, 0, "OFF_SHELF"),
        ("C5_limit_reached", 10, 5, True, 1, 1, "LIMIT_REACHED"),
        ("C6_all_pass", 10, 5, True, 0, 0, None),
    ],
)
async def test_exchangeable_single_condition(
    client: AsyncClient,
    admin_headers,
    user_token,
    case,
    price,
    stock,
    publish,
    limit,
    prior_used,
    expected_reason,
):
    headers_user = {"Authorization": f"Bearer {user_token}"}
    await _set_user_points("13900000001", 100)

    g = await _create_and_publish(
        client,
        admin_headers,
        name=f"商品_{case}",
        price=price,
        stock=stock,
        limit_per_user=limit,
        publish=publish,
    )
    if prior_used > 0:
        await _add_exchange_record("13900000001", g["id"], prior_used)

    r = await client.get(
        "/api/points/mall",
        params={"tab": "exchangeable", "page_size": 50},
        headers=headers_user,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    names = [it["name"] for it in data["items"]]
    item_ids = [it["id"] for it in data["items"]]

    if expected_reason is None:
        assert g["id"] in item_ids, f"{case} 应可兑换但未出现在 exchangeable 列表"
        item = next(it for it in data["items"] if it["id"] == g["id"])
        assert item["is_exchangeable"] is True
        assert item["exchangeable_reason"] is None
    else:
        assert g["id"] not in item_ids, (
            f"{case} 不应可兑换但出现了：names={names}"
        )

        # 必须能在 tab=all 中拿到，并验证 reason 字段
        r_all = await client.get(
            "/api/points/mall",
            params={"tab": "all", "page_size": 50},
            headers=headers_user,
        )
        items_all = r_all.json()["items"]
        match = [it for it in items_all if it["id"] == g["id"]]
        if expected_reason == "OFF_SHELF" and not publish:
            # 草稿态商品不在售，base_filter 直接排除，不会出现在 all 列表
            assert match == []
        else:
            assert match, f"{case} 在 tab=all 列表中也未找到，names={[it['name'] for it in items_all]}"
            it = match[0]
            assert it["is_exchangeable"] is False
            assert it["exchangeable_reason"] == expected_reason


# ─────────────────────────────────────────────────────────────
# off_sale 单独验证（已发布后下架）
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchangeable_excludes_off_sale(
    client: AsyncClient, admin_headers, user_token
):
    headers_user = {"Authorization": f"Bearer {user_token}"}
    await _set_user_points("13900000001", 500)

    g_on = await _create_and_publish(
        client, admin_headers, name="在售商品", price=10, stock=5
    )
    g_off = await _create_and_publish(
        client, admin_headers, name="已下架商品", price=10, stock=5
    )
    await _force_offline(g_off["id"])

    r = await client.get(
        "/api/points/mall",
        params={"tab": "exchangeable", "page_size": 50},
        headers=headers_user,
    )
    assert r.status_code == 200, r.text
    ids = [it["id"] for it in r.json()["items"]]
    assert g_on["id"] in ids
    assert g_off["id"] not in ids


# ─────────────────────────────────────────────────────────────
# 严格语义：移除兜底降级后，结果可以为空
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchangeable_strict_can_be_empty(
    client: AsyncClient, admin_headers, user_token
):
    """所有商品都不可兑换时，exchangeable Tab 应严格返回空数组（不再 <3 兜底）。"""
    headers_user = {"Authorization": f"Bearer {user_token}"}
    await _set_user_points("13900000001", 5)  # 仅 5 积分

    # 全部都积分不够
    for n in range(3):
        await _create_and_publish(
            client, admin_headers, name=f"贵商品{n}", price=9999, stock=5
        )

    r = await client.get(
        "/api/points/mall",
        params={"tab": "exchangeable", "page_size": 50},
        headers=headers_user,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["items"] == [], "严格过滤模式下不应再出现 <3 兜底降级"
    assert data["total"] == 0


# ─────────────────────────────────────────────────────────────
# 5 条件全满足 + 排序：可兑换排在不可兑换之前
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchangeable_sort_puts_eligible_first(
    client: AsyncClient, admin_headers, user_token
):
    headers_user = {"Authorization": f"Bearer {user_token}"}
    await _set_user_points("13900000001", 100)

    g_ok = await _create_and_publish(
        client, admin_headers, name="可兑A", price=10, stock=5
    )
    g_poor = await _create_and_publish(
        client, admin_headers, name="积分不够B", price=9999, stock=5
    )

    r = await client.get(
        "/api/points/mall",
        params={"tab": "all", "page_size": 50},
        headers=headers_user,
    )
    items = r.json()["items"]
    idx_ok = next(idx for idx, it in enumerate(items) if it["id"] == g_ok["id"])
    idx_poor = next(idx for idx, it in enumerate(items) if it["id"] == g_poor["id"])
    assert idx_ok < idx_poor, (
        f"可兑换商品应排在不可兑换之前：idx_ok={idx_ok}, idx_poor={idx_poor}"
    )
