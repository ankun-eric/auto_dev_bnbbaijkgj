"""商家/机构 v1 扩展 API：
- 机构类别管理（管理员）+ 公开列表
- 商家身份状态（小程序入口校验）
- PC Web 登录 /api/merchant/auth/login
- 工作台指标、订单管理、核销记录、报表、对账单、发票、导出、员工
- 订单附件上传与查看（机构端 + 用户端）
"""
from __future__ import annotations

import io
import logging
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    get_identity_codes_for_user,
    require_identity,
    require_role,
    verify_password,
)
from app.models.models import (
    AccountIdentity,
    IdentityType,
    MerchantCategory,
    MerchantExportTask,
    MerchantInvoiceProfile,
    MerchantMemberRole,
    MerchantNotification,
    MerchantOrderVerification,
    MerchantProfile,
    MerchantRoleTemplate,
    MerchantStore,
    MerchantStoreMembership,
    MerchantStorePermission,
    Notification,
    NotificationType,
    OrderAttachment,
    OrderItem,
    OrderRedemption,
    SettlementPaymentProof,
    SettlementStatement,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.schemas.merchant_v1 import (
    ExportTaskCreateRequest,
    ExportTaskResponse,
    InvoiceProfileSchema,
    MerchantCategoryCreate,
    MerchantCategoryResponse,
    MerchantCategoryUpdate,
    MerchantLoginRequest,
    MerchantLoginResponse,
    MerchantOrderItem,
    MerchantOrderListResponse,
    MerchantRoleTemplateBrief,
    MerchantStaffPermissionUpdateRequest,
    MerchantStaffResponse,
    MerchantStaffStatusUpdateRequest,
    MerchantStatusResponse,
    MerchantVerificationRecord,
    MerchantWorkbenchMetrics,
    OrderAttachmentCreateRequest,
    OrderAttachmentResponse,
    PaymentProofCreateRequest,
    ReportAnalysisResponse,
    ReportSeriesPoint,
    SettlementConfirmRequest,
    SettlementDisputeRequest,
    SettlementGenerateRequest,
    SettlementStatementBrief,
)

logger = logging.getLogger(__name__)

# ========== 路由器 ==========

router = APIRouter()  # /api/merchant/v1 + /api/orders/:id/attachments 等
admin_router = APIRouter(prefix="/api/admin", tags=["平台-机构扩展"])

merchant_dep = require_identity("merchant_owner", "merchant_staff")
admin_dep = require_role("admin")

MAX_ATTACHMENTS_PER_ORDER = 5
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB


# ========== 公共工具 ==========

async def _active_merchant_membership(
    db: AsyncSession, user_id: int
) -> List[MerchantStoreMembership]:
    result = await db.execute(
        select(MerchantStoreMembership, MerchantStore)
        .join(MerchantStore, MerchantStore.id == MerchantStoreMembership.store_id)
        .where(
            MerchantStoreMembership.user_id == user_id,
            MerchantStoreMembership.status == "active",
            MerchantStore.status == "active",
        )
    )
    return result.all()


async def _merchant_profile_of_user(db: AsyncSession, user_id: int) -> Optional[MerchantProfile]:
    res = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == user_id))
    return res.scalar_one_or_none()


async def _user_store_ids(db: AsyncSession, user_id: int) -> List[int]:
    rows = await _active_merchant_membership(db, user_id)
    return [m.store_id for m, _ in rows]


async def _max_member_role(db: AsyncSession, user_id: int) -> Optional[MerchantMemberRole]:
    rows = await _active_merchant_membership(db, user_id)
    order = {
        MerchantMemberRole.owner: 5,
        MerchantMemberRole.finance: 4,
        MerchantMemberRole.store_manager: 3,
        MerchantMemberRole.staff: 2,
        MerchantMemberRole.verifier: 1,
    }
    best: Optional[MerchantMemberRole] = None
    for m, _ in rows:
        cur = m.member_role
        if best is None or order.get(cur, 0) > order.get(best, 0):
            best = cur
    return best


# ========== 1. 机构类别管理（平台 Admin） ==========

@admin_router.get("/merchant-categories", response_model=List[MerchantCategoryResponse])
async def admin_list_merchant_categories(
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MerchantCategory).order_by(MerchantCategory.sort.asc(), MerchantCategory.id.asc()))
    items = res.scalars().all()
    return items


