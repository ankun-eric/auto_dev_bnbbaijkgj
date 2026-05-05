"""卡管理 v2.0（第 2 ~ 5 期）C 端与门店端核销 API。

涵盖：
- 第 2 期 购卡下单 + 自动激活 + 卡内项目快照
- 第 3 期 60s 动态核销码 + 门店核销 + 核销记录 + 卡退款规则
- 第 4 期 拆 2 单 / 续卡 / 商品省钱提示 / 可续卡列表
- 第 5 期 销售看板（独立模块在 cards_admin_v2.py）+ 分享海报

设计原则：
- 严格使用项目既有的 schema_sync 幂等加列与表创建机制
- 所有变更增量、幂等
- 不删除任何已有列
- 测试用 sqlite (aiosqlite)，生产用 mysql
"""
from __future__ import annotations

import hashlib
import secrets
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.utils.client_source import require_mobile_verify_client
from app.models.models import (
    CardDefinition,
    CardItem,
    CardRedemptionCode,
    CardRedemptionCodeStatus,
    CardRenewStrategy,
    CardScopeType,
    CardStatus,
    CardType,
    CardUsageLog,
    MerchantProfile,
    MerchantStore,
    OrderItem,
    Product,
    RefundStatusEnum,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserCard,
    UserCardStatus,
)
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/cards", tags=["卡功能 v2.0（C 端）"])
staff_router = APIRouter(prefix="/api/staff/cards", tags=["卡功能 v2.0（门店端）"])
order_card_router = APIRouter(prefix="/api/orders/unified", tags=["卡订单 v2.0"])
product_card_router = APIRouter(prefix="/api/products", tags=["商品省钱提示 v2.0"])


# ───────────────────────────── Schemas ─────────────────────────────


class CardPurchaseCreate(BaseModel):
    card_definition_id: int = Field(..., description="卡定义 ID")
    payment_method: Optional[str] = Field(default="wechat")
    notes: Optional[str] = None
    from_product_id: Optional[int] = Field(
        default=None, description="来源商品 ID（用于第 4 期回流）"
    )
    renew_from_user_card_id: Optional[int] = Field(
        default=None, description="续卡来源 user_card.id"
    )


class CheckoutItem(BaseModel):
    product_type: str = Field(..., description="physical | service | appointment | card")
    product_id: Optional[int] = None
    quantity: int = 1
    card_definition_id: Optional[int] = None
    sku_id: Optional[int] = None


class CheckoutRequest(BaseModel):
    items: List[CheckoutItem]
    notes: Optional[str] = None


class RedemptionCodeResponse(BaseModel):
    user_card_id: int
    token: str
    digits: str
    issued_at: datetime
    expires_at: datetime
    status: str


class StaffRedeemRequest(BaseModel):
    code_token: Optional[str] = None
    code_digits: Optional[str] = None
    product_id: int
    store_id: Optional[int] = None
    technician_id: Optional[int] = None
    notes: Optional[str] = None


class CardUsageLogResponse(BaseModel):
    id: int
    user_card_id: int
    product_id: int
    product_name: Optional[str] = None
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    technician_id: Optional[int] = None
    used_at: datetime
    notes: Optional[str] = None
    remaining_after: Optional[int] = None


class CardUsageLogListResponse(BaseModel):
    total: int
    items: List[CardUsageLogResponse]


class RenewRequest(BaseModel):
    payment_method: Optional[str] = "wechat"


class SavingsTipResponse(BaseModel):
    has_card: bool
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    save_amount: Optional[float] = None
    per_use_price: Optional[float] = None


class RenewableCardResponse(BaseModel):
    user_card_id: int
    card_definition_id: int
    card_name: str
    valid_to: datetime
    days_to_expire: int  # 可为负（已过期）
    renew_strategy: str
    can_renew: bool
    reason: Optional[str] = None


class RenewableCardListResponse(BaseModel):
    total: int
    items: List[RenewableCardResponse]


# ───────────────────────────── Helpers ─────────────────────────────


def _gen_token() -> str:
    """32 位 url-safe token。"""
    return secrets.token_urlsafe(24)[:32]


def _gen_digits(seed: str) -> str:
    """6 位数字（基于卡 ID + 时间戳哈希取模，避免短期重复）。"""
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    n = int(h[:8], 16) % 1_000_000
    return f"{n:06d}"


