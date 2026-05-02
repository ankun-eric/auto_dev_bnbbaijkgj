from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    AppointmentForm,
    AppointmentFormField,
    CheckinRecord,
    Coupon,
    CouponStatus,
    MerchantStore,
    OrderItem,
    OrderRedemption,
    Product,
    ProductCategory,
    ProductSku,
    ProductStore,
    RefundRequest,
    RefundRequestStatus,
    RefundStatusEnum,
    SystemConfig,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserCoupon,
)
from app.schemas.coupons import CouponCreate, CouponResponse, CouponUpdate, CouponDistributeRequest
from app.schemas.member_qr import CheckinConfigRequest, CheckinRecordResponse
from app.schemas.products import (
    AppointmentFormCreate,
    AppointmentFormFieldCreate,
    AppointmentFormFieldResponse,
    AppointmentFormFieldUpdate,
    AppointmentFormResponse,
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCreate,
    ProductResponse,
    ProductSkuResponse,
    ProductUpdate,
    SymptomTagResponse,
)
from app.schemas.store_bindding import (
    BatchBindRequest,
    BatchBindResponse,
    BoundCountResponse,
    BusinessScopeUpdate,
    ProductStoreBindRequest,
    ProductStoreCheckItem,
    ProductStoreResponse,
    SingleBindRequest,
    StoreBinddingProductItem,
    StoreBinddingStoreItem,
    StoreProductCheckItem,
    StoreRecommendResponse,
)
from app.schemas.timeout_policy import TimeoutPolicyResponse, TimeoutPolicyUpdate
from app.schemas.unified_orders import (
    RedemptionDetailItem,
    RefundActionRequest,
    RefundDetailResponse,
    RefundReasonItem,
    RefundRequestResponse,
    SalesStatisticsResponse,
    ShipRequest,
    TrendItem,
    UnifiedOrderResponse,
)

router = APIRouter(prefix="/api/admin", tags=["商品管理后台"])


# ─────────── 营销角标（v1.0 商品功能优化） ───────────

ALLOWED_MARKETING_BADGES = {"limited", "hot", "new", "recommend"}


def _normalize_badges(value) -> list[str]:
    """把数据库里可能是 JSON 字符串 / list / None 的 marketing_badges 归一化为 list[str]。

    非法值自动剔除，保持稳健（DB 中历史脏数据不会导致接口 500）。
    """
    import json as _json
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            value = _json.loads(value)
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen = set()
    for item in value:
        if isinstance(item, str) and item in ALLOWED_MARKETING_BADGES and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ─────────── 内部工具：SKU & Product 序列化 ───────────

async def _get_sku_order_flags(db: AsyncSession, sku_ids: list[int]) -> dict[int, bool]:
    """批量查询一组 sku_id 是否已被订单引用"""
    if not sku_ids:
        return {}
    result = await db.execute(
        select(OrderItem.sku_id, func.count(OrderItem.id))
        .where(OrderItem.sku_id.in_(sku_ids))
        .group_by(OrderItem.sku_id)
    )
    used_ids: dict[int, bool] = {row[0]: (row[1] or 0) > 0 for row in result.all()}
    return {sid: used_ids.get(sid, False) for sid in sku_ids}