@admin_router.post("/merchant-categories", response_model=MerchantCategoryResponse)
async def admin_create_merchant_category(
    data: MerchantCategoryCreate,
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    exist = await db.execute(select(MerchantCategory).where(MerchantCategory.code == data.code))
    if exist.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该 code 已存在")
    obj = MerchantCategory(
        code=data.code,
        name=data.name,
        icon=data.icon,
        description=data.description,
        allowed_attachment_types=data.allowed_attachment_types,
        attachment_label=data.attachment_label,
        sort=data.sort or 0,
        status=data.status or "active",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@admin_router.put("/merchant-categories/{cat_id}", response_model=MerchantCategoryResponse)
async def admin_update_merchant_category(
    cat_id: int,
    data: MerchantCategoryUpdate,
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MerchantCategory).where(MerchantCategory.id == cat_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="未找到类别")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@admin_router.delete("/merchant-categories/{cat_id}")
async def admin_delete_merchant_category(
    cat_id: int,
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MerchantCategory).where(MerchantCategory.id == cat_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="未找到类别")
    in_use = await db.execute(select(func.count(MerchantProfile.id)).where(MerchantProfile.category_id == cat_id))
    if (in_use.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="该类别下还有商家，无法删除")
    await db.delete(obj)
    await db.commit()
    return {"message": "已删除"}


@router.get("/api/merchant-categories", response_model=List[MerchantCategoryResponse])
async def public_list_merchant_categories(db: AsyncSession = Depends(get_db)):
    """公开读取（小程序商家端/H5 PC 后台展示类别用）"""
    res = await db.execute(
        select(MerchantCategory)
        .where(MerchantCategory.status == "active")
        .order_by(MerchantCategory.sort.asc(), MerchantCategory.id.asc())
    )
    return res.scalars().all()


# ========== 2. 商家身份状态（小程序菜单显示校验） ==========

@router.get("/api/auth/merchant-status", response_model=MerchantStatusResponse)
async def get_merchant_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    codes = await get_identity_codes_for_user(db, current_user.id)
    is_merchant = bool({"merchant_owner", "merchant_staff"} & codes)
    if not is_merchant:
        return MerchantStatusResponse(is_merchant=False)
    rows = await _active_merchant_membership(db, current_user.id)
    role = await _max_member_role(db, current_user.id)
    profile = await _merchant_profile_of_user(db, current_user.id)
    category_code = None
    if profile and profile.category_id:
        cat = await db.execute(select(MerchantCategory).where(MerchantCategory.id == profile.category_id))
        c = cat.scalar_one_or_none()
        category_code = c.code if c else None
    return MerchantStatusResponse(
        is_merchant=True,
        merchant_role=role.value if role else None,
        store_count=len(rows),
        category_code=category_code,
    )


# ========== 3. PC Web 登录 ==========

@router.post("/api/merchant/auth/login", response_model=MerchantLoginResponse)
async def merchant_pc_login(
    data: MerchantLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    # 手机号查找用户
    res = await db.execute(select(User).where(User.phone == data.phone))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    # 密码或短信验证码（其一）
    if data.password:
        if not verify_password(data.password, user.password_hash or ""):
            raise HTTPException(status_code=401, detail="账号不存在或密码错误")
    elif data.sms_code:
        # 简化：校验与 sms 接口一致；此处仅做占位校验（全位 8888 为万能码，实际应接 sms_service）
        if data.sms_code != "8888":
            raise HTTPException(status_code=401, detail="验证码错误")
    else:
        raise HTTPException(status_code=400, detail="请提供密码或验证码")
    # 商家身份检查
    codes = await get_identity_codes_for_user(db, user.id)
    if not ({"merchant_owner", "merchant_staff"} & codes):
        raise HTTPException(status_code=403, detail="非商家账号，无法登录商家后台")
    rows = await _active_merchant_membership(db, user.id)
    if not rows:
        raise HTTPException(status_code=403, detail="您还未被绑定到任何门店，请联系平台客服")
    role = await _max_member_role(db, user.id)
    token = create_access_token({"sub": user.id, "scope": "merchant_pc"})
    stores = [
        {
            "id": s.id,
            "store_name": s.store_name,
            "store_code": s.store_code,
            "member_role": m.member_role.value,
        }
        for m, s in rows
    ]
    return MerchantLoginResponse(
        access_token=token,
        user_id=user.id,
        phone=user.phone,
        nickname=user.nickname,
        merchant_role=role.value if role else "staff",
        store_count=len(rows),
        stores=stores,
    )


# ========== 4. 工作台指标 ==========

@router.get("/api/merchant/v1/dashboard/metrics", response_model=MerchantWorkbenchMetrics)
async def merchant_dashboard_metrics(
    store_id: Optional[int] = Query(None),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    if not store_ids:
        return MerchantWorkbenchMetrics()
    effective_ids = [store_id] if store_id and store_id in store_ids else store_ids

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    month_start = today_start.replace(day=1)

    # 今日核销数
    v_res = await db.execute(
        select(func.count(MerchantOrderVerification.id)).where(
            MerchantOrderVerification.store_id.in_(effective_ids),
            MerchantOrderVerification.verified_at >= today_start,
            MerchantOrderVerification.verified_at < tomorrow,
        )
    )
    today_verif = v_res.scalar() or 0

    # 今日订单数（以 redemption 记录的 store + 创建时间为近似）
    o_res = await db.execute(
        select(func.count(OrderRedemption.id)).where(
            OrderRedemption.store_id.in_(effective_ids),
            OrderRedemption.redeemed_at >= today_start,
            OrderRedemption.redeemed_at < tomorrow,
        )
    )
    today_orders = o_res.scalar() or 0

    # 本月 GMV：核销订单的订单金额
    gmv_res = await db.execute(
        select(func.coalesce(func.sum(UnifiedOrder.paid_amount), 0))
        .select_from(OrderRedemption)
        .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            OrderRedemption.store_id.in_(effective_ids),
            OrderRedemption.redeemed_at >= month_start,
            OrderRedemption.redeemed_at < tomorrow,
        )
    )
    month_gmv = float(gmv_res.scalar() or 0)

    # 待对账金额：status in ('pending','confirmed') 的对账单合计
    profile = await _merchant_profile_of_user(db, current_user.id)
    pending_settlement = 0.0
    if profile:
        ps_res = await db.execute(
            select(func.coalesce(func.sum(SettlementStatement.settlement_amount), 0)).where(
                SettlementStatement.merchant_profile_id == profile.id,
                SettlementStatement.status.in_(["pending", "confirmed", "dispute"]),
            )
        )
        pending_settlement = float(ps_res.scalar() or 0)

    # 未读消息
    un_res = await db.execute(
        select(func.count(MerchantNotification.id)).where(
            MerchantNotification.user_id == current_user.id,
            MerchantNotification.is_read == False,  # noqa: E712
        )
    )
    unread = un_res.scalar() or 0

    # 待上传附件：近 30 天已核销但无附件的订单数
    thirty_start = today_start - timedelta(days=30)
    no_att_res = await db.execute(
        select(func.count(OrderRedemption.id.distinct()))
        .select_from(OrderRedemption)
        .outerjoin(
            OrderAttachment,
            and_(
                OrderAttachment.order_id == OrderRedemption.order_item_id,
                OrderAttachment.order_source == "item",
            ),
        )
        .where(
            OrderRedemption.store_id.in_(effective_ids),
            OrderRedemption.redeemed_at >= thirty_start,
            OrderAttachment.id.is_(None),
        )
    )
    pending_att = no_att_res.scalar() or 0

    store_name = None
    if store_id:
        sn = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
        s = sn.scalar_one_or_none()
        if s:
            store_name = s.store_name

    return MerchantWorkbenchMetrics(
        store_id=store_id,
        store_name=store_name,
        today_orders=int(today_orders),
        today_verifications=int(today_verif),
        month_gmv=month_gmv,
        pending_settlement=pending_settlement,
        pending_attachments=int(pending_att),
        unread_messages=int(unread),
    )


# ========== 5. 订单管理（列表 + 详情） ==========

@router.get("/api/merchant/v1/orders", response_model=MerchantOrderListResponse)
async def merchant_list_orders(
    store_id: Optional[int] = Query(None),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    if not store_ids:
        return MerchantOrderListResponse(items=[], total=0, page=page, page_size=page_size)
    effective_ids = [store_id] if store_id and store_id in store_ids else store_ids

    # 用 OrderRedemption -> OrderItem -> UnifiedOrder 组合筛选
    q = (
        select(OrderItem, UnifiedOrder, OrderRedemption)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .join(OrderRedemption, OrderRedemption.order_item_id == OrderItem.id)
        .where(OrderRedemption.store_id.in_(effective_ids))
    )
    if status:
        try:
            q = q.where(UnifiedOrder.status == UnifiedOrderStatus(status))
        except Exception:
            pass
    if keyword:
        q = q.where(or_(UnifiedOrder.order_no.contains(keyword), OrderItem.product_name.contains(keyword)))
    if start_date:
        q = q.where(UnifiedOrder.created_at >= datetime.fromisoformat(f"{start_date}T00:00:00"))
    if end_date:
        q = q.where(UnifiedOrder.created_at <= datetime.fromisoformat(f"{end_date}T23:59:59"))

    count_q = (
        select(func.count(OrderRedemption.id.distinct()))
        .select_from(OrderRedemption)
        .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(OrderRedemption.store_id.in_(effective_ids))
    )
    total = (await db.execute(count_q)).scalar() or 0

    res = await db.execute(q.order_by(UnifiedOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    items: List[MerchantOrderItem] = []
    for oi, uo, red in res.all():
        # 附件数量
        att_count = await db.execute(
            select(func.count(OrderAttachment.id)).where(
                OrderAttachment.order_id == oi.id,
                OrderAttachment.order_source == "item",
            )
        )
        # 脱敏手机号
        user_res = await db.execute(select(User).where(User.id == uo.user_id))
        user = user_res.scalar_one_or_none()
        user_display = "用户"
        if user:
            phone = (user.phone or "").strip()
            if len(phone) >= 11:
                user_display = f"{phone[:3]}****{phone[-4:]}"
            else:
                user_display = user.nickname or phone or f"用户{user.id}"
        store_name = None
        s = await db.execute(select(MerchantStore).where(MerchantStore.id == red.store_id))
        st = s.scalar_one_or_none()
        if st:
            store_name = st.store_name
        items.append(
            MerchantOrderItem(
                order_id=oi.id,
                order_no=uo.order_no,
                user_display=user_display,
                product_name=oi.product_name,
                created_at=uo.created_at,
                appointment_time=oi.appointment_time,
                store_id=red.store_id,
                store_name=store_name,
                status=uo.status.value if hasattr(uo.status, "value") else str(uo.status),
                amount=float(oi.subtotal or 0),
                attachment_count=int(att_count.scalar() or 0),
            )
        )
    return MerchantOrderListResponse(items=items, total=int(total), page=page, page_size=page_size)


# ========== 6. 订单附件：列表/上传（机构端）+ 用户查看 ==========

@router.get("/api/merchant/v1/orders/{order_item_id}/attachments", response_model=List[OrderAttachmentResponse])
async def list_order_item_attachments_merchant(
    order_item_id: int,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    # 权限校验
    red = await db.execute(
        select(OrderRedemption).where(
            OrderRedemption.order_item_id == order_item_id,
            OrderRedemption.store_id.in_(store_ids),
        )
    )
    if not red.first():
        raise HTTPException(status_code=403, detail="无该订单权限")
    res = await db.execute(
        select(OrderAttachment)
        .where(
            OrderAttachment.order_id == order_item_id,
            OrderAttachment.order_source == "item",
        )
        .order_by(OrderAttachment.created_at.desc())
    )
    return res.scalars().all()


@router.post("/api/merchant/v1/orders/{order_item_id}/attachments", response_model=OrderAttachmentResponse)
async def upload_order_attachment(
    order_item_id: int,
    data: OrderAttachmentCreateRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    red = await db.execute(
        select(OrderRedemption).where(
            OrderRedemption.order_item_id == order_item_id,
            OrderRedemption.store_id.in_(store_ids),
        )
    )
    redeem_row = red.first()
    if not redeem_row:
        raise HTTPException(status_code=403, detail="无该订单权限")
    if data.file_type not in ("image", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持图片或 PDF")
    if data.file_size and data.file_size > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=400, detail="单文件不可超过 20MB")
    cnt_res = await db.execute(
        select(func.count(OrderAttachment.id)).where(
            OrderAttachment.order_id == order_item_id,
            OrderAttachment.order_source == "item",
        )
    )
    if (cnt_res.scalar() or 0) >= MAX_ATTACHMENTS_PER_ORDER:
        raise HTTPException(status_code=400, detail=f"每单最多 {MAX_ATTACHMENTS_PER_ORDER} 个附件")
    att = OrderAttachment(
        order_id=order_item_id,
        order_source="item",
        store_id=(redeem_row[0].store_id if redeem_row else data.store_id),
        uploader_user_id=current_user.id,
        file_type=data.file_type,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size=data.file_size or 0,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att


@router.delete("/api/merchant/v1/orders/{order_item_id}/attachments/{attachment_id}")
async def delete_order_attachment(
    order_item_id: int,
    attachment_id: int,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    res = await db.execute(
        select(OrderAttachment).where(
            OrderAttachment.id == attachment_id,
            OrderAttachment.order_id == order_item_id,
            OrderAttachment.order_source == "item",
        )
    )
    att = res.scalar_one_or_none()
    if not att or (att.store_id and att.store_id not in store_ids):
        raise HTTPException(status_code=404, detail="附件不存在")
    await db.delete(att)
    await db.commit()
    return {"message": "已删除"}


@router.get("/api/orders/{order_item_id}/attachments", response_model=List[OrderAttachmentResponse])
async def user_list_order_attachments(
    order_item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """C 端用户查看自己订单的附件"""
    oi_res = await db.execute(
        select(OrderItem, UnifiedOrder)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(OrderItem.id == order_item_id)
    )
    row = oi_res.first()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    _, uo = row
    if uo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限")
    res = await db.execute(
        select(OrderAttachment)
        .where(OrderAttachment.order_id == order_item_id, OrderAttachment.order_source == "item")
        .order_by(OrderAttachment.created_at.desc())
    )
    return res.scalars().all()


# ========== 7. 核销记录（扩展） ==========

@router.get("/api/merchant/v1/verifications")
async def merchant_list_verifications(
    store_id: Optional[int] = Query(None),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    if not store_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    effective_ids = [store_id] if store_id and store_id in store_ids else store_ids
    filters = [OrderRedemption.store_id.in_(effective_ids)]
    if start_date:
        filters.append(OrderRedemption.redeemed_at >= datetime.fromisoformat(f"{start_date}T00:00:00"))
    if end_date:
        filters.append(OrderRedemption.redeemed_at <= datetime.fromisoformat(f"{end_date}T23:59:59"))
    total_res = await db.execute(select(func.count(OrderRedemption.id)).where(and_(*filters)))
    total = total_res.scalar() or 0
    res = await db.execute(
        select(OrderRedemption)
        .where(and_(*filters))
        .order_by(OrderRedemption.redeemed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for r in res.scalars().all():
        oi = (await db.execute(select(OrderItem).where(OrderItem.id == r.order_item_id))).scalar_one_or_none()
        uo = None
        if oi:
            uo = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oi.order_id))).scalar_one_or_none()
        st = (await db.execute(select(MerchantStore).where(MerchantStore.id == r.store_id))).scalar_one_or_none()
        vu = (await db.execute(select(User).where(User.id == r.redeemed_by_user_id))).scalar_one_or_none()
        items.append({
            "id": r.id,
            "order_no": uo.order_no if uo else "",
            "product_name": oi.product_name if oi else "",
            "user_display": (uo.user_id and f"用户{uo.user_id}") or "用户",
            "store_name": st.store_name if st else "",
            "verifier_name": (vu and (vu.nickname or vu.phone)) or "",
            "verified_at": r.redeemed_at,
            "amount": float(oi.subtotal or 0) if oi else 0,
        })
    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


# ========== 8. 报表分析 ==========

@router.get("/api/merchant/v1/reports", response_model=ReportAnalysisResponse)
async def merchant_reports(
    period: str = Query("day", regex="^(day|week|month)$"),
    dim: str = Query("merchant", regex="^(merchant|store)$"),
    store_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    store_ids = await _user_store_ids(db, current_user.id)
    if not store_ids:
        return ReportAnalysisResponse(period=period, dim=dim, series=[], total_orders=0, total_gmv=0, total_verifications=0)
    effective_ids = [store_id] if (dim == "store" and store_id and store_id in store_ids) else store_ids

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.fromisoformat(f"{end_date}T23:59:59") if end_date else today + timedelta(days=1)
    if start_date:
        start = datetime.fromisoformat(f"{start_date}T00:00:00")
    else:
        if period == "day":
            start = today - timedelta(days=6)
        elif period == "week":
            start = today - timedelta(weeks=7)
        else:
            start = today.replace(day=1) - timedelta(days=150)

    # 按期间聚合
    if period == "day":
        fmt = "%Y-%m-%d"
    elif period == "week":
        fmt = "%x-W%v"
    else:
        fmt = "%Y-%m"

    res = await db.execute(
        select(
            func.date_format(OrderRedemption.redeemed_at, fmt).label("label"),
            func.count(OrderRedemption.id).label("cnt"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("gmv"),
        )
        .select_from(OrderRedemption)
        .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
        .where(
            OrderRedemption.store_id.in_(effective_ids),
            OrderRedemption.redeemed_at >= start,
            OrderRedemption.redeemed_at < end,
        )
        .group_by("label")
        .order_by("label")
    )
    series = []
    total_orders = 0
    total_gmv = 0.0
    total_verif = 0
    for row in res.all():
        label, cnt, gmv = row[0], int(row[1] or 0), float(row[2] or 0)
        series.append(ReportSeriesPoint(label=label, orders=cnt, gmv=gmv, verifications=cnt))
        total_orders += cnt
        total_gmv += gmv
        total_verif += cnt

    # TOP 商品
    tp = await db.execute(
        select(
            OrderItem.product_name,
            func.count(OrderRedemption.id).label("cnt"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("gmv"),
        )
        .select_from(OrderRedemption)
        .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
        .where(
            OrderRedemption.store_id.in_(effective_ids),
            OrderRedemption.redeemed_at >= start,
            OrderRedemption.redeemed_at < end,
        )
        .group_by(OrderItem.product_name)
        .order_by(func.count(OrderRedemption.id).desc())
        .limit(10)
    )
    top_products = [{"name": r[0], "count": int(r[1]), "gmv": float(r[2])} for r in tp.all()]

    return ReportAnalysisResponse(
        period=period,
        dim=dim,
        series=series,
        total_orders=total_orders,
        total_gmv=total_gmv,
        total_verifications=total_verif,
        top_products=top_products,
    )


# ========== 9. 对账结算 ==========

@router.get("/api/merchant/v1/settlements", response_model=List[SettlementStatementBrief])
async def merchant_list_settlements(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        return []
    res = await db.execute(
        select(SettlementStatement)
        .where(SettlementStatement.merchant_profile_id == profile.id)
        .order_by(SettlementStatement.period_start.desc(), SettlementStatement.id.desc())
    )
    return res.scalars().all()


@router.get("/api/merchant/v1/settlements/{sid}", response_model=SettlementStatementBrief)
async def merchant_settlement_detail(
    sid: int,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="未找到商家档案")
    res = await db.execute(select(SettlementStatement).where(SettlementStatement.id == sid))
    stmt = res.scalar_one_or_none()
    if not stmt or stmt.merchant_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="对账单不存在")
    return stmt


@router.post("/api/merchant/v1/settlements/{sid}/confirm")
async def merchant_settlement_confirm(
    sid: int,
    data: SettlementConfirmRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="未找到商家档案")
    res = await db.execute(select(SettlementStatement).where(SettlementStatement.id == sid))
    stmt = res.scalar_one_or_none()
    if not stmt or stmt.merchant_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="对账单不存在")
    if stmt.status != "pending":
        raise HTTPException(status_code=400, detail="当前状态不可确认")
    stmt.status = "confirmed"
    stmt.confirmed_at = datetime.utcnow()
    if data.remark:
        stmt.remark = data.remark
    await db.commit()
    return {"message": "已确认"}


@router.post("/api/merchant/v1/settlements/{sid}/dispute")
async def merchant_settlement_dispute(
    sid: int,
    data: SettlementDisputeRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="未找到商家档案")
    res = await db.execute(select(SettlementStatement).where(SettlementStatement.id == sid))
    stmt = res.scalar_one_or_none()
    if not stmt or stmt.merchant_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="对账单不存在")
    stmt.status = "dispute"
    stmt.remark = (stmt.remark or "") + f"\n[异议 {datetime.utcnow().isoformat()}]: {data.reason}"
    await db.commit()
    return {"message": "已发起异议，平台客服将跟进"}


@admin_router.post("/settlements/generate-monthly")
async def admin_generate_monthly_settlements(
    data: SettlementGenerateRequest,
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """平台：按月批量生成对账单（机构维度 + 门店维度各一份）"""
    today = datetime.utcnow().date()
    if data.period_end and data.period_start:
        p_start, p_end = data.period_start, data.period_end
    else:
        # 上月 1 号 - 上月末
        first_this = today.replace(day=1)
        p_end = first_this - timedelta(days=1)
        p_start = p_end.replace(day=1)

    mps_q = select(MerchantProfile)
    if data.merchant_profile_id:
        mps_q = mps_q.where(MerchantProfile.id == data.merchant_profile_id)
    mps = (await db.execute(mps_q)).scalars().all()
    created = 0
    for mp in mps:
        # 找该商家拥有的门店：通过 membership role=owner 定位
        mu_res = await db.execute(
            select(MerchantStoreMembership).where(
                MerchantStoreMembership.user_id == mp.user_id,
                MerchantStoreMembership.member_role == MerchantMemberRole.owner,
            )
        )
        owner_store_ids = [m.store_id for m in mu_res.scalars().all()]
        if not owner_store_ids:
            continue

        # 机构维度统计
        ms_start = datetime.combine(p_start, datetime.min.time())
        ms_end = datetime.combine(p_end, datetime.max.time())
        agg = await db.execute(
            select(
                func.count(OrderRedemption.id).label("cnt"),
                func.coalesce(func.sum(OrderItem.subtotal), 0).label("gmv"),
            )
            .select_from(OrderRedemption)
            .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
            .where(
                OrderRedemption.store_id.in_(owner_store_ids),
                OrderRedemption.redeemed_at >= ms_start,
                OrderRedemption.redeemed_at <= ms_end,
            )
        )
        row = agg.first()
        mcount, mgmv = int(row[0] or 0), float(row[1] or 0)

        # 机构维度对账单（幂等）
        existing = await db.execute(
            select(SettlementStatement).where(
                SettlementStatement.merchant_profile_id == mp.id,
                SettlementStatement.dim == "merchant",
                SettlementStatement.period_start == p_start,
                SettlementStatement.period_end == p_end,
            )
        )
        if not existing.scalar_one_or_none():
            sno = f"ST-M{mp.id}-{p_start.strftime('%Y%m')}-{secrets.token_hex(2)}"
            db.add(SettlementStatement(
                statement_no=sno,
                merchant_profile_id=mp.id,
                store_id=None,
                dim="merchant",
                period_start=p_start,
                period_end=p_end,
                order_count=mcount,
                total_amount=Decimal(str(mgmv)),
                settlement_amount=Decimal(str(mgmv)),
                status="pending",
            ))
            created += 1

        # 门店维度
        for sid in owner_store_ids:
            ex2 = await db.execute(
                select(SettlementStatement).where(
                    SettlementStatement.merchant_profile_id == mp.id,
                    SettlementStatement.store_id == sid,
                    SettlementStatement.dim == "store",
                    SettlementStatement.period_start == p_start,
                    SettlementStatement.period_end == p_end,
                )
            )
            if ex2.scalar_one_or_none():
                continue
            agg2 = await db.execute(
                select(
                    func.count(OrderRedemption.id).label("cnt"),
                    func.coalesce(func.sum(OrderItem.subtotal), 0).label("gmv"),
                )
                .select_from(OrderRedemption)
                .join(OrderItem, OrderItem.id == OrderRedemption.order_item_id)
                .where(
                    OrderRedemption.store_id == sid,
                    OrderRedemption.redeemed_at >= ms_start,
                    OrderRedemption.redeemed_at <= ms_end,
                )
            )
            r2 = agg2.first()
            sc, sg = int(r2[0] or 0), float(r2[1] or 0)
            sno2 = f"ST-S{sid}-{p_start.strftime('%Y%m')}-{secrets.token_hex(2)}"
            db.add(SettlementStatement(
                statement_no=sno2,
                merchant_profile_id=mp.id,
                store_id=sid,
                dim="store",
                period_start=p_start,
                period_end=p_end,
                order_count=sc,
                total_amount=Decimal(str(sg)),
                settlement_amount=Decimal(str(sg)),
                status="pending",
            ))
            created += 1
    await db.commit()
    return {"message": "已生成", "created": created, "period_start": p_start.isoformat(), "period_end": p_end.isoformat()}


@admin_router.post("/settlements/{sid}/payment-proof")
async def admin_upload_payment_proof(
    sid: int,
    data: PaymentProofCreateRequest,
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(SettlementStatement).where(SettlementStatement.id == sid))
    stmt = res.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="对账单不存在")
    pp_res = await db.execute(select(SettlementPaymentProof).where(SettlementPaymentProof.statement_id == sid))
    pp = pp_res.scalar_one_or_none()
    if pp:
        pp.file_url = data.file_url
        pp.file_name = data.file_name
        pp.amount = Decimal(str(data.amount or 0))
        pp.paid_at = data.paid_at or datetime.utcnow()
    else:
        db.add(SettlementPaymentProof(
            statement_id=sid,
            file_url=data.file_url,
            file_name=data.file_name,
            amount=Decimal(str(data.amount or 0)),
            paid_at=data.paid_at or datetime.utcnow(),
        ))
    stmt.status = "settled"
    stmt.settled_at = datetime.utcnow()
    await db.commit()
    return {"message": "打款凭证已上传"}


# ========== 10. 发票信息 ==========

@router.get("/api/merchant/v1/invoice-profile", response_model=InvoiceProfileSchema)
async def get_invoice_profile(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        return InvoiceProfileSchema()
    res = await db.execute(select(MerchantInvoiceProfile).where(MerchantInvoiceProfile.merchant_profile_id == profile.id))
    inv = res.scalar_one_or_none()
    if not inv:
        return InvoiceProfileSchema()
    return inv


@router.put("/api/merchant/v1/invoice-profile", response_model=InvoiceProfileSchema)
async def update_invoice_profile(
    data: InvoiceProfileSchema,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="未找到商家档案")
    res = await db.execute(select(MerchantInvoiceProfile).where(MerchantInvoiceProfile.merchant_profile_id == profile.id))
    inv = res.scalar_one_or_none()
    if not inv:
        inv = MerchantInvoiceProfile(merchant_profile_id=profile.id)
        db.add(inv)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(inv, k, v)
    await db.commit()
    await db.refresh(inv)
    return inv


# ========== 11. 导出任务 ==========

@router.post("/api/merchant/v1/exports", response_model=ExportTaskResponse)
async def create_export_task(
    data: ExportTaskCreateRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="未找到商家档案")
    # 时间范围 ≤1 年
    if data.start_date and data.end_date:
        if (data.end_date - data.start_date).days > 366:
            raise HTTPException(status_code=400, detail="单次导出范围最多 1 年，请分批导出")
    # 1 分钟 1 次
    last = await db.execute(
        select(MerchantExportTask)
        .where(MerchantExportTask.merchant_profile_id == profile.id)
        .order_by(MerchantExportTask.created_at.desc())
        .limit(1)
    )
    last_task = last.scalar_one_or_none()
    if last_task and (datetime.utcnow() - last_task.created_at).total_seconds() < 60:
        raise HTTPException(status_code=429, detail="导出过于频繁，请稍后再试")
    task = MerchantExportTask(
        merchant_profile_id=profile.id,
        user_id=current_user.id,
        task_name=data.task_name,
        task_type=data.task_type,
        params={"start_date": data.start_date.isoformat() if data.start_date else None,
                "end_date": data.end_date.isoformat() if data.end_date else None,
                "store_id": data.store_id},
        status="completed",  # 简化：同步完成（本期不接 Celery）
        file_url=f"/api/merchant/v1/exports/placeholder/{secrets.token_hex(6)}.xlsx",
        finished_at=datetime.utcnow(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/api/merchant/v1/exports", response_model=List[ExportTaskResponse])
async def list_export_tasks(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    profile = await _merchant_profile_of_user(db, current_user.id)
    if not profile:
        return []
    res = await db.execute(
        select(MerchantExportTask)
        .where(MerchantExportTask.merchant_profile_id == profile.id)
        .order_by(MerchantExportTask.created_at.desc())
        .limit(50)
    )
    return res.scalars().all()


@router.get("/api/merchant/v1/exports/placeholder/{name}")
async def download_export_placeholder(
    name: str,
    current_user: User = Depends(merchant_dep),
):
    """占位下载：本期返回 CSV 空壳，后续可接真实导出"""
    csv_content = "order_no,product,amount,verified_at\n"
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}.csv"},
    )


# ========== 12. 员工（只读） ==========

@router.get("/api/merchant/v1/staff", response_model=List[MerchantStaffResponse])
async def merchant_list_staff(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    role = await _max_member_role(db, current_user.id)
    # 仅 owner / store_manager / finance 可查看
    if role not in (MerchantMemberRole.owner, MerchantMemberRole.store_manager, MerchantMemberRole.finance):
        raise HTTPException(status_code=403, detail="无权限查看员工")
    my_store_ids = await _user_store_ids(db, current_user.id)
    if not my_store_ids:
        return []
    res = await db.execute(
        select(MerchantStoreMembership, User)
        .join(User, User.id == MerchantStoreMembership.user_id)
        .where(MerchantStoreMembership.store_id.in_(my_store_ids))
    )
    # 预加载角色模板名称
    tpl_res = await db.execute(select(MerchantRoleTemplate))
    role_name_map = {t.code: t.name for t in tpl_res.scalars().all()}
    _DEFAULT_ROLE_NAMES = {"boss": "老板", "manager": "店长", "finance": "财务", "clerk": "店员"}

    by_user: dict[int, MerchantStaffResponse] = {}
    for m, u in res.all():
        existing = by_user.get(u.id)
        if existing:
            if m.store_id not in existing.store_ids:
                existing.store_ids.append(m.store_id)
        else:
            rc = getattr(m, "role_code", None)
            if not rc:
                if m.member_role == MerchantMemberRole.owner:
                    rc = "boss"
                else:
                    rc = "clerk"
            by_user[u.id] = MerchantStaffResponse(
                user_id=u.id,
                phone=u.phone or "",
                nickname=u.nickname,
                member_role=m.member_role.value,
                role_code=rc,
                role_name=role_name_map.get(rc) or _DEFAULT_ROLE_NAMES.get(rc),
                store_ids=[m.store_id],
                status=m.status,
            )
    return list(by_user.values())


# ========== 13. 角色模板（平台字典，Admin 读取） ==========

@admin_router.get("/merchant-role-templates", response_model=List[MerchantRoleTemplateBrief])
async def admin_list_merchant_role_templates(
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(MerchantRoleTemplate).order_by(
            MerchantRoleTemplate.sort_order.asc(), MerchantRoleTemplate.id.asc()
        )
    )
    items = []
    for t in res.scalars().all():
        mods = t.default_modules if isinstance(t.default_modules, list) else []
        items.append(MerchantRoleTemplateBrief(code=t.code, name=t.name, default_modules=list(mods)))
    return items


@router.get("/api/merchant/v1/role-templates", response_model=List[MerchantRoleTemplateBrief])
async def merchant_list_role_templates(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    """商家端读取角色模板（用于店长查看权限 / 前端展示角色）"""
    res = await db.execute(
        select(MerchantRoleTemplate).order_by(
            MerchantRoleTemplate.sort_order.asc(), MerchantRoleTemplate.id.asc()
        )
    )
    items = []
    for t in res.scalars().all():
        mods = t.default_modules if isinstance(t.default_modules, list) else []
        items.append(MerchantRoleTemplateBrief(code=t.code, name=t.name, default_modules=list(mods)))
    return items


# ========== 14. 商家端员工管理（店长可改权限/停用，不能新增） ==========

_FULL_MODULE_CODES_V1 = [
    "dashboard", "verify", "records", "messages", "profile", "finance", "staff", "settings",
]


async def _require_manager_or_owner(db: AsyncSession, user_id: int) -> MerchantMemberRole:
    role = await _max_member_role(db, user_id)
    if role not in (MerchantMemberRole.owner, MerchantMemberRole.store_manager):
        raise HTTPException(status_code=403, detail="无权限操作员工")
    return role


@router.post("/api/merchant/v1/staff")
async def merchant_staff_create_forbidden(
    current_user: User = Depends(merchant_dep),
):
    """店长/老板通过商家端新增员工——本期统一禁止，需要由 Admin 新建"""
    raise HTTPException(status_code=403, detail={
        "code": "E_MANAGER_CANNOT_CREATE",
        "message": "新增员工请在平台管理后台完成",
    })


@router.put("/api/merchant/v1/staff/{target_user_id}/permissions")
async def merchant_staff_update_permissions(
    target_user_id: int,
    data: MerchantStaffPermissionUpdateRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    role = await _require_manager_or_owner(db, current_user.id)
    my_store_ids = set(await _user_store_ids(db, current_user.id))
    if data.store_id not in my_store_ids:
        raise HTTPException(status_code=403, detail="无权限跨店操作")

    target_mem_res = await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == target_user_id,
            MerchantStoreMembership.store_id == data.store_id,
        )
    )
    target_mem = target_mem_res.scalar_one_or_none()
    if not target_mem:
        raise HTTPException(status_code=404, detail="目标员工在该门店不存在")

    target_rc = getattr(target_mem, "role_code", None) or (
        "boss" if target_mem.member_role == MerchantMemberRole.owner else "clerk"
    )
    # 店长不能修改老板/其他店长；老板可修改除老板外的角色
    if role == MerchantMemberRole.store_manager and target_rc in ("boss", "manager"):
        raise HTTPException(status_code=403, detail="无权限修改该员工")
    if target_rc == "boss":
        raise HTTPException(status_code=403, detail="不能修改老板权限")

    modules = [m for m in (data.module_codes or []) if m in _FULL_MODULE_CODES_V1]
    perm_res = await db.execute(
        select(MerchantStorePermission).where(
            MerchantStorePermission.membership_id == target_mem.id
        )
    )
    existing = perm_res.scalars().all()
    existing_map = {p.module_code: p for p in existing}
    keep = set(modules)
    for p in existing:
        if p.module_code not in keep:
            await db.delete(p)
    for m in modules:
        if m not in existing_map:
            db.add(MerchantStorePermission(membership_id=target_mem.id, module_code=m))
    await db.commit()
    return {"message": "权限已更新", "module_codes": sorted(keep)}


@router.put("/api/merchant/v1/staff/{target_user_id}/status")
async def merchant_staff_update_status(
    target_user_id: int,
    data: MerchantStaffStatusUpdateRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    role = await _require_manager_or_owner(db, current_user.id)
    if data.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="无效的状态值")
    my_store_ids = set(await _user_store_ids(db, current_user.id))
    target_mem_res = await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == target_user_id,
            MerchantStoreMembership.store_id.in_(my_store_ids),
        )
    )
    memberships = target_mem_res.scalars().all()
    if not memberships:
        raise HTTPException(status_code=404, detail="目标员工不在你的授权门店")

    for mem in memberships:
        target_rc = getattr(mem, "role_code", None) or (
            "boss" if mem.member_role == MerchantMemberRole.owner else "clerk"
        )
        if target_rc == "boss":
            raise HTTPException(status_code=403, detail="不能停用老板账号")
        if role == MerchantMemberRole.store_manager and target_rc in ("boss", "manager"):
            raise HTTPException(status_code=403, detail="无权限操作该员工")

    for mem in memberships:
        mem.status = data.status
        mem.updated_at = datetime.utcnow()
    await db.commit()
    return {"message": "状态已更新", "status": data.status}