def _normalize_status(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _generate_order_no() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"UO{ts}{rand}"


async def _get_user_card_owned(
    db: AsyncSession, user_id: int, user_card_id: int
) -> UserCard:
    res = await db.execute(
        select(UserCard).where(UserCard.id == user_card_id, UserCard.user_id == user_id)
    )
    uc = res.scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="未找到该卡")
    return uc


async def _expire_old_codes(db: AsyncSession, user_card_id: int) -> None:
    """把该卡名下所有 active 码瞬时改为 expired。"""
    res = await db.execute(
        select(CardRedemptionCode).where(
            CardRedemptionCode.user_card_id == user_card_id,
            CardRedemptionCode.status == CardRedemptionCodeStatus.active,
        )
    )
    for code in res.scalars().all():
        code.status = CardRedemptionCodeStatus.expired


async def _activate_user_card(
    db: AsyncSession, order: UnifiedOrder
) -> Optional[UserCard]:
    """支付成功后激活卡：写 user_cards、累加 sales_count。
    支持续卡（renew_from_user_card_id）按 STACK/RESET/DISABLED 策略合并。
    """
    if order.product_type != "card" or not order.card_definition_id:
        return None

    # 已激活防重
    existing_q = await db.execute(
        select(UserCard).where(UserCard.purchase_order_id == order.id)
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        return existing

    cd_res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == order.card_definition_id)
    )
    cd: Optional[CardDefinition] = cd_res.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义不存在")

    # 卡内项目快照
    items = cd.items or []
    pid_list = [it.product_id for it in items]
    items_snapshot = []
    if pid_list:
        prods = await db.execute(select(Product).where(Product.id.in_(pid_list)))
        pmap = {p.id: p for p in prods.scalars().all()}
        for it in items:
            p = pmap.get(it.product_id)
            if not p:
                continue
            first_img = None
            if p.images and isinstance(p.images, list) and p.images:
                first_img = p.images[0]
            items_snapshot.append(
                {
                    "product_id": p.id,
                    "product_name": p.name,
                    "product_image": first_img,
                }
            )

    now = datetime.utcnow()
    valid_days = int(cd.valid_days or 365)

    # 续卡分支
    renew_from_id = order.renew_from_user_card_id
    if renew_from_id:
        old_q = await db.execute(
            select(UserCard).where(
                UserCard.id == renew_from_id, UserCard.user_id == order.user_id
            )
        )
        old: Optional[UserCard] = old_q.scalar_one_or_none()
        if not old:
            raise HTTPException(status_code=404, detail="续卡来源不存在")
        strategy = cd.renew_strategy
        if hasattr(strategy, "value"):
            strategy_val = strategy.value
        else:
            strategy_val = str(strategy)

        if strategy_val in ("DISABLED",):
            raise HTTPException(status_code=400, detail="该卡不支持续卡")

        if strategy_val in ("STACK", "add_on"):
            # 叠加：剩余次数=老卡剩余+新卡总次数；有效期=老卡 valid_to 顺延 valid_days；过期则从今天起算
            base_to = old.valid_to if old.valid_to >= now else now
            new_valid_from = old.valid_from if old.valid_from <= now else now
            new_valid_to = base_to + timedelta(days=valid_days)
            new_remaining = (old.remaining_times or 0) + (cd.total_times or 0)
            new_card = UserCard(
                card_definition_id=cd.id,
                user_id=order.user_id,
                purchase_order_id=order.id,
                bound_items_snapshot={"items": items_snapshot, "snapshot_at": now.isoformat()},
                remaining_times=new_remaining,
                valid_from=new_valid_from,
                valid_to=new_valid_to,
                status=UserCardStatus.active,
                renewed_from_id=old.id,
                renew_count=(old.renew_count or 0) + 1,
            )
            # 老卡作废（合并到新卡）：用 expired 表示已被新卡接管
            old.status = UserCardStatus.expired
            db.add(new_card)
        else:  # RESET / new_card
            new_valid_from = now
            new_valid_to = now + timedelta(days=valid_days)
            new_card = UserCard(
                card_definition_id=cd.id,
                user_id=order.user_id,
                purchase_order_id=order.id,
                bound_items_snapshot={"items": items_snapshot, "snapshot_at": now.isoformat()},
                remaining_times=cd.total_times,
                valid_from=new_valid_from,
                valid_to=new_valid_to,
                status=UserCardStatus.active,
                renewed_from_id=old.id,
                renew_count=(old.renew_count or 0) + 1,
            )
            old.status = UserCardStatus.expired
            db.add(new_card)
    else:
        new_card = UserCard(
            card_definition_id=cd.id,
            user_id=order.user_id,
            purchase_order_id=order.id,
            bound_items_snapshot={"items": items_snapshot, "snapshot_at": now.isoformat()},
            remaining_times=cd.total_times,
            valid_from=now,
            valid_to=now + timedelta(days=valid_days),
            status=UserCardStatus.active,
            renew_count=0,
        )
        db.add(new_card)

    cd.sales_count = (cd.sales_count or 0) + 1
    await db.flush()
    await db.refresh(new_card)
    return new_card


