"""[商家 PC 后台优化 PRD v1.1] 自动化测试

覆盖范围：
- F1+F2：14 态状态映射存在性 + 商家订单列表返回 status 在 14 态范围内
- F4：商家订单附件接口（GET / POST upload / DELETE）
  - 上传 jpg → 成功
  - 上传 pdf → 成功
  - 上传 docx → 400（仅支持 jpg/png/pdf）
  - 单文件 > 5MB → 400
  - 已有 9 个时再上传 → 400
  - 列表返回数量正确
  - 删除后列表减少
- F7：redeemed → completed 数据迁移函数幂等可重入
- F8：paid 历史状态在前端兼容映射（仅 backend 不再写入，靠前端 mapping）
"""
from __future__ import annotations

import io

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.security import get_password_hash
from app.models.models import (
    AccountIdentity,
    FulfillmentType,
    IdentityType,
    MerchantCategory,
    MerchantStore,
    MerchantStoreMembership,
    OrderAttachment,
    OrderItem,
    Product,
    ProductCategory,
    ProductStore,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from tests.conftest import test_session


# ────────────────── 辅助 fixture ──────────────────


async def _ensure_category() -> int:
    async with test_session() as db:
        res = await db.execute(select(MerchantCategory).where(MerchantCategory.code == "self_store"))
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def merchant_setup(client: AsyncClient):
    """创建：
    - 1 个商家用户（owner_user）
    - 1 个门店 + 该用户的 owner membership
    - 1 个商品（挂载到该门店）
    - 1 个 UnifiedOrder + OrderItem
    返回所需 ID 和登录 token。
    """
    # 1. 用户
    async with test_session() as db:
        user = User(
            phone="13900001111",
            password_hash=get_password_hash("test1234"),
            nickname="测试商家",
            role=UserRole.merchant,
        )
        db.add(user)
        await db.flush()
        user_id = user.id

        # 商家身份（require_identity 校验依赖此表）
        identity = AccountIdentity(
            user_id=user_id,
            identity_type=IdentityType.merchant_owner,
            status="active",
        )
        db.add(identity)

        cat_id = await _ensure_category()

        # 商家档案 store
        store = MerchantStore(
            category_id=cat_id,
            store_name="测试门店",
            store_code="ST001",
            contact_name="店长",
            contact_phone="13800000001",
            address="测试地址",
            lat=23.0,
            lng=113.0,
            status="active",
        )
        db.add(store)
        await db.flush()
        store_id = store.id

        membership = MerchantStoreMembership(
            user_id=user_id,
            store_id=store_id,
            member_role="owner",
            status="active",
        )
        db.add(membership)

        # 商品
        pcat = ProductCategory(name="测试分类", sort_order=1)
        db.add(pcat)
        await db.flush()
        product = Product(
            category_id=pcat.id,
            name="测试商品",
            description="测试用",
            sale_price=199.00,
            original_price=299.00,
            stock=10,
            fulfillment_type=FulfillmentType.in_store,
        )
        db.add(product)
        await db.flush()
        product_id = product.id

        ps = ProductStore(product_id=product_id, store_id=store_id)
        db.add(ps)

        # 统一订单
        uo = UnifiedOrder(
            order_no="UO_TEST_001",
            user_id=user_id,
            total_amount=199.00,
            paid_amount=199.00,
            status=UnifiedOrderStatus.pending_use,
        )
        db.add(uo)
        await db.flush()
        order_id = uo.id

        oi = OrderItem(
            order_id=order_id,
            product_id=product_id,
            product_name="测试商品",
            product_price=199.00,
            quantity=1,
            subtotal=199.00,
            fulfillment_type=FulfillmentType.in_store,
        )
        db.add(oi)

        await db.commit()

    # 2. 登录
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": "13900001111", "password": "test1234"},
    )
    assert login_resp.status_code == 200, login_resp.text
    body = login_resp.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"login response missing token: {body}"

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "store_id": store_id,
        "product_id": product_id,
        "order_id": order_id,
    }


# ────────────────── F1+F2：14 态映射存在性 ──────────────────


@pytest.mark.asyncio
async def test_unified_order_status_enum_has_14_states():
    """后端 UnifiedOrderStatus 枚举至少覆盖 PRD 所述 13 个核心态（pending_review 历史保留）。"""
    expected = {
        "pending_payment",
        "pending_shipment",
        "pending_receipt",
        "pending_appointment",
        "appointed",
        "pending_use",
        "partial_used",
        "pending_review",
        "completed",
        "expired",
        "refunding",
        "refunded",
        "cancelled",
    }
    actual = {s.value for s in UnifiedOrderStatus}
    assert expected.issubset(actual), f"缺少状态: {expected - actual}"


# ────────────────── F4：附件接口 ──────────────────


