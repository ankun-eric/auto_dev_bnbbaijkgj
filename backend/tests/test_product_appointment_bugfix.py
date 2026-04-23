"""Tests for BUG-PRODUCT-APPT-001: 商品管理·预约与核销 保存失败 & 联动 UI 缺失

覆盖：
- 预约模式枚举对齐（none / date / time_slot / custom_form）
- 联动必填字段校验（advance_days / daily_quota / time_slots / custom_form_id）
- 预约表单库 CRUD（支持多商品复用）
- "表单"按钮潜规则收敛（未绑定不再自动建）
"""

import pytest
from httpx import AsyncClient


async def _create_cat(client: AsyncClient, admin_headers, name="预约分类") -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


# ──────────────── 1. 枚举对齐 ────────────────

@pytest.mark.asyncio
async def test_create_product_appointment_none(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "无需预约分类")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "普通商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "none",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["appointment_mode"] == "none"


@pytest.mark.asyncio
async def test_create_product_appointment_date_ok(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "日期预约分类")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "日期预约商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "date",
            "purchase_appointment_mode": "purchase_with_appointment",
            "advance_days": 7,
            "daily_quota": 20,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["appointment_mode"] == "date"
    assert body["advance_days"] == 7
    assert body["daily_quota"] == 20


@pytest.mark.asyncio
async def test_create_product_appointment_date_missing_advance_days(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "日期缺参分类")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "日期缺参商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "date",
            "purchase_appointment_mode": "purchase_with_appointment",
            # 缺 advance_days
            "daily_quota": 20,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    # Pydantic 错误 detail 是 list，其中至少一项包含"提前可预约天数"
    flat = str(body)
    assert "提前可预约天数" in flat


@pytest.mark.asyncio
async def test_create_product_appointment_time_slot_ok(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "时段预约分类")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "时段预约商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "time_slot",
            "purchase_appointment_mode": "appointment_later",
            "time_slots": [
                {"start": "09:00", "end": "10:00", "capacity": 5},
                {"start": "14:00", "end": "15:00", "capacity": 3},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["appointment_mode"] == "time_slot"
    assert isinstance(body["time_slots"], list) and len(body["time_slots"]) == 2


@pytest.mark.asyncio
async def test_create_product_appointment_time_slot_empty(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "时段空分类")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "时段空商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "time_slot",
            "purchase_appointment_mode": "purchase_with_appointment",
            "time_slots": [],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert "至少配置 1 个时段" in str(resp.json())


@pytest.mark.asyncio
async def test_create_product_appointment_custom_form_missing(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "自定义表单缺参")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "自定义表单缺参商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "custom_form",
            "purchase_appointment_mode": "purchase_with_appointment",
            # 缺 custom_form_id
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert "必须绑定一张预约表单" in str(resp.json())


@pytest.mark.asyncio
async def test_create_product_invalid_appointment_mode(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "非法枚举")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "非法枚举商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "schedule",  # 旧值，已下线
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert "预约模式不合法" in str(resp.json())


# ──────────────── 2. 预约表单库 ────────────────

@pytest.mark.asyncio
async def test_appointment_form_crud_and_reuse(client: AsyncClient, admin_headers):
    # 新建表单
    resp = await client.post(
        "/api/admin/appointment-forms",
        json={"name": "通用基础信息表", "description": "姓名/手机号"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    form_id = resp.json()["id"]

    # 加字段
    r2 = await client.post(
        f"/api/admin/appointment-forms/{form_id}/fields",
        json={"field_type": "text", "label": "姓名", "required": True, "sort_order": 0},
        headers=admin_headers,
    )
    assert r2.status_code == 200

    # 列表
    rl = await client.get("/api/admin/appointment-forms", headers=admin_headers)
    assert rl.status_code == 200
    items = rl.json()["items"]
    target = next((i for i in items if i["id"] == form_id), None)
    assert target and target["field_count"] == 1

    # 用同一张表单创建 2 个商品 → 多商品复用成功
    cid = await _create_cat(client, admin_headers, "复用分类")
    for i in range(2):
        r = await client.post(
            "/api/admin/products",
            json={
                "name": f"复用商品{i}",
                "category_id": cid,
                "fulfillment_type": "in_store",
                "original_price": 10.0,
                "sale_price": 9.0,
                "stock": 1,
                "status": "draft",
                "appointment_mode": "custom_form",
                "purchase_appointment_mode": "purchase_with_appointment",
                "custom_form_id": form_id,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text

    # 再查列表，product_count 应 = 2
    rl2 = await client.get("/api/admin/appointment-forms", headers=admin_headers)
    target2 = next((i for i in rl2.json()["items"] if i["id"] == form_id), None)
    assert target2["product_count"] == 2

    # 被引用时删除应报 409
    rd = await client.delete(f"/api/admin/appointment-forms/{form_id}", headers=admin_headers)
    assert rd.status_code == 409


@pytest.mark.asyncio
async def test_form_button_no_longer_auto_create(client: AsyncClient, admin_headers):
    """商品未绑 custom_form_id 时，拉取字段接口不再偷偷建表单。"""
    cid = await _create_cat(client, admin_headers, "未绑表单分类")
    r = await client.post(
        "/api/admin/products",
        json={
            "name": "未绑表单商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "appointment_mode": "none",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    product_id = r.json()["id"]

    rf = await client.get(
        f"/api/admin/products/{product_id}/form-fields",
        headers=admin_headers,
    )
    assert rf.status_code == 200
    body = rf.json()
    assert body["form_id"] is None
    assert body["items"] == []
    assert "表单库" in body.get("message", "")
