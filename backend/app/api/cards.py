"""卡功能 C 端 API（PRD v1.1 第 1 期）：
- 卡列表
- 卡详情
- 我的-卡包
- 商品的"可用卡"推荐
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    CardDefinition,
    CardItem,
    CardScopeType,
    CardStatus,
    CardType,
    Product,
    User,
    UserCard,
    UserCardStatus,
)
from app.schemas.cards import (
    CardItemRef,
    CardPublicListResponse,
    CardPublicResponse,
    ProductAvailableCardsResponse,
    UserCardListResponse,
    UserCardResponse,
)


router = APIRouter(prefix="/api/cards", tags=["卡功能（C 端）"])


# ─────────────── 帮助函数 ───────────────


async def _build_card_items(db: AsyncSession, card: CardDefinition) -> List[CardItemRef]:
    if not card.items:
        return []
    pids = [it.product_id for it in card.items]
    res = await db.execute(select(Product).where(Product.id.in_(pids)))
    pmap = {p.id: p for p in res.scalars().all()}
    out: List[CardItemRef] = []
    for it in card.items:
        p = pmap.get(it.product_id)
        if not p:
            continue
        first_img = None
        if p.images and isinstance(p.images, list) and p.images:
            first_img = p.images[0]
        out.append(CardItemRef(product_id=p.id, product_name=p.name, product_image=first_img))
    return out


async def _user_active_card_for_definition(
    db: AsyncSession, user_id: int, card_def_id: int
) -> Optional[UserCard]:
    """返回该用户当前持有的、该卡定义下"最近到期、仍处于 active 状态、未过期"的一张实卡。"""
    now = datetime.utcnow()
    res = await db.execute(
        select(UserCard)
        .where(
            UserCard.user_id == user_id,
            UserCard.card_definition_id == card_def_id,
            UserCard.status == UserCardStatus.active,
            UserCard.valid_to >= now,
        )
        .order_by(UserCard.valid_to.asc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _build_public_response(
    db: AsyncSession, card: CardDefinition, user: Optional[User] = None
) -> CardPublicResponse:
    items = await _build_card_items(db, card)
    user_active: Optional[UserCard] = None
    if user is not None:
        user_active = await _user_active_card_for_definition(db, user.id, card.id)

    days_to_expire: Optional[int] = None
    if user_active is not None:
        delta = (user_active.valid_to - datetime.utcnow()).days
        days_to_expire = max(0, int(delta))

    return CardPublicResponse(
        id=card.id,
        name=card.name,
        cover_image=card.cover_image,
        description=card.description,
        card_type=card.card_type.value if hasattr(card.card_type, "value") else str(card.card_type),
        scope_type=card.scope_type.value if hasattr(card.scope_type, "value") else str(card.scope_type),
        owner_merchant_id=card.owner_merchant_id,
        price=card.price,
        original_price=card.original_price,
        total_times=card.total_times,
        valid_days=card.valid_days,
        frequency_limit=card.frequency_limit,
        store_scope=card.store_scope,
        items=items,
        sales_count=card.sales_count or 0,
        face_style=getattr(card, "face_style", None) or "ST1",
        face_bg_code=getattr(card, "face_bg_code", None) or "BG1",
        face_show_flags=int(getattr(card, "face_show_flags", 7) or 7),
        face_layout=getattr(card, "face_layout", None) or "ON_CARD",
        user_has_active_card=user_active is not None,
        nearest_expiry_days=days_to_expire,
    )


# ─────────────── 路由：卡列表 / 卡详情 ───────────────


@router.get("", response_model=CardPublicListResponse, summary="C 端卡列表（仅展示已上架）")
async def list_cards_for_user(
    keyword: Optional[str] = Query(default=None),
    card_type: Optional[str] = Query(default=None),
    scope_type: Optional[str] = Query(default=None),
    owner_merchant_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.status == CardStatus.active)
    )
    cnt = select(func.count(CardDefinition.id)).where(CardDefinition.status == CardStatus.active)

    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(CardDefinition.name.like(like))
        cnt = cnt.where(CardDefinition.name.like(like))
    if card_type and card_type in {t.value for t in CardType}:
        stmt = stmt.where(CardDefinition.card_type == CardType(card_type))
        cnt = cnt.where(CardDefinition.card_type == CardType(card_type))
    if scope_type and scope_type in {t.value for t in CardScopeType}:
        stmt = stmt.where(CardDefinition.scope_type == CardScopeType(scope_type))
        cnt = cnt.where(CardDefinition.scope_type == CardScopeType(scope_type))
    if owner_merchant_id is not None:
        stmt = stmt.where(CardDefinition.owner_merchant_id == owner_merchant_id)
        cnt = cnt.where(CardDefinition.owner_merchant_id == owner_merchant_id)

    total = (await db.execute(cnt)).scalar() or 0
    stmt = stmt.order_by(CardDefinition.sort_order.desc(), CardDefinition.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    cards = (await db.execute(stmt)).scalars().all()

    items = [await _build_public_response(db, c) for c in cards]
    return CardPublicListResponse(total=total, items=items)


@router.get("/{card_id}", response_model=CardPublicResponse, summary="C 端卡详情")
async def get_card_for_user(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == card_id, CardDefinition.status == CardStatus.active)
    )
    card = res.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="卡不存在或已下架")
    return await _build_public_response(db, card)


# ─────────────── 我的-卡包 ───────────────


def _build_user_card_response(
    user_card: UserCard,
    card_def: CardDefinition,
    items: List[CardItemRef],
) -> UserCardResponse:
    days_to_expire = None
    if user_card.valid_to:
        days_to_expire = max(0, (user_card.valid_to - datetime.utcnow()).days)

    return UserCardResponse(
        id=user_card.id,
        card_definition_id=user_card.card_definition_id,
        card_name=card_def.name,
        cover_image=card_def.cover_image,
        card_type=card_def.card_type.value if hasattr(card_def.card_type, "value") else str(card_def.card_type),
        scope_type=card_def.scope_type.value if hasattr(card_def.scope_type, "value") else str(card_def.scope_type),
        bound_items=items,
        remaining_times=user_card.remaining_times,
        total_times=card_def.total_times,
        frequency_limit=card_def.frequency_limit,
        valid_from=user_card.valid_from,
        valid_to=user_card.valid_to,
        status=user_card.status.value if hasattr(user_card.status, "value") else str(user_card.status),
        days_to_expire=days_to_expire,
        purchase_order_id=user_card.purchase_order_id,
        created_at=user_card.created_at,
        face_style=getattr(card_def, "face_style", None) or "ST1",
        face_bg_code=getattr(card_def, "face_bg_code", None) or "BG1",
        face_show_flags=int(getattr(card_def, "face_show_flags", 7) or 7),
        face_layout=getattr(card_def, "face_layout", None) or "ON_CARD",
        price=card_def.price,
        original_price=card_def.original_price,
        description=card_def.description,
    )


@router.get("/me/wallet", response_model=UserCardListResponse, summary="我的-卡包（按 status 过滤）")
async def my_card_wallet(
    status_filter: Optional[str] = Query(default=None, alias="status",
                                          description="active|used_up|expired|refunded；不传则返回全部"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """先把过期但状态仍 active 的实卡刷为 expired（懒迁移）"""
    now = datetime.utcnow()
    expired_res = await db.execute(
        select(UserCard).where(
            UserCard.user_id == user.id,
            UserCard.status == UserCardStatus.active,
            UserCard.valid_to < now,
        )
    )
    for uc in expired_res.scalars().all():
        uc.status = UserCardStatus.expired
    await db.flush()

    base = select(UserCard).where(UserCard.user_id == user.id)
    if status_filter:
        if status_filter not in {s.value for s in UserCardStatus}:
            raise HTTPException(status_code=400, detail="status 取值非法")
        base = base.where(UserCard.status == UserCardStatus(status_filter))

    base = base.order_by(UserCard.created_at.desc())
    user_cards = (await db.execute(base)).scalars().all()

    # 计数
    cnt_res = await db.execute(
        select(UserCard.status, func.count(UserCard.id))
        .where(UserCard.user_id == user.id)
        .group_by(UserCard.status)
    )
    cnt_map = {row[0]: row[1] for row in cnt_res.all()}

    def _cnt(s: UserCardStatus) -> int:
        return int(cnt_map.get(s, 0))

    if not user_cards:
        await db.commit()
        return UserCardListResponse(
            total=0,
            unused_count=_cnt(UserCardStatus.active),  # 第 1 期：未消费过 = active 简化处理
            in_use_count=0,
            expired_count=_cnt(UserCardStatus.expired),
            items=[],
        )

    def_ids = list({uc.card_definition_id for uc in user_cards})
    defs_res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id.in_(def_ids))
    )
    def_map = {d.id: d for d in defs_res.scalars().all()}

    out: List[UserCardResponse] = []
    for uc in user_cards:
        cd = def_map.get(uc.card_definition_id)
        if not cd:
            continue
        items = await _build_card_items(db, cd)
        out.append(_build_user_card_response(uc, cd, items))

    await db.commit()

    # 第 1 期：未使用 = active 且 remaining_times 等于卡定义 total_times；使用中 = active 但已使用过
    unused_count = 0
    in_use_count = 0
    for uc in (await db.execute(
        select(UserCard).where(UserCard.user_id == user.id, UserCard.status == UserCardStatus.active)
    )).scalars().all():
        cd = def_map.get(uc.card_definition_id)
        if not cd:
            continue
        if cd.card_type == CardType.times and (uc.remaining_times == cd.total_times):
            unused_count += 1
        else:
            in_use_count += 1

    return UserCardListResponse(
        total=len(out),
        unused_count=unused_count,
        in_use_count=in_use_count,
        expired_count=_cnt(UserCardStatus.expired),
        items=out,
    )


@router.get("/me/{user_card_id}", response_model=UserCardResponse, summary="我的卡详情（单张）")
async def my_user_card_detail(
    user_card_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(UserCard).where(UserCard.id == user_card_id, UserCard.user_id == user.id)
    )
    uc = res.scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="未找到该卡")
    cd_res = await db.execute(
        select(CardDefinition).options(selectinload(CardDefinition.items)).where(
            CardDefinition.id == uc.card_definition_id
        )
    )
    cd = cd_res.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义已被删除")
    items = await _build_card_items(db, cd)
    return _build_user_card_response(uc, cd, items)


# ─────────────── 商品详情页：可用卡推荐 ───────────────


@router.get(
    "/by-product/{product_id}",
    response_model=ProductAvailableCardsResponse,
    summary="商品详情页可用卡推荐（卡内项目包含本商品的所有已上架卡）",
)
async def list_cards_for_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    p_res = await db.execute(select(Product).where(Product.id == product_id))
    if not p_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="商品不存在")

    stmt = (
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .join(CardItem, CardItem.card_definition_id == CardDefinition.id)
        .where(
            CardItem.product_id == product_id,
            CardDefinition.status == CardStatus.active,
        )
        .order_by(CardDefinition.sort_order.desc(), CardDefinition.id.desc())
    )
    cards = (await db.execute(stmt)).scalars().unique().all()

    out: List[CardPublicResponse] = []
    for c in cards:
        out.append(await _build_public_response(db, c))
    return ProductAvailableCardsResponse(product_id=product_id, items=out)
