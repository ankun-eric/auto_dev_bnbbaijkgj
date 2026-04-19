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
    Product,
    ProductCategory,
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
    ProductUpdate,
    SymptomTagResponse,
)
from app.schemas.unified_orders import (
    RefundActionRequest,
    RefundReasonItem,
    RefundRequestResponse,
    SalesStatisticsResponse,
    ShipRequest,
    TrendItem,
    UnifiedOrderResponse,
)

router = APIRouter(prefix="/api/admin", tags=["商品管理后台"])

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
    items = [ProductResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
        valid_start_date=data.valid_start_date,
        valid_end_date=data.valid_end_date,
        points_exchangeable=data.points_exchangeable,
        points_price=data.points_price,
        points_deductible=data.points_deductible,
        redeem_count=data.redeem_count,
        appointment_mode=data.appointment_mode,
        purchase_appointment_mode=data.purchase_appointment_mode,
        custom_form_id=data.custom_form_id,
        faq=data.faq,
        recommend_weight=data.recommend_weight,
        status=data.status,
        sort_order=data.sort_order,
        payment_timeout_minutes=data.payment_timeout_minutes,
    )
    db.add(product)
    await db.flush()

    if data.store_ids:
        for store_id in data.store_ids:
            ps = ProductStore(product_id=product.id, store_id=store_id)
            db.add(ps)
        await db.flush()

    await db.refresh(product)
    return ProductResponse.model_validate(product)


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

    update_data = data.model_dump(exclude_unset=True)
    store_ids = update_data.pop("store_ids", None)

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

    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


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

    if not product.custom_form_id:
        form = AppointmentForm(name=f"商品{product.id}预约表单")
        db.add(form)
        await db.flush()
        product.custom_form_id = form.id
        await db.flush()

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
        form = AppointmentForm(name=f"商品{product.id}预约表单")
        db.add(form)
        await db.flush()
        product.custom_form_id = form.id
        await db.flush()

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
    refund_req.updated_at = datetime.utcnow()

    order_result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.refund_status = RefundStatusEnum.refund_success
        order.status = UnifiedOrderStatus.cancelled
        order.cancelled_at = datetime.utcnow()
        order.updated_at = datetime.utcnow()

    return {"message": "退款已批准"}


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