# ───────────────────────────── 第 2 期：购卡下单 ─────────────────────────────


@router.post("/purchase", summary="发起购卡下单（第 2 期）")
async def purchase_card(
    data: CardPurchaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cd_res = await db.execute(
        select(CardDefinition).where(CardDefinition.id == data.card_definition_id)
    )
    cd: Optional[CardDefinition] = cd_res.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡不存在")

    cd_status = cd.status
    if hasattr(cd_status, "value"):
        cd_status = cd_status.value
    if cd_status != "active":
        raise HTTPException(status_code=400, detail="该卡未上架，无法购买")

    # 库存校验
    if cd.stock is not None:
        if int(cd.stock) <= 0:
            raise HTTPException(status_code=400, detail="库存不足")

    # 单用户限购校验
    if cd.per_user_limit is not None:
        own_q = await db.execute(
            select(func.count(UserCard.id)).where(
                UserCard.user_id == current_user.id,
                UserCard.card_definition_id == cd.id,
                UserCard.status == UserCardStatus.active,
            )
        )
        own_cnt = int(own_q.scalar() or 0)
        # 续卡场景下不计入限购
        if not data.renew_from_user_card_id and own_cnt >= int(cd.per_user_limit):
            raise HTTPException(status_code=400, detail="已达单用户限购")

    # 续卡校验
    if data.renew_from_user_card_id:
        old_q = await db.execute(
            select(UserCard).where(
                UserCard.id == data.renew_from_user_card_id,
                UserCard.user_id == current_user.id,
            )
        )
        old = old_q.scalar_one_or_none()
        if not old:
            raise HTTPException(status_code=404, detail="续卡来源不存在")
        strategy_val = old.card_definition.renew_strategy if old.card_definition else cd.renew_strategy
        if hasattr(strategy_val, "value"):
            strategy_val = strategy_val.value
        if strategy_val in ("DISABLED",):
            raise HTTPException(status_code=400, detail="该卡不支持续卡")

    # 创建订单
    order = UnifiedOrder(
        order_no=_generate_order_no(),
        user_id=current_user.id,
        total_amount=cd.price,
        paid_amount=0,
        status=UnifiedOrderStatus.pending_payment,
        product_type="card",
        card_definition_id=cd.id,
        items_snapshot={
            "card_definition_id": cd.id,
            "card_name": cd.name,
            "total_times": cd.total_times,
            "valid_days": cd.valid_days,
            "price": float(cd.price),
            "snapshot_at": datetime.utcnow().isoformat(),
            "from_product_id": data.from_product_id,
        },
        renew_from_user_card_id=data.renew_from_user_card_id,
        notes=data.notes,
    )
    db.add(order)

    # 库存扣减（一次性）
    if cd.stock is not None:
        cd.stock = max(0, int(cd.stock) - 1)

    await db.flush()
    await db.refresh(order)
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "total_amount": float(order.total_amount),
        "product_type": "card",
        "card_definition_id": cd.id,
        "from_product_id": data.from_product_id,
        "renew_from_user_card_id": data.renew_from_user_card_id,
        "status": _normalize_status(order.status),
    }


