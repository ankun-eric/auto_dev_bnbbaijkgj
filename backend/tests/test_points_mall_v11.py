"""积分商城 v1.1 自动化测试

覆盖：
- M1 三态流转（draft/on_sale/off_sale）+ 字段锁定
- M2 修改历史日志
- M3 复制新建 + 无缝替换
- M5 用户端列表 Tab（全部 / 可兑换）+ 两级排序 + 按钮态
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    PointsMallItem,
    PointsMallGoodsChangeLog,
    PointsRecord,
    PointsType,
    User,
)
from tests.conftest import test_session


async def _create_draft(client: AsyncClient, admin_headers: dict, **overrides):
    # 兼容测试里用 points / image 的写法，映射到后端实际字段
    payload = {
        "name": "测试商品",
        "type": "physical",
        "price_points": overrides.pop("points", 100) if "points" in overrides else 100,
        "stock": 10,
        "description": "测试",
        "images": [],
        "detail_html": "<p>hi</p>",
        "limit_per_user": 1,
        "sort_weight": 0,
    }
    if "image" in overrides:
        img = overrides.pop("image")
        if img:
            payload["images"] = [img]
    if "points" in overrides:
        payload["price_points"] = overrides.pop("points")
    payload.update(overrides)
    r = await client.post("/api/admin/points/mall", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _set_user_points(user_phone: str, amount: int):
    async with test_session() as session:
        user = (await session.execute(select(User).where(User.phone == user_phone))).scalar_one()
        session.add(PointsRecord(user_id=user.id, points=amount, type=PointsType.signin, description="测试充积分"))
        await session.commit()


# ───────── M1 三态流转 ─────────


@pytest.mark.asyncio
async def test_create_default_draft(client: AsyncClient, admin_headers):
    g = await _create_draft(client, admin_headers)
    assert g.get("goods_status") == "draft"


@pytest.mark.asyncio
async def test_publish_and_offline_flow(client: AsyncClient, admin_headers):
    g = await _create_draft(client, admin_headers)
    gid = g["id"]

    # draft → on_sale
    r = await client.post(f"/api/admin/points/mall/{gid}/publish", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("goods_status") == "on_sale"

    # on_sale → off_sale
    r = await client.post(f"/api/admin/points/mall/{gid}/offline", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("goods_status") == "off_sale"


@pytest.mark.asyncio
async def test_locked_field_cannot_be_changed_when_on_sale(client: AsyncClient, admin_headers):
    g = await _create_draft(client, admin_headers, points=100)
    gid = g["id"]
    await client.post(f"/api/admin/points/mall/{gid}/publish", headers=admin_headers)

    # 尝试修改锁定字段 price_points（积分价）
    r = await client.put(
        f"/api/admin/points/mall/{gid}",
        json={"price_points": 200, "goods_status": "on_sale"},
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text
    assert "锁定" in r.text or "不可修改" in r.text or "locked" in r.text.lower()


# ───────── M2 修改历史 ─────────


@pytest.mark.asyncio
async def test_change_log_title_and_image(client: AsyncClient, admin_headers):
    g = await _create_draft(client, admin_headers, name="初始标题", image="https://a/a.png")
    gid = g["id"]
    await client.post(f"/api/admin/points/mall/{gid}/publish", headers=admin_headers)

    # 修改标题 + 图片 → 应落日志
    r = await client.put(
        f"/api/admin/points/mall/{gid}",
        json={"name": "新标题", "images": ["https://a/b.png"]},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/admin/points/mall/{gid}/change-logs", headers=admin_headers)
    assert r.status_code == 200
    logs = r.json().get("items") or r.json()
    if isinstance(logs, dict):
        logs = logs.get("items", [])
    assert any(l.get("field_key") == "name" for l in logs)
    # 主图或 images 至少其一落日志
    assert any(l.get("field_key") in ("image", "main_image", "images") for l in logs)


# ───────── M3 复制新建 + 无缝替换 ─────────


@pytest.mark.asyncio
async def test_duplicate_and_seamless_replace(client: AsyncClient, admin_headers):
    original = await _create_draft(client, admin_headers, name="原商品")
    oid = original["id"]
    await client.post(f"/api/admin/points/mall/{oid}/publish", headers=admin_headers)

    # 复制新建
    r = await client.post(f"/api/admin/points/mall/{oid}/duplicate", headers=admin_headers)
    assert r.status_code == 200, r.text
    new_goods = r.json()
    nid = new_goods["id"]
    assert new_goods.get("goods_status") == "draft"
    assert new_goods.get("copied_from_goods_id") == oid

    # 发布新商品 → 原商品应自动下架并被替代
    r = await client.post(f"/api/admin/points/mall/{nid}/publish", headers=admin_headers)
    assert r.status_code == 200

    async with test_session() as session:
        old = (await session.execute(select(PointsMallItem).where(PointsMallItem.id == oid))).scalar_one()
        assert old.goods_status == "off_sale"
        assert old.replaced_by_goods_id == nid


# ───────── M5 用户端列表 ─────────


@pytest.mark.asyncio
async def test_user_list_tab_and_button_state(client: AsyncClient, admin_headers, user_token):
    # 构造 3 个在售商品：两个便宜（可兑换），一个贵（不可兑换），另一个库存=0
    headers_user = {"Authorization": f"Bearer {user_token}"}

    g1 = await _create_draft(client, admin_headers, name="便宜A", points=10, stock=5)
    g2 = await _create_draft(client, admin_headers, name="便宜B", points=20, stock=5)
    g3 = await _create_draft(client, admin_headers, name="贵重C", points=9999, stock=5)
    g4 = await _create_draft(client, admin_headers, name="空库D", points=10, stock=0, type="physical")

    for gid in (g1["id"], g2["id"], g3["id"], g4["id"]):
        await client.post(f"/api/admin/points/mall/{gid}/publish", headers=admin_headers)

    await _set_user_points("13900000001", 100)

    # tab=all
    r = await client.get("/api/points/mall", params={"tab": "all", "page_size": 50}, headers=headers_user)
    assert r.status_code == 200, r.text
    data = r.json()
    names = [it["name"] for it in data["items"]]
    assert set(["便宜A", "便宜B", "贵重C", "空库D"]).issubset(set(names))
    # 库存 0 应该沉底
    assert names.index("空库D") > names.index("便宜A")
    # has_exchangeable 为 True
    assert data.get("has_exchangeable") is True

    # 按钮态：空库D 应为 sold_out
    item_d = next(i for i in data["items"] if i["name"] == "空库D")
    assert item_d["button_state"] == "sold_out"
    # 贵重C 应为 not_enough
    item_c = next(i for i in data["items"] if i["name"] == "贵重C")
    assert item_c["button_state"] == "not_enough"
    # 便宜A 正常
    item_a = next(i for i in data["items"] if i["name"] == "便宜A")
    assert item_a["button_state"] == "normal"

    # tab=exchangeable：便宜A + 便宜B 可见；由于可兑换总数 = 2 < 3，触发兜底 → 展示所有 stock>0 的商品
    r = await client.get("/api/points/mall", params={"tab": "exchangeable", "page_size": 50}, headers=headers_user)
    assert r.status_code == 200
    names2 = [it["name"] for it in r.json()["items"]]
    # 兜底后库存>0 的 3 个应该全部出现
    assert "便宜A" in names2 and "便宜B" in names2 and "贵重C" in names2
    # 空库D（stock=0）即使在兜底也不应该展示（兜底只放宽积分条件，不放宽库存条件）
    assert "空库D" not in names2