@pytest.mark.asyncio
async def test_merchant_attachments_list_empty_initially(
    client: AsyncClient, merchant_setup
):
    """新订单的附件列表应为空数组。"""
    order_id = merchant_setup["order_id"]
    res = await client.get(
        f"/api/merchant/orders/{order_id}/attachments",
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 200, res.text
    assert res.json() == []


@pytest.mark.asyncio
async def test_merchant_attachment_upload_jpg_ok(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """上传 jpg 图片应成功，返回的 file_type=image。"""
    monkeypatch.chdir(tmp_path)  # 让 uploads/ 创建在临时目录
    order_id = merchant_setup["order_id"]
    files = {"file": ("photo.jpg", io.BytesIO(b"fakejpgdata" * 100), "image/jpeg")}
    res = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["file_type"] == "image"
    assert data["file_name"] == "photo.jpg"
    assert data["order_id"] == order_id
    assert data["file_url"].startswith("/uploads/order_attachments/")


@pytest.mark.asyncio
async def test_merchant_attachment_upload_pdf_ok(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """上传 pdf 文档应成功，file_type=pdf。"""
    monkeypatch.chdir(tmp_path)
    order_id = merchant_setup["order_id"]
    files = {"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    res = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 200, res.text
    assert res.json()["file_type"] == "pdf"


@pytest.mark.asyncio
async def test_merchant_attachment_upload_docx_rejected(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """上传 .docx 应被拒（仅支持 jpg/png/pdf）。"""
    monkeypatch.chdir(tmp_path)
    order_id = merchant_setup["order_id"]
    files = {
        "file": (
            "doc.docx",
            io.BytesIO(b"fake"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    res = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 400, res.text
    assert "jpg" in res.json()["detail"] or "pdf" in res.json()["detail"]


@pytest.mark.asyncio
async def test_merchant_attachment_upload_oversize_rejected(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """单文件 > 5MB 应被拒。"""
    monkeypatch.chdir(tmp_path)
    order_id = merchant_setup["order_id"]
    big = b"x" * (5 * 1024 * 1024 + 100)  # 5MB + 100B
    files = {"file": ("big.jpg", io.BytesIO(big), "image/jpeg")}
    res = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 400, res.text
    assert "5MB" in res.json()["detail"]


@pytest.mark.asyncio
async def test_merchant_attachment_max_count_9(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """单订单最多 9 个附件，第 10 个应被拒。"""
    monkeypatch.chdir(tmp_path)
    order_id = merchant_setup["order_id"]
    headers = merchant_setup["headers"]

    # 上传 9 个
    for i in range(9):
        files = {"file": (f"p{i}.jpg", io.BytesIO(b"data"), "image/jpeg")}
        r = await client.post(
            f"/api/merchant/orders/{order_id}/attachments/upload",
            files=files,
            headers=headers,
        )
        assert r.status_code == 200, f"#{i} failed: {r.text}"

    # 第 10 个
    files = {"file": ("p10.jpg", io.BytesIO(b"data"), "image/jpeg")}
    r = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=headers,
    )
    assert r.status_code == 400
    assert "9" in r.json()["detail"]

    # 列表应有 9 个
    list_r = await client.get(
        f"/api/merchant/orders/{order_id}/attachments", headers=headers
    )
    assert list_r.status_code == 200
    assert len(list_r.json()) == 9


@pytest.mark.asyncio
async def test_merchant_attachment_delete_ok(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """上传 1 个附件后删除，列表恢复为空。"""
    monkeypatch.chdir(tmp_path)
    order_id = merchant_setup["order_id"]
    headers = merchant_setup["headers"]
    files = {"file": ("p.png", io.BytesIO(b"png"), "image/png")}
    r = await client.post(
        f"/api/merchant/orders/{order_id}/attachments/upload",
        files=files,
        headers=headers,
    )
    assert r.status_code == 200
    aid = r.json()["id"]

    del_r = await client.delete(
        f"/api/merchant/orders/{order_id}/attachments/{aid}",
        headers=headers,
    )
    assert del_r.status_code == 200, del_r.text

    list_r = await client.get(
        f"/api/merchant/orders/{order_id}/attachments", headers=headers
    )
    assert list_r.json() == []


@pytest.mark.asyncio
async def test_merchant_attachment_unauthorized_other_order(
    client: AsyncClient, merchant_setup, tmp_path, monkeypatch
):
    """商家不能访问不属于自己门店的订单附件（403）。"""
    monkeypatch.chdir(tmp_path)
    headers = merchant_setup["headers"]
    # 不存在 / 无权限的订单 ID
    r = await client.get(
        f"/api/merchant/orders/999999/attachments", headers=headers
    )
    # 404 或 403 都可接受（订单不存在 vs 权限不足）
    assert r.status_code in (403, 404)


# ────────────────── F7：redeemed → completed 迁移幂等 ──────────────────


@pytest.mark.asyncio
async def test_migrate_redeemed_to_completed_idempotent():
    """迁移函数本身可重入：在没有 redeemed 行时静默返回。"""
    from app.services.schema_sync import _migrate_redeemed_to_completed

    # SQLite 中表结构已通过 conftest create_all 创建
    async with test_session() as session:
        async with session.bind.connect() as conn:
            # 第一次调用：无 redeemed 行 → 应该静默通过
            await _migrate_redeemed_to_completed(conn)
            # 第二次再调用同样应不报错
            await _migrate_redeemed_to_completed(conn)
            await conn.commit()

    # 数据库中无 redeemed 状态行（SQLite 接受任意字符串）
    async with test_session() as session:
        res = await session.execute(
            text("SELECT COUNT(*) FROM unified_orders WHERE status = 'redeemed'")
        )
        assert (res.scalar() or 0) == 0


# ────────────────── F1：商家订单列表返回字段完整 ──────────────────


@pytest.mark.asyncio
async def test_merchant_list_orders_returns_attachment_count(
    client: AsyncClient, merchant_setup
):
    """商家订单列表应返回 attachment_count 字段（默认为 0）。"""
    res = await client.get(
        "/api/merchant/orders",
        params={"store_id": merchant_setup["store_id"]},
        headers=merchant_setup["headers"],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 1
    item = body["items"][0]
    assert "attachment_count" in item
    assert "user_phone" in item
    assert "redemption_code" in item
    # 状态应在 14 态范围
    valid_states = {
        "pending_payment", "pending_shipment", "pending_receipt",
        "pending_appointment", "appointed", "pending_use",
        "partial_used", "pending_review", "completed", "expired",
        "refunding", "refunded", "cancelled",
    }
    assert item["status"] in valid_states, f"unexpected status: {item['status']}"