async def _build_product_response_dict(db: AsyncSession, product: Product) -> dict:
    """把 Product ORM 对象 + 其 SKUs 组装成响应 dict（含 has_orders 标记）"""
    sku_result = await db.execute(
        select(ProductSku)
        .where(ProductSku.product_id == product.id)
        .order_by(ProductSku.sort_order.asc(), ProductSku.id.asc())
    )
    skus = list(sku_result.scalars().all())
    has_orders_map = await _get_sku_order_flags(db, [s.id for s in skus])

    sku_list: list[dict] = []
    for s in skus:
        sku_list.append({
            "id": s.id,
            "product_id": s.product_id,
            "spec_name": s.spec_name,
            "sale_price": float(s.sale_price or 0),
            "origin_price": float(s.origin_price) if s.origin_price is not None else None,
            "stock": s.stock or 0,
            "is_default": bool(s.is_default),
            "status": int(s.status or 1),
            "sort_order": s.sort_order or 0,
            "has_orders": bool(has_orders_map.get(s.id, False)),
        })

    status_val = product.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    ft = product.fulfillment_type
    if hasattr(ft, "value"):
        ft = ft.value
    am = product.appointment_mode
    if hasattr(am, "value"):
        am = am.value
    pam = product.purchase_appointment_mode
    if hasattr(pam, "value"):
        pam = pam.value

    # 条码反序列化（存储为 JSON）
    code_list = product.product_code_list
    if isinstance(code_list, str):
        import json
        try:
            code_list = json.loads(code_list)
        except Exception:
            code_list = []
    if not isinstance(code_list, list):
        code_list = []

    return {
        "id": product.id,
        "name": product.name,
        "category_id": product.category_id,
        "fulfillment_type": ft,
        "original_price": float(product.original_price) if product.original_price is not None else None,
        "sale_price": float(product.sale_price or 0),
        "images": product.images or [],
        "video_url": product.video_url or "",
        "description": product.description or "",
        "symptom_tags": product.symptom_tags or [],
        "stock": product.stock or 0,
        "points_exchangeable": bool(product.points_exchangeable),
        "points_price": product.points_price or 0,
        "points_deductible": bool(product.points_deductible),
        "redeem_count": product.redeem_count or 1,
        "appointment_mode": am or "none",
        "purchase_appointment_mode": pam,
        "custom_form_id": product.custom_form_id,
        "advance_days": product.advance_days,
        "daily_quota": product.daily_quota,
        "time_slots": product.time_slots or None,
        # BUG-PRODUCT-APPT-002：date / time_slot 共用「是否包含今天」
        "include_today": False if getattr(product, "include_today", True) is False else True,
        "faq": product.faq,
        "recommend_weight": product.recommend_weight or 0,
        "sales_count": product.sales_count or 0,
        "status": status_val or "draft",
        "sort_order": product.sort_order or 0,
        "payment_timeout_minutes": product.payment_timeout_minutes or 15,
        # v2 新字段
        "product_code_list": code_list,
        "spec_mode": int(product.spec_mode or 1),
        "main_video_url": product.main_video_url or "",
        "selling_point": product.selling_point or "",
        "description_rich": product.description_rich or "",
        "marketing_badges": _normalize_badges(product.marketing_badges),
        "skus": sku_list,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


async def _sync_skus_for_product(db: AsyncSession, product: Product, sku_items: list) -> None:
    """根据前端传入的 skus 列表，完成数据库 SKU 的增/删/改。
    - 有 id 的尝试编辑（若被订单引用则只允许修改 stock/origin_price/status/sort_order）
    - 无 id 的视为新增
    - 未出现在列表中的旧 SKU：
        * 未被订单引用 → 物理删除
        * 已被订单引用 → 仅将 status 置为 2（停用），不删除
    - 确保仅 1 条 is_default=True，如全无则自动把第一条置为默认
    """
    if sku_items is None:
        return

    old_result = await db.execute(
        select(ProductSku).where(ProductSku.product_id == product.id)
    )
    old_skus = {s.id: s for s in old_result.scalars().all()}

    used_map = await _get_sku_order_flags(db, list(old_skus.keys()))

    incoming_ids = {int(item.id) for item in sku_items if getattr(item, "id", None)}

    # 1) 处理未在新列表中的旧 SKU
    for old_id, old_sku in list(old_skus.items()):
        if old_id not in incoming_ids:
            if used_map.get(old_id, False):
                old_sku.status = 2  # 停用
            else:
                await db.delete(old_sku)

    # 2) 处理新列表中的每一条
    default_count = 0
    new_rows: list[ProductSku] = []
    for idx, item in enumerate(sku_items):
        if getattr(item, "id", None) and int(item.id) in old_skus:
            sku = old_skus[int(item.id)]
            is_used = used_map.get(sku.id, False)
            if is_used:
                # 锁定 spec_name/sale_price/is_default；允许修改 stock/origin_price/status/sort_order
                sku.stock = int(item.stock or 0)
                sku.origin_price = item.origin_price
                sku.status = int(item.status or 1)
                sku.sort_order = idx
            else:
                sku.spec_name = item.spec_name
                sku.sale_price = item.sale_price
                sku.origin_price = item.origin_price
                sku.stock = int(item.stock or 0)
                sku.is_default = bool(item.is_default)
                sku.status = int(item.status or 1)
                sku.sort_order = idx
            if sku.is_default:
                default_count += 1
            new_rows.append(sku)
        else:
            sku = ProductSku(
                product_id=product.id,
                spec_name=item.spec_name,
                sale_price=item.sale_price,
                origin_price=item.origin_price,
                stock=int(item.stock or 0),
                is_default=bool(item.is_default),
                status=int(item.status or 1),
                sort_order=idx,
            )
            db.add(sku)
            if item.is_default:
                default_count += 1
            new_rows.append(sku)

    await db.flush()

    # 3) 处理默认规格：必须有且仅有 1 条
    if new_rows and default_count != 1:
        # 全部清空，再把第一条（或第一条启用的）置为默认
        for s in new_rows:
            s.is_default = False
        # 优先选 status=1（启用）的第一条
        first_enable = next((s for s in new_rows if int(s.status or 1) == 1), new_rows[0])
        first_enable.is_default = True
        await db.flush()


def _build_product_payload_from_data(data) -> dict:
    """从 ProductCreate/ProductUpdate 中提取用于写入 Product 表的字段（不含 store_ids/skus）"""
    d = data.model_dump(exclude_unset=True)
    d.pop("store_ids", None)
    d.pop("skus", None)
    return d

# ─────────── 分类管理 ───────────


@router.get("/products/categories")
async def admin_list_categories(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductCategory).order_by(ProductCategory.level.asc(), ProductCategory.sort_order.asc())
    )
    items = [ProductCategoryResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


@router.post("/products/categories")
async def admin_create_category(
    data: ProductCategoryCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if data.parent_id:
        parent_result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == data.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="父分类不存在")
        data.level = 2
    else:
        data.level = 1

    cat = ProductCategory(
        name=data.name,
        parent_id=data.parent_id,
        icon=data.icon,
        description=data.description,
        sort_order=data.sort_order,
        status=data.status,
        level=data.level,
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return ProductCategoryResponse.model_validate(cat)


@router.put("/products/categories/{category_id}")
async def admin_update_category(
    category_id: int,
    data: ProductCategoryUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cat, key, value)

    await db.flush()
    await db.refresh(cat)
    return ProductCategoryResponse.model_validate(cat)


@router.delete("/products/categories/{category_id}")
async def admin_delete_category(
    category_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")

    children_result = await db.execute(
        select(func.count(ProductCategory.id)).where(ProductCategory.parent_id == category_id)
    )
    if children_result.scalar() > 0:
        raise HTTPException(status_code=400, detail="请先删除子分类")

    products_result = await db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    if products_result.scalar() > 0:
        raise HTTPException(status_code=400, detail="该分类下有商品，无法删除")

    await db.delete(cat)
    return {"message": "分类已删除"}


@router.post("/products/categories/reorder")
async def admin_reorder_categories(
    payload: dict,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """同级拖拽排序：在指定 parent_id 范围内，按 ordered_ids 顺序写入 sort_order = 0,1,2,…"""
    parent_id = payload.get("parent_id")
    ordered_ids = payload.get("ordered_ids") or []
    if not isinstance(ordered_ids, list):
        raise HTTPException(status_code=400, detail="ordered_ids 必须为数组")
    if not ordered_ids:
        return {"message": "排序已更新"}

    where_clause = (
        ProductCategory.parent_id.is_(None)
        if parent_id in (None, 0)
        else ProductCategory.parent_id == parent_id
    )
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id.in_(ordered_ids),
            where_clause,
        )
    )
    cats = result.scalars().all()
    cat_map = {c.id: c for c in cats}

    for index, cat_id in enumerate(ordered_ids):
        cat = cat_map.get(int(cat_id))
        if cat is not None:
            cat.sort_order = index

    await db.flush()
    return {"message": "排序已更新", "updated_count": len(cat_map)}


# ─────────── 商品管理 ───────────


@router.get("/products")
async def admin_list_products(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    count_query = select(func.count(Product.id))

    if status:
        query = query.where(Product.status == status)
        count_query = count_query.where(Product.status == status)
    if category_id:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(Product.name.like(kw))
        count_query = count_query.where(Product.name.like(kw))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Product.sort_order.asc(), Product.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    products = list(result.scalars().all())
    items = [await _build_product_response_dict(db, p) for p in products]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/products/{product_id}/detail")
async def admin_get_product_detail(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """获取商品详细信息（含 SKU 与订单引用标记），用于编辑弹窗"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return await _build_product_response_dict(db, product)


@router.post("/products")
async def admin_create_product(
    data: ProductCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cat_result = await db.execute(
        select(ProductCategory).where(ProductCategory.id == data.category_id)
    )
    if not cat_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="分类不存在")

    # 条码限制：最多 10 个，每个 ≤ 30 字符
    code_list = data.product_code_list or []
    if len(code_list) > 10:
        raise HTTPException(status_code=400, detail="产品条码最多 10 个")
    for c in code_list:
        if len(str(c)) > 30:
            raise HTTPException(status_code=400, detail="单个条码长度不可超过 30 字符")

    # 卖点长度限制 100
    if data.selling_point and len(data.selling_point) > 100:
        raise HTTPException(status_code=400, detail="商品卖点不能超过 100 字")

    # 保存并上架强校验
    if data.status == "active":
        _validate_for_publish(data)

    product = Product(
        name=data.name,
        category_id=data.category_id,
        fulfillment_type=data.fulfillment_type,
        original_price=data.original_price,
        sale_price=data.sale_price,
        images=data.images,
        video_url=data.video_url,
        description=data.description,
        symptom_tags=data.symptom_tags,
        stock=data.stock,
        points_exchangeable=data.points_exchangeable,
        points_price=data.points_price,
        points_deductible=data.points_deductible,
        redeem_count=data.redeem_count,
        appointment_mode=data.appointment_mode,
        purchase_appointment_mode=data.purchase_appointment_mode,
        custom_form_id=data.custom_form_id,
        advance_days=data.advance_days,
        daily_quota=data.daily_quota,
        time_slots=[s.model_dump() for s in data.time_slots] if data.time_slots else None,
        # BUG-PRODUCT-APPT-002：include_today 默认 true
        include_today=False if getattr(data, "include_today", True) is False else True,
        faq=data.faq,
        recommend_weight=data.recommend_weight,
        status=data.status,
        sort_order=data.sort_order,
        payment_timeout_minutes=data.payment_timeout_minutes,
        # v2 新字段
        product_code_list=code_list,
        spec_mode=int(data.spec_mode or 1),
        main_video_url=data.main_video_url,
        selling_point=data.selling_point,
        description_rich=data.description_rich,
        marketing_badges=data.marketing_badges if data.marketing_badges is not None else [],
    )
    db.add(product)
    await db.flush()

    if data.store_ids:
        for store_id in data.store_ids:
            ps = ProductStore(product_id=product.id, store_id=store_id)
            db.add(ps)
        await db.flush()

    # 多规格模式下：同步 skus
    if int(data.spec_mode or 1) == 2 and data.skus:
        await _sync_skus_for_product(db, product, data.skus)

    await db.refresh(product)
    return await _build_product_response_dict(db, product)


def _validate_for_publish(data) -> None:
    """保存并上架强校验：图片 ≥ 1、库存 > 0（统一规格）或 ≥1 条 SKU 库存 > 0、多规格需有默认"""
    images = data.images or []
    if not images:
        raise HTTPException(status_code=400, detail="上架必须至少上传 1 张商品图片")

    spec_mode = int(getattr(data, "spec_mode", 1) or 1)
    if spec_mode == 1:
        if (data.stock or 0) <= 0:
            raise HTTPException(status_code=400, detail="上架必须库存大于 0")
    else:
        skus = data.skus or []
        if not skus:
            raise HTTPException(status_code=400, detail="多规格商品必须至少 1 条规格")
        if not any((s.stock or 0) > 0 for s in skus):
            raise HTTPException(status_code=400, detail="多规格商品必须至少 1 条规格库存大于 0")
        if not any(s.is_default for s in skus):
            raise HTTPException(status_code=400, detail="多规格商品必须有 1 条默认规格")

    # 原价必须 ≥ 售价（若填了）
    if data.original_price is not None and data.sale_price is not None:
        if data.original_price and data.sale_price and data.original_price < data.sale_price:
            raise HTTPException(status_code=400, detail="原价必须大于等于售价")


@router.put("/products/{product_id}")
async def admin_update_product(
    product_id: int,
    data: ProductUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 条码校验
    if data.product_code_list is not None:
        if len(data.product_code_list) > 10:
            raise HTTPException(status_code=400, detail="产品条码最多 10 个")
        for c in data.product_code_list:
            if len(str(c)) > 30:
                raise HTTPException(status_code=400, detail="单个条码长度不可超过 30 字符")
    if data.selling_point and len(data.selling_point) > 100:
        raise HTTPException(status_code=400, detail="商品卖点不能超过 100 字")

    # 组合后的"虚拟数据对象"用于上架强校验
    if data.status == "active":
        class _P:
            pass
        eff = _P()
        eff.images = data.images if data.images is not None else product.images
        eff.stock = data.stock if data.stock is not None else product.stock
        eff.spec_mode = int(data.spec_mode if data.spec_mode is not None else (product.spec_mode or 1))
        eff.original_price = data.original_price if data.original_price is not None else (float(product.original_price) if product.original_price is not None else None)
        eff.sale_price = data.sale_price if data.sale_price is not None else float(product.sale_price or 0)
        if data.skus is not None:
            eff.skus = data.skus
        else:
            # 从数据库读取现有 skus
            sku_rows = await db.execute(select(ProductSku).where(ProductSku.product_id == product.id))
            existing_skus = list(sku_rows.scalars().all())
            eff.skus = [
                type("S", (), {
                    "stock": s.stock,
                    "is_default": s.is_default,
                })()
                for s in existing_skus
            ]
        _validate_for_publish(eff)

    update_data = data.model_dump(exclude_unset=True)
    store_ids = update_data.pop("store_ids", None)
    skus_input = update_data.pop("skus", None)
    # time_slots 已经在 model_dump 中序列化为 list[dict]；直接赋值即可

    for key, value in update_data.items():
        setattr(product, key, value)

    if store_ids is not None:
        existing = await db.execute(
            select(ProductStore).where(ProductStore.product_id == product_id)
        )
        for ps in existing.scalars().all():
            await db.delete(ps)
        for store_id in store_ids:
            ps = ProductStore(product_id=product_id, store_id=store_id)
            db.add(ps)

    # 同步 SKU
    if skus_input is not None:
        await _sync_skus_for_product(db, product, data.skus or [])

    # 如果切换回统一规格，清空启用中的规格（未被订单引用的删除，被引用的设置停用）
    if int(product.spec_mode or 1) == 1 and skus_input is not None and len(skus_input) == 0:
        pass  # 已在 _sync_skus_for_product 内处理（传空列表时）

    await db.flush()
    await db.refresh(product)
    return await _build_product_response_dict(db, product)


# ─────────── 规格管理（独立接口） ───────────


@router.get("/products/{product_id}/skus")
async def admin_list_product_skus(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """查询商品规格清单（含 has_orders 标记）"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    sku_result = await db.execute(
        select(ProductSku)
        .where(ProductSku.product_id == product_id)
        .order_by(ProductSku.sort_order.asc(), ProductSku.id.asc())
    )
    skus = list(sku_result.scalars().all())
    has_orders_map = await _get_sku_order_flags(db, [s.id for s in skus])

    items = []
    for s in skus:
        items.append({
            "id": s.id,
            "product_id": s.product_id,
            "spec_name": s.spec_name,
            "sale_price": float(s.sale_price or 0),
            "origin_price": float(s.origin_price) if s.origin_price is not None else None,
            "stock": s.stock or 0,
            "is_default": bool(s.is_default),
            "status": int(s.status or 1),
            "sort_order": s.sort_order or 0,
            "has_orders": bool(has_orders_map.get(s.id, False)),
        })
    return {"items": items}


@router.get("/skus/{sku_id}/used")
async def admin_check_sku_used(
    sku_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """判断某一规格是否被订单引用"""
    result = await db.execute(
        select(func.count(OrderItem.id)).where(OrderItem.sku_id == sku_id)
    )
    count = result.scalar() or 0
    return {"sku_id": sku_id, "has_orders": count > 0, "order_count": count}


@router.delete("/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    order_items_result = await db.execute(
        select(func.count(OrderItem.id)).where(OrderItem.product_id == product_id)
    )
    if order_items_result.scalar() > 0:
        raise HTTPException(status_code=400, detail="该商品已有订单，无法删除，请下架处理")

    stores_result = await db.execute(
        select(ProductStore).where(ProductStore.product_id == product_id)
    )
    for ps in stores_result.scalars().all():
        await db.delete(ps)

    await db.delete(product)
    return {"message": "商品已删除"}


# ─────────── 预约表单字段 ───────────


@router.get("/products/{product_id}/form-fields")
async def admin_list_form_fields(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # BUG-PRODUCT-APPT-001：收敛"未绑定自动建表单"的潜规则
    # 改为：未绑定则直接返回空 + 提示，由前端引导去预约表单库显式创建或选择
    if not product.custom_form_id:
        return {
            "items": [],
            "form_id": None,
            "message": "该商品尚未绑定预约表单，请到「预约表单库」新建或在商品编辑中选择一张表单",
        }

    fields_result = await db.execute(
        select(AppointmentFormField)
        .where(AppointmentFormField.form_id == product.custom_form_id)
        .order_by(AppointmentFormField.sort_order.asc())
    )
    items = [AppointmentFormFieldResponse.model_validate(f) for f in fields_result.scalars().all()]
    return {"items": items, "form_id": product.custom_form_id}


@router.post("/products/{product_id}/form-fields")
async def admin_create_form_field(
    product_id: int,
    data: AppointmentFormFieldCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    if not product.custom_form_id:
        raise HTTPException(
            status_code=400,
            detail="该商品尚未绑定预约表单，请先在「预约表单库」新建表单并在商品编辑中选择",
        )

    field = AppointmentFormField(
        form_id=product.custom_form_id,
        field_type=data.field_type,
        label=data.label,
        placeholder=data.placeholder,
        required=data.required,
        options=data.options,
        sort_order=data.sort_order,
    )
    db.add(field)
    await db.flush()
    await db.refresh(field)
    return AppointmentFormFieldResponse.model_validate(field)


@router.put("/products/{product_id}/form-fields/{field_id}")
async def admin_update_form_field(
    product_id: int,
    field_id: int,
    data: AppointmentFormFieldUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AppointmentFormField).where(AppointmentFormField.id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(field, key, value)

    await db.flush()
    await db.refresh(field)
    return AppointmentFormFieldResponse.model_validate(field)


@router.delete("/products/{product_id}/form-fields/{field_id}")
async def admin_delete_form_field(
    product_id: int,
    field_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AppointmentFormField).where(AppointmentFormField.id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    await db.delete(field)
    return {"message": "字段已删除"}


# ─────────── 订单管理 ───────────


@router.get("/orders/unified")
async def admin_list_unified_orders(
    status: Optional[str] = None,
    refund_status: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_method: Optional[str] = None,
    category_id: Optional[int] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(UnifiedOrder)
    count_query = select(func.count(UnifiedOrder.id))

    if status:
        query = query.where(UnifiedOrder.status == status)
        count_query = count_query.where(UnifiedOrder.status == status)
    if refund_status:
        if refund_status in ("all_refund", "all"):
            query = query.where(UnifiedOrder.refund_status != "none")
            count_query = count_query.where(UnifiedOrder.refund_status != "none")
        elif "," in refund_status:
            rs_values = [v.strip() for v in refund_status.split(",") if v.strip()]
            if rs_values:
                query = query.where(UnifiedOrder.refund_status.in_(rs_values))
                count_query = count_query.where(UnifiedOrder.refund_status.in_(rs_values))
        else:
            query = query.where(UnifiedOrder.refund_status == refund_status)
            count_query = count_query.where(UnifiedOrder.refund_status == refund_status)
    if keyword:
        kw = f"%{keyword}%"
        user_subq = select(User.id).where(
            (User.nickname.like(kw)) | (User.phone.like(kw))
        ).scalar_subquery()
        keyword_filter = (UnifiedOrder.order_no.like(kw)) | (UnifiedOrder.user_id.in_(user_subq))
        query = query.where(keyword_filter)
        count_query = count_query.where(keyword_filter)
    if start_date:
        query = query.where(UnifiedOrder.created_at >= start_date)
        count_query = count_query.where(UnifiedOrder.created_at >= start_date)
    if end_date:
        query = query.where(UnifiedOrder.created_at <= end_date)
        count_query = count_query.where(UnifiedOrder.created_at <= end_date)
    if payment_method:
        query = query.where(UnifiedOrder.payment_method == payment_method)
        count_query = count_query.where(UnifiedOrder.payment_method == payment_method)
    if min_amount is not None:
        query = query.where(UnifiedOrder.paid_amount >= min_amount)
        count_query = count_query.where(UnifiedOrder.paid_amount >= min_amount)
    if max_amount is not None:
        query = query.where(UnifiedOrder.paid_amount <= max_amount)
        count_query = count_query.where(UnifiedOrder.paid_amount <= max_amount)
    if category_id:
        product_ids_subq = select(Product.id).where(Product.category_id == category_id).scalar_subquery()
        order_ids_subq = select(OrderItem.order_id).where(
            OrderItem.product_id.in_(product_ids_subq)
        ).distinct().scalar_subquery()
        query = query.where(UnifiedOrder.id.in_(order_ids_subq))
        count_query = count_query.where(UnifiedOrder.id.in_(order_ids_subq))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(UnifiedOrder.items))
        .order_by(UnifiedOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = result.scalars().all()
    items = []
    for o in orders:
        resp = UnifiedOrderResponse.model_validate(o)
        s = o.status
        if hasattr(s, "value"):
            s = s.value
        rs = o.refund_status
        if hasattr(rs, "value"):
            rs = rs.value
        if s == "cancelled" and rs == "refund_success":
            resp.status_display = "已取消（已退款）"
        items.append(resp)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/orders/unified/{order_id}/ship")
async def admin_ship_order(
    order_id: int,
    data: ShipRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "pending_shipment":
        raise HTTPException(status_code=400, detail="该订单无法发货")

    order.tracking_company = data.tracking_company
    order.tracking_number = data.tracking_number
    order.shipped_at = datetime.utcnow()
    order.status = UnifiedOrderStatus.pending_receipt
    order.updated_at = datetime.utcnow()

    return {"message": "发货成功"}


@router.post("/orders/unified/{order_id}/refund/approve")
async def admin_approve_refund(
    order_id: int,
    data: RefundActionRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    refund_result = await db.execute(
        select(RefundRequest)
        .where(RefundRequest.order_id == order_id, RefundRequest.status == RefundRequestStatus.pending)
        .order_by(RefundRequest.created_at.desc())
    )
    refund_req = refund_result.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    refund_req.status = RefundRequestStatus.approved
    refund_req.admin_user_id = current_user.id
    refund_req.admin_notes = data.admin_notes
    if data.refund_amount is not None:
        refund_req.refund_amount_approved = data.refund_amount
    else:
        refund_req.refund_amount_approved = refund_req.refund_amount
    refund_req.updated_at = datetime.utcnow()

    order_result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.refund_status = RefundStatusEnum.refund_success
        order.status = UnifiedOrderStatus.cancelled
        order.cancelled_at = datetime.utcnow()
        order.updated_at = datetime.utcnow()

    return {"message": "退款已批准", "refund_amount_approved": float(refund_req.refund_amount_approved)}


@router.post("/orders/unified/{order_id}/refund/reject")
async def admin_reject_refund(
    order_id: int,
    data: RefundActionRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    refund_result = await db.execute(
        select(RefundRequest)
        .where(RefundRequest.order_id == order_id, RefundRequest.status == RefundRequestStatus.pending)
        .order_by(RefundRequest.created_at.desc())
    )
    refund_req = refund_result.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    refund_req.status = RefundRequestStatus.rejected
    refund_req.admin_user_id = current_user.id
    refund_req.admin_notes = data.admin_notes
    refund_req.updated_at = datetime.utcnow()

    order_result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.refund_status = RefundStatusEnum.rejected
        order.updated_at = datetime.utcnow()

    return {"message": "退款已拒绝"}


@router.get("/orders/unified/{order_id}/refund-detail", response_model=RefundDetailResponse)
async def admin_get_refund_detail(
    order_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    refund_result = await db.execute(
        select(RefundRequest)
        .where(RefundRequest.order_id == order_id)
        .order_by(RefundRequest.created_at.desc())
    )
    refund_req = refund_result.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    order_result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    item_ids = [item.id for item in order.items]
    used_redeem_count = sum(item.used_redeem_count for item in order.items)
    total_redeem_count = sum(item.total_redeem_count for item in order.items)

    redemptions_list = []
    if item_ids:
        redemption_result = await db.execute(
            select(OrderRedemption, User.nickname, MerchantStore.store_name)
            .outerjoin(User, OrderRedemption.redeemed_by_user_id == User.id)
            .outerjoin(MerchantStore, OrderRedemption.store_id == MerchantStore.id)
            .where(OrderRedemption.order_item_id.in_(item_ids))
            .order_by(OrderRedemption.redeemed_at.asc())
        )
        for row in redemption_result.all():
            redemption, nickname, store_name = row
            redemptions_list.append(RedemptionDetailItem(
                id=redemption.id,
                order_item_id=redemption.order_item_id,
                redeemed_at=redemption.redeemed_at,
                store_name=store_name,
                redeemed_by_name=nickname,
            ))

    ratio = f"{round(used_redeem_count / total_redeem_count * 100)}%" if total_redeem_count > 0 else "0%"

    return RefundDetailResponse(
        refund_request=RefundRequestResponse.model_validate(refund_req),
        has_redemption=refund_req.has_redemption,
        used_redeem_count=used_redeem_count,
        total_redeem_count=total_redeem_count,
        redemption_ratio=ratio,
        redemptions=redemptions_list,
        paid_amount=float(order.paid_amount),
    )


# ─────────── 优惠券管理 ───────────


@router.get("/coupons")
async def admin_list_coupons(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Coupon)
    count_query = select(func.count(Coupon.id))

    if status:
        query = query.where(Coupon.status == status)
        count_query = count_query.where(Coupon.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Coupon.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CouponResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/coupons")
async def admin_create_coupon(
    data: CouponCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    coupon = Coupon(
        name=data.name,
        type=data.type,
        condition_amount=data.condition_amount,
        discount_value=data.discount_value,
        discount_rate=data.discount_rate,
        scope=data.scope,
        scope_ids=data.scope_ids,
        total_count=data.total_count,
        valid_start=data.valid_start,
        valid_end=data.valid_end,
        status=data.status,
    )
    db.add(coupon)
    await db.flush()
    await db.refresh(coupon)
    return CouponResponse.model_validate(coupon)


@router.put("/coupons/{coupon_id}")
async def admin_update_coupon(
    coupon_id: int,
    data: CouponUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(coupon, key, value)

    await db.flush()
    await db.refresh(coupon)
    return CouponResponse.model_validate(coupon)


# V2.1：DELETE /api/admin/coupons/{id} 已**移除**。
# 优惠券一律不可物理删除，请改用 POST /api/admin/coupons/{id}/offline（仅超管）。
@router.delete("/coupons/{coupon_id}")
async def admin_delete_coupon_removed(coupon_id: int):
    raise HTTPException(
        status_code=405,
        detail="该接口已下线，请使用 POST /api/admin/coupons/{id}/offline 进行下架（仅超级管理员）",
    )


@router.post("/coupons/{coupon_id}/distribute")
async def admin_distribute_coupon(
    coupon_id: int,
    data: CouponDistributeRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    coupon_result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = coupon_result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    distributed = 0
    for user_id in data.user_ids:
        existing = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == user_id, UserCoupon.coupon_id == coupon_id
            )
        )
        if existing.scalar_one_or_none():
            continue

        uc = UserCoupon(user_id=user_id, coupon_id=coupon_id)
        db.add(uc)
        coupon.claimed_count += 1
        distributed += 1

    return {"message": f"成功发放给 {distributed} 个用户"}


# ─────────── 销量统计 ───────────


@router.get("/statistics/sales")
async def admin_sales_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    base_filter = UnifiedOrder.status != "cancelled"

    query = select(
        func.count(UnifiedOrder.id).label("total_orders"),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0).label("total_revenue"),
    ).where(base_filter)
    if start_date:
        query = query.where(UnifiedOrder.created_at >= start_date)
    if end_date:
        query = query.where(UnifiedOrder.created_at <= end_date)
    result = await db.execute(query)
    row = result.one()

    items_query = select(
        func.coalesce(func.sum(OrderItem.quantity), 0)
    ).join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id).where(base_filter)
    if start_date:
        items_query = items_query.where(UnifiedOrder.created_at >= start_date)
    if end_date:
        items_query = items_query.where(UnifiedOrder.created_at <= end_date)
    items_result = await db.execute(items_query)
    total_products_sold = items_result.scalar() or 0

    refund_query = select(
        func.count(UnifiedOrder.id),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0),
    ).where(UnifiedOrder.refund_status == RefundStatusEnum.refund_success)
    if start_date:
        refund_query = refund_query.where(UnifiedOrder.created_at >= start_date)
    if end_date:
        refund_query = refund_query.where(UnifiedOrder.created_at <= end_date)
    refund_result = await db.execute(refund_query)
    refund_row = refund_result.one()

    today = date.today()
    today_start = datetime(today.year, today.month, today.day)
    today_end = today_start + timedelta(days=1)

    today_query = select(
        func.count(UnifiedOrder.id),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0),
    ).where(base_filter, UnifiedOrder.created_at >= today_start, UnifiedOrder.created_at < today_end)
    today_result = await db.execute(today_query)
    today_row = today_result.one()

    today_refund_query = select(
        func.count(UnifiedOrder.id),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0),
    ).where(
        UnifiedOrder.refund_status == RefundStatusEnum.refund_success,
        UnifiedOrder.created_at >= today_start,
        UnifiedOrder.created_at < today_end,
    )
    today_refund_result = await db.execute(today_refund_query)
    today_refund_row = today_refund_result.one()

    month_start = datetime(today.year, today.month, 1)
    if today.month == 12:
        month_end = datetime(today.year + 1, 1, 1)
    else:
        month_end = datetime(today.year, today.month + 1, 1)

    month_query = select(
        func.count(UnifiedOrder.id),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0),
    ).where(base_filter, UnifiedOrder.created_at >= month_start, UnifiedOrder.created_at < month_end)
    month_result = await db.execute(month_query)
    month_row = month_result.one()

    month_refund_query = select(
        func.count(UnifiedOrder.id),
        func.coalesce(func.sum(UnifiedOrder.paid_amount), 0),
    ).where(
        UnifiedOrder.refund_status == RefundStatusEnum.refund_success,
        UnifiedOrder.created_at >= month_start,
        UnifiedOrder.created_at < month_end,
    )
    month_refund_result = await db.execute(month_refund_query)
    month_refund_row = month_refund_result.one()

    return SalesStatisticsResponse(
        total_orders=row.total_orders,
        total_revenue=float(row.total_revenue),
        total_products_sold=total_products_sold,
        total_refund_count=refund_row[0],
        total_refund_amount=float(refund_row[1]),
        today_orders=today_row[0],
        today_revenue=float(today_row[1]),
        today_refund_count=today_refund_row[0],
        today_refund_amount=float(today_refund_row[1]),
        month_orders=month_row[0],
        month_revenue=float(month_row[1]),
        month_refund_count=month_refund_row[0],
        month_refund_amount=float(month_refund_row[1]),
    )


@router.get("/statistics/trends")
async def admin_statistics_trends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if not start_date:
        start_dt = date.today() - timedelta(days=29)
    else:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    if not end_date:
        end_dt = date.today()
    else:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

    order_date = cast(UnifiedOrder.created_at, Date)

    order_query = (
        select(
            order_date.label("d"),
            func.count(UnifiedOrder.id).label("cnt"),
            func.coalesce(func.sum(UnifiedOrder.paid_amount), 0).label("rev"),
        )
        .where(
            UnifiedOrder.status != "cancelled",
            UnifiedOrder.created_at >= datetime(start_dt.year, start_dt.month, start_dt.day),
            UnifiedOrder.created_at < datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1),
        )
        .group_by(order_date)
    )
    order_result = await db.execute(order_query)
    order_rows = {str(r.d): (r.cnt, float(r.rev)) for r in order_result.all()}

    refund_query = (
        select(
            order_date.label("d"),
            func.coalesce(func.sum(UnifiedOrder.paid_amount), 0).label("ref_amt"),
        )
        .where(
            UnifiedOrder.refund_status == RefundStatusEnum.refund_success,
            UnifiedOrder.created_at >= datetime(start_dt.year, start_dt.month, start_dt.day),
            UnifiedOrder.created_at < datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1),
        )
        .group_by(order_date)
    )
    refund_result = await db.execute(refund_query)
    refund_rows = {str(r.d): float(r.ref_amt) for r in refund_result.all()}

    trends = []
    current = start_dt
    while current <= end_dt:
        ds = str(current)
        cnt, rev = order_rows.get(ds, (0, 0.0))
        ref = refund_rows.get(ds, 0.0)
        trends.append(TrendItem(date=ds, order_count=cnt, revenue=rev, refund_amount=ref))
        current += timedelta(days=1)

    return {"items": trends}


@router.get("/statistics/refund-reasons")
async def admin_refund_reasons(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            RefundRequest.reason,
            func.count(RefundRequest.id).label("cnt"),
        )
        .where(RefundRequest.reason.isnot(None), RefundRequest.reason != "")
        .group_by(RefundRequest.reason)
        .order_by(func.count(RefundRequest.id).desc())
    )
    result = await db.execute(query)
    items = [RefundReasonItem(reason=r.reason or "未填写", count=r.cnt) for r in result.all()]
    return {"items": items}


# ─────────── 进店记录 ───────────


@router.get("/checkin-records")
async def admin_list_checkin_records(
    store_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(CheckinRecord)
    count_query = select(func.count(CheckinRecord.id))

    if store_id:
        query = query.where(CheckinRecord.store_id == store_id)
        count_query = count_query.where(CheckinRecord.store_id == store_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(CheckinRecord.checked_in_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = result.scalars().all()

    items = []
    for r in records:
        user_res = await db.execute(select(User).where(User.id == r.user_id))
        user = user_res.scalar_one_or_none()
        store_res = await db.execute(select(MerchantStore).where(MerchantStore.id == r.store_id))
        store = store_res.scalar_one_or_none()

        items.append(CheckinRecordResponse(
            id=r.id,
            user_id=r.user_id,
            store_id=r.store_id,
            staff_user_id=r.staff_user_id,
            points_earned=r.points_earned,
            checked_in_at=r.checked_in_at,
            user_nickname=user.nickname if user else None,
            user_phone=user.phone if user else None,
            store_name=store.store_name if store else None,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ─────────── 签到积分配置 ───────────


@router.post("/checkin-config")
async def admin_set_checkin_config(
    data: CheckinConfigRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "checkin_points_per_visit")
    )
    config = result.scalar_one_or_none()
    if config:
        config.config_value = str(data.points_per_checkin)
    else:
        config = SystemConfig(
            config_key="checkin_points_per_visit",
            config_value=str(data.points_per_checkin),
            config_type="points",
            description="到店签到积分",
        )
        db.add(config)

    result2 = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "checkin_daily_limit")
    )
    config2 = result2.scalar_one_or_none()
    if config2:
        config2.config_value = str(data.daily_limit)
    else:
        config2 = SystemConfig(
            config_key="checkin_daily_limit",
            config_value=str(data.daily_limit),
            config_type="points",
            description="每日签到次数限制",
        )
        db.add(config2)

    return {"message": "配置已更新"}


# ─────────── 症状标签库 ───────────


@router.get("/symptom-tags")
async def admin_list_symptom_tags(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product.symptom_tags).where(Product.symptom_tags.isnot(None))
    )
    all_tags: dict[str, int] = {}
    for row in result.scalars().all():
        if isinstance(row, list):
            for tag in row:
                all_tags[tag] = all_tags.get(tag, 0) + 1

    items = [SymptomTagResponse(tag=k, count=v) for k, v in sorted(all_tags.items(), key=lambda x: -x[1])]
    return {"items": items}


# ─────────── 门店推荐与商品绑定 ───────────


@router.get("/stores/recommend")
async def admin_recommend_stores(
    product_category_id: int = Query(...),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    seen: dict[int, StoreRecommendResponse] = {}

    scope_result = await db.execute(
        select(MerchantStore).where(MerchantStore.status == "active")
    )
    for store in scope_result.scalars().all():
        bs = store.business_scope
        if isinstance(bs, list) and product_category_id in bs:
            seen[store.id] = StoreRecommendResponse(
                id=store.id,
                store_name=store.store_name,
                store_code=store.store_code,
                address=store.address,
                match_type="business_scope",
            )

    sold_subq = (
        select(ProductStore.store_id)
        .join(Product, Product.id == ProductStore.product_id)
        .where(Product.category_id == product_category_id)
        .distinct()
    )
    sold_result = await db.execute(
        select(MerchantStore).where(
            MerchantStore.id.in_(sold_subq),
            MerchantStore.status == "active",
        )
    )
    for store in sold_result.scalars().all():
        if store.id not in seen:
            seen[store.id] = StoreRecommendResponse(
                id=store.id,
                store_name=store.store_name,
                store_code=store.store_code,
                address=store.address,
                match_type="history_sale",
            )

    return {"items": list(seen.values())}


@router.put("/products/{product_id}/stores")
async def admin_update_product_stores(
    product_id: int,
    data: ProductStoreBindRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="商品不存在")

    existing = await db.execute(
        select(ProductStore).where(ProductStore.product_id == product_id)
    )
    for ps in existing.scalars().all():
        await db.delete(ps)

    for store_id in data.store_ids:
        db.add(ProductStore(product_id=product_id, store_id=store_id))

    await db.flush()
    return {"message": "门店绑定已更新"}


@router.get("/products/{product_id}/stores")
async def admin_get_product_stores(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductStore, MerchantStore)
        .join(MerchantStore, MerchantStore.id == ProductStore.store_id)
        .where(ProductStore.product_id == product_id)
    )
    items = []
    for ps, store in result.all():
        items.append(ProductStoreResponse(
            store_id=store.id,
            store_name=store.store_name,
            store_code=store.store_code,
            address=store.address,
        ))
    return {"items": items}


@router.put("/stores/{store_id}/business-scope")
async def admin_update_store_business_scope(
    store_id: int,
    data: BusinessScopeUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    store.business_scope = data.business_scope
    await db.flush()
    return {"message": "经营范围已更新"}


# ─────────── 超时策略 ───────────


_TIMEOUT_KEYS = {
    "urge_minutes": ("order_urge_minutes", "30"),
    "timeout_minutes": ("order_timeout_minutes", "60"),
    "timeout_action": ("order_timeout_action", "auto_cancel"),
    "reminder_advance_hours": ("appointment_reminder_advance_hours", "24"),
}


async def _get_timeout_policy(db: AsyncSession) -> TimeoutPolicyResponse:
    keys = [v[0] for v in _TIMEOUT_KEYS.values()]
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    )
    cfg = {c.config_key: c.config_value for c in result.scalars().all()}
    return TimeoutPolicyResponse(
        urge_minutes=int(cfg.get("order_urge_minutes", "30")),
        timeout_minutes=int(cfg.get("order_timeout_minutes", "60")),
        timeout_action=cfg.get("order_timeout_action", "auto_cancel"),
        reminder_advance_hours=int(cfg.get("appointment_reminder_advance_hours", "24")),
    )


@router.get("/settings/timeout-policy")
async def admin_get_timeout_policy(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await _get_timeout_policy(db)


@router.put("/settings/timeout-policy")
async def admin_update_timeout_policy(
    data: TimeoutPolicyUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    updates = data.model_dump(exclude_unset=True)
    for field_name, (config_key, default_val) in _TIMEOUT_KEYS.items():
        if field_name in updates and updates[field_name] is not None:
            val = str(updates[field_name])
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.config_key == config_key)
            )
            cfg = result.scalar_one_or_none()
            if cfg:
                cfg.config_value = val
            else:
                db.add(SystemConfig(
                    config_key=config_key,
                    config_value=val,
                    config_type="timeout",
                    description=config_key,
                ))
    await db.flush()
    return await _get_timeout_policy(db)


@router.get("/settings/reminder-advance")
async def admin_get_reminder_advance(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "appointment_reminder_advance_hours")
    )
    cfg = result.scalar_one_or_none()
    hours = int(cfg.config_value) if cfg else 24
    return {"reminder_advance_hours": hours}


@router.put("/settings/reminder-advance")
async def admin_update_reminder_advance(
    data: dict,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    hours = data.get("reminder_advance_hours", 24)
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "appointment_reminder_advance_hours")
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.config_value = str(hours)
    else:
        db.add(SystemConfig(
            config_key="appointment_reminder_advance_hours",
            config_value=str(hours),
            config_type="timeout",
            description="预约提醒提前时长（小时）",
        ))
    await db.flush()
    return {"reminder_advance_hours": hours}


# ─────────── 适用门店独立管理 ───────────


@router.get("/store-bindding/products")
async def store_bindding_product_list(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    bound_count_sub = (
        select(
            ProductStore.product_id,
            func.count(ProductStore.id).label("bound_store_count"),
        )
        .group_by(ProductStore.product_id)
        .subquery()
    )

    base = (
        select(
            Product.id,
            Product.name,
            ProductCategory.name.label("category_name"),
            Product.sale_price,
            Product.images,
            Product.status,
            func.coalesce(bound_count_sub.c.bound_store_count, 0).label("bound_store_count"),
        )
        .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
        .outerjoin(bound_count_sub, Product.id == bound_count_sub.c.product_id)
    )

    if search:
        base = base.where(Product.name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(Product.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        StoreBinddingProductItem(
            id=r.id,
            name=r.name,
            category_name=r.category_name,
            sale_price=float(r.sale_price),
            images=r.images,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            bound_store_count=r.bound_store_count,
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/store-bindding/stores")
async def store_bindding_store_list(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    bound_count_sub = (
        select(
            ProductStore.store_id,
            func.count(ProductStore.id).label("bound_product_count"),
        )
        .group_by(ProductStore.store_id)
        .subquery()
    )

    base = (
        select(
            MerchantStore.id,
            MerchantStore.store_name,
            MerchantStore.store_code,
            MerchantStore.status,
            func.coalesce(bound_count_sub.c.bound_product_count, 0).label("bound_product_count"),
        )
        .outerjoin(bound_count_sub, MerchantStore.id == bound_count_sub.c.store_id)
    )

    if search:
        base = base.where(MerchantStore.store_name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(MerchantStore.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        StoreBinddingStoreItem(
            id=r.id,
            store_name=r.store_name,
            store_code=r.store_code,
            status=r.status if isinstance(r.status, str) else str(r.status),
            bound_product_count=r.bound_product_count,
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/store-bindding/products/{product_id}/stores")
async def store_bindding_product_store_checklist(
    product_id: int,
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    bound_sub = (
        select(ProductStore.store_id)
        .where(ProductStore.product_id == product_id)
        .subquery()
    )

    is_bound_expr = bound_sub.c.store_id.isnot(None)

    base = (
        select(
            MerchantStore.id.label("store_id"),
            MerchantStore.store_name,
            MerchantStore.store_code,
            MerchantStore.address,
            MerchantStore.status,
            is_bound_expr.label("is_bound"),
        )
        .outerjoin(bound_sub, MerchantStore.id == bound_sub.c.store_id)
    )

    if search:
        base = base.where(MerchantStore.store_name.ilike(f"%{search}%"))

    if status_filter == "bound":
        base = base.where(bound_sub.c.store_id.isnot(None))
    elif status_filter == "unbound":
        base = base.where(bound_sub.c.store_id.is_(None))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(MerchantStore.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        ProductStoreCheckItem(
            store_id=r.store_id,
            store_name=r.store_name,
            store_code=r.store_code,
            address=r.address,
            status=r.status if isinstance(r.status, str) else str(r.status),
            is_bound=bool(r.is_bound),
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/store-bindding/stores/{store_id}/products")
async def store_bindding_store_product_checklist(
    store_id: int,
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    bound_sub = (
        select(ProductStore.product_id)
        .where(ProductStore.store_id == store_id)
        .subquery()
    )

    is_bound_expr = bound_sub.c.product_id.isnot(None)

    base = (
        select(
            Product.id.label("product_id"),
            Product.name,
            ProductCategory.name.label("category_name"),
            Product.sale_price,
            Product.images,
            Product.status,
            is_bound_expr.label("is_bound"),
        )
        .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
        .outerjoin(bound_sub, Product.id == bound_sub.c.product_id)
    )

    if search:
        base = base.where(Product.name.ilike(f"%{search}%"))
    if category_id is not None:
        base = base.where(Product.category_id == category_id)

    if status_filter == "bound":
        base = base.where(bound_sub.c.product_id.isnot(None))
    elif status_filter == "unbound":
        base = base.where(bound_sub.c.product_id.is_(None))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(Product.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        StoreProductCheckItem(
            product_id=r.product_id,
            name=r.name,
            category_name=r.category_name,
            sale_price=float(r.sale_price),
            images=r.images,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            is_bound=bool(r.is_bound),
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/store-bindding/bind")
async def store_bindding_bind(
    data: SingleBindRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(ProductStore).where(
            and_(
                ProductStore.product_id == data.product_id,
                ProductStore.store_id == data.store_id,
            )
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(ProductStore(product_id=data.product_id, store_id=data.store_id))
        await db.flush()
    return {"message": "绑定成功"}


@router.post("/store-bindding/unbind")
async def store_bindding_unbind(
    data: SingleBindRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductStore).where(
            and_(
                ProductStore.product_id == data.product_id,
                ProductStore.store_id == data.store_id,
            )
        )
    )
    record = result.scalar_one_or_none()
    if record is not None:
        await db.delete(record)
        await db.flush()
    return {"message": "解绑成功"}


@router.post("/store-bindding/batch-bind")
async def store_bindding_batch_bind(
    data: BatchBindRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    success_count = 0
    fail_count = 0
    failures: list[str] = []

    for pid in data.product_ids:
        try:
            existing = await db.execute(
                select(ProductStore).where(
                    and_(
                        ProductStore.product_id == pid,
                        ProductStore.store_id == data.store_id,
                    )
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(ProductStore(product_id=pid, store_id=data.store_id))
                await db.flush()
            success_count += 1
        except Exception as e:
            fail_count += 1
            failures.append(f"商品{pid}绑定失败: {str(e)}")

    return BatchBindResponse(
        message="批量绑定成功",
        success_count=success_count,
        fail_count=fail_count,
        failures=failures,
    )


@router.post("/store-bindding/batch-unbind")
async def store_bindding_batch_unbind(
    data: BatchBindRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    success_count = 0
    fail_count = 0
    failures: list[str] = []

    for pid in data.product_ids:
        try:
            result = await db.execute(
                select(ProductStore).where(
                    and_(
                        ProductStore.product_id == pid,
                        ProductStore.store_id == data.store_id,
                    )
                )
            )
            record = result.scalar_one_or_none()
            if record is not None:
                await db.delete(record)
                await db.flush()
            success_count += 1
        except Exception as e:
            fail_count += 1
            failures.append(f"商品{pid}解绑失败: {str(e)}")

    return BatchBindResponse(
        message="批量解绑成功",
        success_count=success_count,
        fail_count=fail_count,
        failures=failures,
    )


@router.get("/store-bindding/products/{product_id}/bound-count")
async def store_bindding_product_bound_count(
    product_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(ProductStore.id)).where(
            ProductStore.product_id == product_id
        )
    )
    count = result.scalar() or 0
    return BoundCountResponse(product_id=product_id, bound_store_count=count)
