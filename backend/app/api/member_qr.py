import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_identity
from app.utils.client_source import require_mobile_verify_client
from app.models.models import (
    CheckinRecord,
    MemberQRToken,
    MerchantStore,
    OrderItem,
    OrderRedemption,
    PointsRecord,
    PointsType,
    RefundStatusEnum,
    StoreVisitRecord,
    SystemConfig,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.schemas.member_qr import (
    CheckinConfigRequest,
    CheckinRecordResponse,
    CheckinRequest,
    CheckinResponse,
    MemberQRCodeResponse,
    RedeemRequest,
    RedeemResponse,
    StoreVisitResponse,
    VerifyMemberQRRequest,
    VerifyMemberQRResponse,
)

router = APIRouter(tags=["会员码"])


@router.get("/api/member/qrcode")
async def get_member_qrcode(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    qr_token = MemberQRToken(
        user_id=current_user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(qr_token)
    await db.flush()
    return MemberQRCodeResponse(
        token=token, expires_at=expires_at, user_id=current_user.id
    )


@router.post("/api/verify/member-qrcode")
async def verify_member_qrcode(
    data: VerifyMemberQRRequest,
    request: Request,
    current_user: User = Depends(require_identity("merchant_owner", "merchant_staff")),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-05 R-05-04] 会员码识别同样属于"门店现场"动作，PC 端不应触发，仅手机端可用。
    result = await db.execute(
        select(MemberQRToken).where(MemberQRToken.token == data.token)
    )
    qr_token = result.scalar_one_or_none()
    if not qr_token:
        raise HTTPException(status_code=404, detail="无效的会员码")
    if qr_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="会员码已过期")

    user_result = await db.execute(select(User).where(User.id == qr_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return VerifyMemberQRResponse(
        user_id=user.id,
        nickname=user.nickname,
        avatar=user.avatar,
        phone=user.phone,
        member_level=user.member_level or 0,
        points=user.points or 0,
    )


@router.post("/api/verify/checkin")
async def checkin_at_store(
    data: CheckinRequest,
    request: Request,
    current_user: User = Depends(require_identity("merchant_owner", "merchant_staff")),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-05 R-05-04] 到店签到属于现场动作，PC 端不应触发，仅手机端可用。
    result = await db.execute(
        select(MemberQRToken).where(MemberQRToken.token == data.token)
    )
    qr_token = result.scalar_one_or_none()
    if not qr_token:
        raise HTTPException(status_code=404, detail="无效的会员码")
    if qr_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="会员码已过期")

    store_result = await db.execute(
        select(MerchantStore).where(MerchantStore.id == data.store_id)
    )
    store = store_result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    # ===== 新版到店签到积分配置（兼容旧键 checkin_points_per_visit）=====
    cfg_keys = [
        "storeCheckIn",
        "storeCheckInDailyTimes",
        "storeCheckInDailyLimit",
        "checkin_points_per_visit",  # 旧键回退
    ]
    cfg_res = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(cfg_keys))
    )
    cfg_map = {c.config_key: c.config_value for c in cfg_res.scalars().all()}

    def _to_int(val, default=0):
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    per_visit = _to_int(cfg_map.get("storeCheckIn"), 0)
    if per_visit <= 0:
        per_visit = _to_int(cfg_map.get("checkin_points_per_visit"), 5)
    daily_times = _to_int(cfg_map.get("storeCheckInDailyTimes"), 0)
    daily_limit = _to_int(cfg_map.get("storeCheckInDailyLimit"), 0)

    today = date.today()
    today_count_res = await db.execute(
        select(func.count(CheckinRecord.id)).where(
            CheckinRecord.user_id == qr_token.user_id,
            func.date(CheckinRecord.checked_in_at) == today,
        )
    )
    today_count = int(today_count_res.scalar() or 0)

    today_points_res = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == qr_token.user_id,
            PointsRecord.type == PointsType.checkin,
            PointsRecord.description.like("到店签到%"),
            func.date(PointsRecord.created_at) == today,
        )
    )
    today_points = int(today_points_res.scalar() or 0)

    points_earned = per_visit
    limit_reached = False
    if daily_times > 0 and today_count >= daily_times:
        points_earned = 0
        limit_reached = True
    if daily_limit > 0:
        remaining = daily_limit - today_points
        if remaining <= 0:
            points_earned = 0
            limit_reached = True
        else:
            points_earned = min(points_earned, remaining)

    checkin = CheckinRecord(
        user_id=qr_token.user_id,
        store_id=data.store_id,
        staff_user_id=current_user.id,
        points_earned=points_earned,
    )
    db.add(checkin)

    visit = StoreVisitRecord(
        user_id=qr_token.user_id,
        store_id=data.store_id,
        staff_user_id=current_user.id,
    )
    db.add(visit)

    user_result = await db.execute(select(User).where(User.id == qr_token.user_id))
    user = user_result.scalar_one_or_none()
    if user and points_earned > 0:
        user.points += points_earned
        pr = PointsRecord(
            user_id=user.id,
            points=points_earned,
            type=PointsType.checkin,
            description=f"到店签到 {store.store_name}{' (达到每日上限)' if limit_reached else ''}",
        )
        db.add(pr)

    await db.flush()
    await db.refresh(checkin)
    return CheckinResponse.model_validate(checkin)