@order_card_router.post("/{order_id}/pay-card", summary="支付卡订单（第 2 期）—— 模拟支付回调")
async def pay_card_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """模拟支付成功 → 自动激活 user_card。

    生产环境的真实支付回调中也应调用 `_activate_user_card(db, order)`。
    """
    res = await db.execute(
        select(UnifiedOrder).where(
            UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id
        )
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.product_type != "card":
        raise HTTPException(status_code=400, detail="非卡订单")
    if _normalize_status(order.status) != "pending_payment":
        raise HTTPException(status_code=400, detail="该订单无法支付")

    order.status = UnifiedOrderStatus.completed  # 卡订单支付即完成
    order.paid_amount = order.total_amount
    order.paid_at = datetime.utcnow()
    order.completed_at = datetime.utcnow()

    user_card = await _activate_user_card(db, order)
    return {
        "message": "支付成功，卡已激活",
        "order_id": order.id,
        "user_card_id": user_card.id if user_card else None,
    }


# ───────────────────────────── 第 3 期：核销码 + 退款 ─────────────────────────────


@router.post(
    "/me/{user_card_id}/redemption-code",
    response_model=RedemptionCodeResponse,
    summary="生成新核销码（60 秒动态码 + 6 位数字）",
)
async def issue_redemption_code(
    user_card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = await _get_user_card_owned(db, current_user.id, user_card_id)
    if uc.status != UserCardStatus.active:
        raise HTTPException(status_code=400, detail="卡当前状态不可生成核销码")
    if uc.valid_to < datetime.utcnow():
        raise HTTPException(status_code=400, detail="卡已过期")
    if (uc.remaining_times or 0) <= 0:
        raise HTTPException(status_code=400, detail="剩余次数不足")

    await _expire_old_codes(db, uc.id)

    now = datetime.utcnow()
    token = _gen_token()
    digits = _gen_digits(f"{uc.id}-{now.timestamp()}-{secrets.token_hex(4)}")
    code = CardRedemptionCode(
        user_card_id=uc.id,
        code_token=token,
        code_digits=digits,
        issued_at=now,
        expires_at=now + timedelta(seconds=60),
        status=CardRedemptionCodeStatus.active,
    )
    db.add(code)
    await db.flush()
    await db.refresh(code)
    return RedemptionCodeResponse(
        user_card_id=uc.id,
        token=code.code_token,
        digits=code.code_digits,
        issued_at=code.issued_at,
        expires_at=code.expires_at,
        status=code.status.value,
    )


@router.get(
    "/me/{user_card_id}/redemption-code/current",
    response_model=Optional[RedemptionCodeResponse],
    summary="获取当前 active 核销码（无则返回 null）",
)
async def get_current_redemption_code(
    user_card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = await _get_user_card_owned(db, current_user.id, user_card_id)
    res = await db.execute(
        select(CardRedemptionCode)
        .where(
            CardRedemptionCode.user_card_id == uc.id,
            CardRedemptionCode.status == CardRedemptionCodeStatus.active,
            CardRedemptionCode.expires_at > datetime.utcnow(),
        )
        .order_by(CardRedemptionCode.issued_at.desc())
        .limit(1)
    )
    code = res.scalar_one_or_none()
    if not code:
        return None
    return RedemptionCodeResponse(
        user_card_id=uc.id,
        token=code.code_token,
        digits=code.code_digits,
        issued_at=code.issued_at,
        expires_at=code.expires_at,
        status=code.status.value,
    )


def _check_product_in_card(card: CardDefinition, product_id: int) -> bool:
    if not card.items:
        return False
    return any(it.product_id == product_id for it in card.items)


def _check_store_in_scope(card: CardDefinition, store_id: Optional[int]) -> bool:
    """卡门店范围校验。store_scope=None 视为 all。"""
    scope = card.store_scope
    if not scope:
        return True
    stype = scope.get("type") if isinstance(scope, dict) else None
    if stype == "all" or stype is None:
        return True
    if stype == "list":
        ids = scope.get("store_ids") or []
        if store_id is None:
            return False
        return int(store_id) in [int(x) for x in ids]
    return True


async def _check_frequency(
    db: AsyncSession, user_card: UserCard, card: CardDefinition
) -> bool:
    """频次校验：按 frequency_limit.scope (day/week) 限额。"""
    fl = card.frequency_limit
    if not fl:
        return True
    scope = fl.get("scope") if isinstance(fl, dict) else None
    times = int(fl.get("times", 0)) if isinstance(fl, dict) else 0
    if not scope or times <= 0:
        return True
    now = datetime.utcnow()
    if scope == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif scope == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        return True
    cnt_q = await db.execute(
        select(func.count(CardUsageLog.id)).where(
            CardUsageLog.user_card_id == user_card.id,
            CardUsageLog.used_at >= start,
        )
    )
    cnt = int(cnt_q.scalar() or 0)
    return cnt < times


@staff_router.post("/redeem", summary="门店扫码核销卡（第 3 期）")
async def staff_redeem_card(
    data: StaffRedeemRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-05 R-05-04] 卡核销同样属于"核销动作"范畴，PC 端不允许发起。
    if not data.code_token and not data.code_digits:
        raise HTTPException(status_code=400, detail="必须提供 code_token 或 code_digits")

    # 行锁查码
    stmt = select(CardRedemptionCode)
    if data.code_token:
        stmt = stmt.where(CardRedemptionCode.code_token == data.code_token)
    else:
        # 数字码可能多日期重复——优先取最新 active
        stmt = stmt.where(
            CardRedemptionCode.code_digits == data.code_digits,
            CardRedemptionCode.status == CardRedemptionCodeStatus.active,
        ).order_by(CardRedemptionCode.issued_at.desc()).limit(1)
    # 部分数据库不支持 with_for_update（如 sqlite），try/except 兜底
    try:
        stmt = stmt.with_for_update()
    except Exception:
        pass
    res = await db.execute(stmt)
    code: Optional[CardRedemptionCode] = res.scalar_one_or_none()
    if not code:
        raise HTTPException(status_code=404, detail="核销码无效")
    if code.status != CardRedemptionCodeStatus.active:
        raise HTTPException(status_code=409, detail="核销码已使用或失效")
    if code.expires_at < datetime.utcnow():
        code.status = CardRedemptionCodeStatus.expired
        await db.flush()
        raise HTTPException(status_code=410, detail="核销码已过期")

    uc_q = await db.execute(
        select(UserCard).where(UserCard.id == code.user_card_id)
    )
    uc: Optional[UserCard] = uc_q.scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="卡不存在")
    if uc.status != UserCardStatus.active:
        raise HTTPException(status_code=409, detail="卡已失效")
    if uc.valid_to < datetime.utcnow():
        uc.status = UserCardStatus.expired
        await db.flush()
        raise HTTPException(status_code=410, detail="卡已过期")
    if (uc.remaining_times or 0) <= 0:
        raise HTTPException(status_code=409, detail="剩余次数不足")

    cd_q = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == uc.card_definition_id)
    )
    cd: Optional[CardDefinition] = cd_q.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义不存在")

    if not _check_product_in_card(cd, data.product_id):
        raise HTTPException(status_code=403, detail="该项目不在卡内可用项目范围")

    if not _check_store_in_scope(cd, data.store_id):
        raise HTTPException(status_code=403, detail="该门店不在卡使用范围")

    if not await _check_frequency(db, uc, cd):
        raise HTTPException(status_code=429, detail="超频次")

    # 商家 ID 解析（用于第 5 期看板）
    merchant_id: Optional[int] = None
    if data.store_id:
        ms_q = await db.execute(
            select(MerchantStore).where(MerchantStore.id == data.store_id)
        )
        ms = ms_q.scalar_one_or_none()
        if ms and getattr(ms, "merchant_id", None):
            merchant_id = ms.merchant_id

    # 扣次 + 写日志 + 关闭码
    uc.remaining_times = (uc.remaining_times or 0) - 1
    if uc.remaining_times == 0:
        uc.status = UserCardStatus.used_up

    log = CardUsageLog(
        user_card_id=uc.id,
        product_id=data.product_id,
        store_id=data.store_id,
        technician_id=data.technician_id,
        merchant_id=merchant_id,
        used_at=datetime.utcnow(),
        notes=data.notes,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    code.status = CardRedemptionCodeStatus.used
    code.used_at = datetime.utcnow()
    code.used_by_log_id = log.id

    return {
        "message": "核销成功",
        "log_id": log.id,
        "user_card_id": uc.id,
        "remaining_times": uc.remaining_times,
        "card_status": uc.status.value,
    }


@router.get(
    "/me/{user_card_id}/usage-logs",
    response_model=CardUsageLogListResponse,
    summary="用户端我的卡核销记录",
)
async def my_card_usage_logs(
    user_card_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = await _get_user_card_owned(db, current_user.id, user_card_id)
    cnt_q = await db.execute(
        select(func.count(CardUsageLog.id)).where(CardUsageLog.user_card_id == uc.id)
    )
    total = int(cnt_q.scalar() or 0)
    res = await db.execute(
        select(CardUsageLog)
        .where(CardUsageLog.user_card_id == uc.id)
        .order_by(CardUsageLog.used_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = list(res.scalars().all())
    out: List[CardUsageLogResponse] = []
    if logs:
        pids = [l.product_id for l in logs]
        sids = [l.store_id for l in logs if l.store_id]
        pname_map = {}
        if pids:
            pres = await db.execute(
                select(Product.id, Product.name).where(Product.id.in_(pids))
            )
            pname_map = {row[0]: row[1] for row in pres.all()}
        sname_map = {}
        if sids:
            sres = await db.execute(
                select(MerchantStore.id, MerchantStore.store_name).where(
                    MerchantStore.id.in_(sids)
                )
            )
            sname_map = {row[0]: row[1] for row in sres.all()}
        for l in logs:
            out.append(
                CardUsageLogResponse(
                    id=l.id,
                    user_card_id=l.user_card_id,
                    product_id=l.product_id,
                    product_name=pname_map.get(l.product_id),
                    store_id=l.store_id,
                    store_name=sname_map.get(l.store_id) if l.store_id else None,
                    technician_id=l.technician_id,
                    used_at=l.used_at,
                    notes=l.notes,
                )
            )
    return CardUsageLogListResponse(total=total, items=out)


@order_card_router.post("/{order_id}/refund-card", summary="卡订单退款（第 3 期）")
async def refund_card_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(UnifiedOrder).where(
            UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id
        )
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.product_type != "card":
        raise HTTPException(status_code=400, detail="非卡订单")

    # 查找此订单激活的卡
    uc_q = await db.execute(
        select(UserCard).where(UserCard.purchase_order_id == order.id)
    )
    uc: Optional[UserCard] = uc_q.scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=400, detail="未找到对应卡，无法退款")

    cd_q = await db.execute(
        select(CardDefinition).where(CardDefinition.id == uc.card_definition_id)
    )
    cd: Optional[CardDefinition] = cd_q.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义不存在")

    # 退款规则：未核销全额退（remaining_times == total_times 且 status=active 且未过期）
    if uc.status != UserCardStatus.active:
        raise HTTPException(status_code=400, detail="卡当前状态不可退款")
    if uc.valid_to < datetime.utcnow():
        raise HTTPException(status_code=400, detail="卡已过期不可退款")
    if cd.total_times is not None and uc.remaining_times != cd.total_times:
        raise HTTPException(status_code=400, detail="已核销过的卡不可退款")

    # 退款执行
    uc.status = UserCardStatus.refunded
    await _expire_old_codes(db, uc.id)
    cd.sales_count = max(0, (cd.sales_count or 0) - 1)
    order.status = UnifiedOrderStatus.refunded
    order.refund_status = RefundStatusEnum.refund_success
    order.updated_at = datetime.utcnow()

    return {"message": "退款成功", "user_card_id": uc.id, "order_id": order.id}


# ───────────────────────────── 第 4 期：拆 2 单 + 续卡 + 省钱提示 ─────────────────────────────


@order_card_router.post("/checkout", summary="混买结算 —— 按 product_type 拆 2 单（第 4 期）")
async def checkout_split(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.items:
        raise HTTPException(status_code=400, detail="商品不能为空")

    card_items = [it for it in data.items if it.product_type == "card"]
    other_items = [it for it in data.items if it.product_type != "card"]

    split_group_id = uuid.uuid4().hex[:32]
    created_orders: List[int] = []

    if card_items:
        # 当前简化：每张卡都生成一个独立卡订单（PRD 主路径每次只买 1 张卡，但兼容多张）
        for ci in card_items:
            if not ci.card_definition_id:
                raise HTTPException(status_code=400, detail="card 商品必须传 card_definition_id")
            cd_q = await db.execute(
                select(CardDefinition).where(CardDefinition.id == ci.card_definition_id)
            )
            cd = cd_q.scalar_one_or_none()
            if not cd:
                raise HTTPException(status_code=404, detail=f"卡 {ci.card_definition_id} 不存在")
            order_card = UnifiedOrder(
                order_no=_generate_order_no(),
                user_id=current_user.id,
                total_amount=cd.price,
                paid_amount=0,
                status=UnifiedOrderStatus.pending_payment,
                product_type="card",
                card_definition_id=cd.id,
                items_snapshot={
                    "card_definition_id": cd.id,
                    "card_name": cd.name,
                    "total_times": cd.total_times,
                    "valid_days": cd.valid_days,
                    "price": float(cd.price),
                },
                split_group_id=split_group_id,
                notes=data.notes,
            )
            db.add(order_card)
            await db.flush()
            await db.refresh(order_card)
            created_orders.append(order_card.id)

    # 项目订单（普通商品集中合并为一笔）
    if other_items:
        total_amount = Decimal("0")
        order_items_pending: List[OrderItem] = []
        for it in other_items:
            if not it.product_id:
                continue
            p_q = await db.execute(select(Product).where(Product.id == it.product_id))
            p = p_q.scalar_one_or_none()
            if not p:
                raise HTTPException(status_code=404, detail=f"商品 {it.product_id} 不存在")
            unit = Decimal(str(p.sale_price))
            sub = unit * it.quantity
            total_amount += sub
            ft = p.fulfillment_type
            if hasattr(ft, "value"):
                ft = ft.value
            from app.models.models import FulfillmentType as FT_Enum
            ft_enum = FT_Enum(ft) if not isinstance(ft, FT_Enum) else ft
            first_image = None
            if p.images and isinstance(p.images, list) and p.images:
                first_image = p.images[0]
            order_items_pending.append(
                OrderItem(
                    product_id=p.id,
                    sku_id=it.sku_id,
                    product_name=p.name,
                    product_image=first_image,
                    product_price=unit,
                    quantity=it.quantity,
                    subtotal=sub,
                    fulfillment_type=ft_enum,
                    total_redeem_count=it.quantity,
                )
            )
        order_other = UnifiedOrder(
            order_no=_generate_order_no(),
            user_id=current_user.id,
            total_amount=total_amount,
            paid_amount=0,
            status=UnifiedOrderStatus.pending_payment,
            product_type="physical",
            split_group_id=split_group_id,
            notes=data.notes,
        )
        db.add(order_other)
        await db.flush()
        await db.refresh(order_other)
        for oi in order_items_pending:
            oi.order_id = order_other.id
            db.add(oi)
        await db.flush()
        created_orders.append(order_other.id)

    return {
        "split_group_id": split_group_id,
        "order_ids": created_orders,
    }


@router.post("/me/{user_card_id}/renew", summary="发起续卡（第 4 期）")
async def renew_card(
    user_card_id: int,
    data: RenewRequest = Body(default=RenewRequest()),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = await _get_user_card_owned(db, current_user.id, user_card_id)
    cd_q = await db.execute(
        select(CardDefinition).where(CardDefinition.id == uc.card_definition_id)
    )
    cd: Optional[CardDefinition] = cd_q.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义不存在")
    strategy = cd.renew_strategy
    if hasattr(strategy, "value"):
        strategy = strategy.value
    if strategy == "DISABLED":
        raise HTTPException(status_code=400, detail="该卡不支持续卡")

    # 临期 7 天 / 过期 30 天内可续
    now = datetime.utcnow()
    delta = (uc.valid_to - now).days
    if delta > 7 and uc.status == UserCardStatus.active:
        # 仍非临期不限制续——按 PRD 入口，但接口不做硬卡，让用户也能提前续
        pass
    if uc.status not in (UserCardStatus.active, UserCardStatus.expired):
        raise HTTPException(status_code=400, detail="该卡当前状态不可续卡")
    if uc.status == UserCardStatus.expired and delta < -30:
        raise HTTPException(status_code=400, detail="过期超过 30 天的卡不支持续卡")

    # 创建续卡订单
    order = UnifiedOrder(
        order_no=_generate_order_no(),
        user_id=current_user.id,
        total_amount=cd.price,
        paid_amount=0,
        status=UnifiedOrderStatus.pending_payment,
        product_type="card",
        card_definition_id=cd.id,
        items_snapshot={
            "card_definition_id": cd.id,
            "card_name": cd.name,
            "total_times": cd.total_times,
            "valid_days": cd.valid_days,
            "price": float(cd.price),
            "renew": True,
        },
        renew_from_user_card_id=uc.id,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "renew_from_user_card_id": uc.id,
        "card_definition_id": cd.id,
        "renew_strategy": strategy,
    }


@product_card_router.get(
    "/{product_id}/savings-tip",
    response_model=SavingsTipResponse,
    summary="商品省钱提示（第 4 期）",
)
async def product_savings_tip(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    p_q = await db.execute(select(Product).where(Product.id == product_id))
    p = p_q.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 找包含该商品的已上架卡，优先 single-amount 最大节省
    stmt = (
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .join(CardItem, CardItem.card_definition_id == CardDefinition.id)
        .where(
            CardItem.product_id == product_id,
            CardDefinition.status == CardStatus.active,
        )
    )
    cards = (await db.execute(stmt)).scalars().unique().all()
    if not cards:
        return SavingsTipResponse(has_card=False)

    best_card: Optional[CardDefinition] = None
    best_save: float = 0.0
    best_per_use: float = 0.0
    for c in cards:
        total_times = c.total_times or 1
        if total_times <= 0:
            continue
        per_use = float(c.price) / float(total_times)
        product_unit = float(p.sale_price or 0)
        save = max(0.0, (product_unit - per_use) * total_times)
        if save > best_save:
            best_save = save
            best_card = c
            best_per_use = per_use

    if not best_card:
        return SavingsTipResponse(has_card=False)
    return SavingsTipResponse(
        has_card=True,
        card_id=best_card.id,
        card_name=best_card.name,
        save_amount=round(best_save, 2),
        per_use_price=round(best_per_use, 2),
    )


@router.get(
    "/me/renewable",
    response_model=RenewableCardListResponse,
    summary="我的可续卡列表（临期 7 天 + 过期 30 天）",
)
async def my_renewable_cards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    soon = now + timedelta(days=7)
    expired_30d_ago = now - timedelta(days=30)

    # 临期 active 卡
    near_q = await db.execute(
        select(UserCard).where(
            UserCard.user_id == current_user.id,
            UserCard.status == UserCardStatus.active,
            UserCard.valid_to >= now,
            UserCard.valid_to <= soon,
        )
    )
    near_cards = list(near_q.scalars().all())

    # 已过期但 ≤ 30 天
    expired_q = await db.execute(
        select(UserCard).where(
            UserCard.user_id == current_user.id,
            UserCard.status == UserCardStatus.expired,
            UserCard.valid_to >= expired_30d_ago,
        )
    )
    expired_cards = list(expired_q.scalars().all())

    all_cards = near_cards + expired_cards
    if not all_cards:
        return RenewableCardListResponse(total=0, items=[])

    def_ids = list({uc.card_definition_id for uc in all_cards})
    defs_q = await db.execute(
        select(CardDefinition).where(CardDefinition.id.in_(def_ids))
    )
    def_map = {d.id: d for d in defs_q.scalars().all()}

    out: List[RenewableCardResponse] = []
    for uc in all_cards:
        cd = def_map.get(uc.card_definition_id)
        if not cd:
            continue
        strategy = cd.renew_strategy
        if hasattr(strategy, "value"):
            strategy = strategy.value
        days = (uc.valid_to - now).days
        can_renew = strategy != "DISABLED"
        out.append(
            RenewableCardResponse(
                user_card_id=uc.id,
                card_definition_id=cd.id,
                card_name=cd.name,
                valid_to=uc.valid_to,
                days_to_expire=days,
                renew_strategy=str(strategy),
                can_renew=can_renew,
                reason=None if can_renew else "该卡不支持续卡",
            )
        )
    return RenewableCardListResponse(total=len(out), items=out)