@router.post("/api/verify/redeem")
async def redeem_service(
    data: RedeemRequest,
    request: Request,
    current_user: User = Depends(require_identity("merchant_owner", "merchant_staff")),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-05 R-05-04] 来源校验：仅允许 h5-mobile / verify-miniprogram，PC 端 403。
    # 上方 require_mobile_verify_client 已完成校验，不通过会直接抛 403。
    result = await db.execute(
        select(OrderItem).where(OrderItem.verification_code == data.verification_code)
    )
    order_item = result.scalar_one_or_none()
    if not order_item:
        raise HTTPException(status_code=404, detail="核销码无效")

    if order_item.used_redeem_count >= order_item.total_redeem_count:
        raise HTTPException(status_code=400, detail="已全部核销")

    order_result = await db.execute(
        select(UnifiedOrder)
        .where(UnifiedOrder.id == order_item.order_id)
        .with_for_update()
    )
    order_for_check = order_result.scalar_one_or_none()
    if not order_for_check:
        raise HTTPException(status_code=404, detail="关联订单不存在")

    refund_val = order_for_check.refund_status
    if hasattr(refund_val, "value"):
        refund_val = refund_val.value
    if refund_val in ("applied", "reviewing", "approved", "returning"):
        raise HTTPException(status_code=400, detail="该订单正在退款处理中，暂时无法核销")
    if refund_val == "refund_success":
        raise HTTPException(status_code=400, detail="该订单已退款，核销码已失效")

    redemption = OrderRedemption(
        order_item_id=order_item.id,
        redeemed_by_user_id=current_user.id,
        store_id=data.store_id,
    )
    db.add(redemption)

    order_item.used_redeem_count += 1
    order_item.updated_at = datetime.utcnow()

    all_items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_item.order_id)
    )
    all_items = all_items_result.scalars().all()
    all_redeemed = all(it.used_redeem_count >= it.total_redeem_count for it in all_items)
    if all_redeemed:
        order_result = await db.execute(
            select(UnifiedOrder).where(UnifiedOrder.id == order_item.order_id)
        )
        order = order_result.scalar_one_or_none()
        if order:
            status_val = order.status
            if hasattr(status_val, "value"):
                status_val = status_val.value
            if status_val == "pending_use":
                order.status = UnifiedOrderStatus.completed
                order.completed_at = datetime.utcnow()
                order.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(redemption)

    return RedeemResponse(
        id=redemption.id,
        order_item_id=order_item.id,
        redeemed_by_user_id=current_user.id,
        store_id=data.store_id,
        redeemed_at=redemption.redeemed_at,
        remaining_count=order_item.total_redeem_count - order_item.used_redeem_count,
    )


# [PRD-05 §2.4] 统一核销入口，作为 /api/verify/redeem 的别名，方便手机端 / 核销小程序统一调用。
# 同样要求来源 ∈ ("h5-mobile", "verify-miniprogram") 才允许通过；PC 端 403。
@router.post("/api/verifications/verify")
async def verifications_verify(
    data: RedeemRequest,
    request: Request,
    current_user: User = Depends(require_identity("merchant_owner", "merchant_staff")),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-05] 核销动作统一入口（手机端专用）。

    与 `/api/verify/redeem` 行为完全等价，是 PRD §2.4 规定的对外接口名。
    保留 `/api/verify/redeem` 以向后兼容现存的 H5 移动端调用。
    """
    return await redeem_service(
        data=data,
        request=request,
        current_user=current_user,
        _client_type=_client_type,
        db=db,
    )


@router.get("/api/verify/checkin-records")
async def list_checkin_records(
    store_id: int = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_identity("merchant_owner", "merchant_staff")),
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
