"""卡功能 Admin 管理 API（PRD v1.1 第 1 期）。

仅 admin 可以操作；商家与 C 端无任何写入权限。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    CardDefinition,
    CardItem,
    CardRenewStrategy,
    CardScopeType,
    CardStatus,
    CardType,
    MerchantProfile,
    Product,
    User,
)
from app.schemas.cards import (
    CardDefinitionCreate,
    CardDefinitionResponse,
    CardDefinitionUpdate,
    CardItemRef,
    CardListResponse,
    CardStatusUpdate,
)


router = APIRouter(prefix="/api/admin/cards", tags=["卡管理（Admin）"])


# ─────────────── 帮助函数 ───────────────


async def _resolve_owner_merchant_name(db: AsyncSession, merchant_profile_id: Optional[int]) -> Optional[str]:
    if not merchant_profile_id:
        return None
    res = await db.execute(
        select(MerchantProfile, User.username, User.nickname)
        .join(User, User.id == MerchantProfile.user_id)
        .where(MerchantProfile.id == merchant_profile_id)
    )
    row = res.first()
    if not row:
        return None
    _, username, nickname = row
    return nickname or username or f"商家#{merchant_profile_id}"


async def _build_card_response(db: AsyncSession, card: CardDefinition) -> CardDefinitionResponse:
    items: list[CardItemRef] = []
    if card.items:
        product_ids = [it.product_id for it in card.items]
        if product_ids:
            res = await db.execute(select(Product).where(Product.id.in_(product_ids)))
            prod_map = {p.id: p for p in res.scalars().all()}
            for it in card.items:
                p = prod_map.get(it.product_id)
                if p is None:
                    continue
                first_img = None
                if p.images and isinstance(p.images, list) and p.images:
                    first_img = p.images[0]
                items.append(CardItemRef(
                    product_id=p.id,
                    product_name=p.name,
                    product_image=first_img,
                ))

    owner_name = await _resolve_owner_merchant_name(db, card.owner_merchant_id)

    return CardDefinitionResponse(
        id=card.id,
        name=card.name,
        cover_image=card.cover_image,
        description=card.description,
        card_type=card.card_type.value if hasattr(card.card_type, "value") else str(card.card_type),
        scope_type=card.scope_type.value if hasattr(card.scope_type, "value") else str(card.scope_type),
        owner_merchant_id=card.owner_merchant_id,
        owner_merchant_name=owner_name,
        price=card.price,
        original_price=card.original_price,
        total_times=card.total_times,
        valid_days=card.valid_days,
        frequency_limit=card.frequency_limit,
        store_scope=card.store_scope,
        stock=card.stock,
        per_user_limit=card.per_user_limit,
        renew_strategy=card.renew_strategy.value if hasattr(card.renew_strategy, "value") else str(card.renew_strategy),
        status=card.status.value if hasattr(card.status, "value") else str(card.status),
        sales_count=card.sales_count or 0,
        sort_order=card.sort_order or 0,
        items=items,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


async def _validate_item_product_ids(db: AsyncSession, product_ids: list[int]) -> None:
    if not product_ids:
        return
    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(status_code=400, detail="卡内项目存在重复商品")
    res = await db.execute(select(Product.id).where(Product.id.in_(product_ids)))
    found = {row[0] for row in res.all()}
    missing = [pid for pid in product_ids if pid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"商品不存在或已删除：{missing}")


async def _validate_owner_merchant(db: AsyncSession, merchant_profile_id: Optional[int]) -> None:
    if merchant_profile_id is None:
        return
    res = await db.execute(select(MerchantProfile).where(MerchantProfile.id == merchant_profile_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail=f"商家档案 ID 不存在：{merchant_profile_id}")


# ─────────────── 路由 ───────────────


@router.get("", response_model=CardListResponse, summary="卡定义列表（Admin）")
async def list_cards(
    keyword: Optional[str] = Query(default=None, description="按卡名模糊搜索"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="active|inactive|draft"),
    card_type: Optional[str] = Query(default=None, description="times|period"),
    scope_type: Optional[str] = Query(default=None, description="merchant|platform"),
    owner_merchant_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    stmt = select(CardDefinition).options(selectinload(CardDefinition.items))
    cnt_stmt = select(func.count(CardDefinition.id))
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(CardDefinition.name.like(like))
        cnt_stmt = cnt_stmt.where(CardDefinition.name.like(like))
    if status_filter:
        if status_filter not in {s.value for s in CardStatus}:
            raise HTTPException(status_code=400, detail="status 取值非法")
        stmt = stmt.where(CardDefinition.status == CardStatus(status_filter))
        cnt_stmt = cnt_stmt.where(CardDefinition.status == CardStatus(status_filter))
    if card_type:
        if card_type not in {t.value for t in CardType}:
            raise HTTPException(status_code=400, detail="card_type 取值非法")
        stmt = stmt.where(CardDefinition.card_type == CardType(card_type))
        cnt_stmt = cnt_stmt.where(CardDefinition.card_type == CardType(card_type))
    if scope_type:
        if scope_type not in {t.value for t in CardScopeType}:
            raise HTTPException(status_code=400, detail="scope_type 取值非法")
        stmt = stmt.where(CardDefinition.scope_type == CardScopeType(scope_type))
        cnt_stmt = cnt_stmt.where(CardDefinition.scope_type == CardScopeType(scope_type))
    if owner_merchant_id is not None:
        stmt = stmt.where(CardDefinition.owner_merchant_id == owner_merchant_id)
        cnt_stmt = cnt_stmt.where(CardDefinition.owner_merchant_id == owner_merchant_id)

    total = (await db.execute(cnt_stmt)).scalar() or 0
    stmt = stmt.order_by(CardDefinition.sort_order.desc(), CardDefinition.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    cards = (await db.execute(stmt)).scalars().all()

    items = [await _build_card_response(db, c) for c in cards]
    return CardListResponse(total=total, items=items)


@router.post("", response_model=CardDefinitionResponse, summary="新建卡定义（Admin）")
async def create_card(
    payload: CardDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    await _validate_owner_merchant(db, payload.owner_merchant_id)
    await _validate_item_product_ids(db, payload.item_product_ids)

    card = CardDefinition(
        name=payload.name.strip(),
        cover_image=payload.cover_image,
        description=payload.description,
        card_type=CardType(payload.card_type),
        scope_type=CardScopeType(payload.scope_type),
        owner_merchant_id=payload.owner_merchant_id,
        price=payload.price,
        original_price=payload.original_price,
        total_times=payload.total_times,
        valid_days=payload.valid_days,
        frequency_limit=payload.frequency_limit.model_dump() if payload.frequency_limit else None,
        store_scope=payload.store_scope.model_dump() if payload.store_scope else {"type": "all"},
        stock=payload.stock,
        per_user_limit=payload.per_user_limit,
        renew_strategy=CardRenewStrategy(payload.renew_strategy),
        status=CardStatus.draft,
        created_by_admin_id=user.id,
    )
    db.add(card)
    await db.flush()

    for pid in payload.item_product_ids:
        db.add(CardItem(card_definition_id=card.id, product_id=pid))

    await db.commit()
    await db.refresh(card, ["items"])
    return await _build_card_response(db, card)


@router.get("/{card_id}", response_model=CardDefinitionResponse, summary="卡定义详情（Admin）")
async def get_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == card_id)
    )
    card = res.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="卡不存在")
    return await _build_card_response(db, card)


@router.put("/{card_id}", response_model=CardDefinitionResponse, summary="编辑卡定义（Admin）")
async def update_card(
    card_id: int,
    payload: CardDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == card_id)
    )
    card = res.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="卡不存在")

    data = payload.model_dump(exclude_unset=True)

    if "owner_merchant_id" in data:
        await _validate_owner_merchant(db, data["owner_merchant_id"])

    for key in (
        "name",
        "cover_image",
        "description",
        "price",
        "original_price",
        "total_times",
        "valid_days",
        "stock",
        "per_user_limit",
        "owner_merchant_id",
        "sort_order",
    ):
        if key in data:
            setattr(card, key, data[key])

    if "card_type" in data:
        card.card_type = CardType(data["card_type"])
    if "scope_type" in data:
        card.scope_type = CardScopeType(data["scope_type"])
    if "renew_strategy" in data:
        card.renew_strategy = CardRenewStrategy(data["renew_strategy"])
    if "frequency_limit" in data:
        fl = data["frequency_limit"]
        card.frequency_limit = fl.model_dump() if hasattr(fl, "model_dump") else fl
    if "store_scope" in data:
        ss = data["store_scope"]
        card.store_scope = ss.model_dump() if hasattr(ss, "model_dump") else ss

    if "item_product_ids" in data and data["item_product_ids"] is not None:
        new_ids = data["item_product_ids"]
        await _validate_item_product_ids(db, new_ids)
        old_items_res = await db.execute(select(CardItem).where(CardItem.card_definition_id == card.id))
        for old in old_items_res.scalars().all():
            await db.delete(old)
        await db.flush()
        for pid in new_ids:
            db.add(CardItem(card_definition_id=card.id, product_id=pid))

    card.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(card, ["items"])
    return await _build_card_response(db, card)


@router.put("/{card_id}/status", response_model=CardDefinitionResponse, summary="上下架卡（Admin）")
async def update_card_status(
    card_id: int,
    payload: CardStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    res = await db.execute(
        select(CardDefinition)
        .options(selectinload(CardDefinition.items))
        .where(CardDefinition.id == card_id)
    )
    card = res.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="卡不存在")
    if payload.status == "active":
        if not card.items:
            raise HTTPException(status_code=400, detail="上架前必须先绑定至少一个项目")
    card.status = CardStatus(payload.status)
    card.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(card, ["items"])
    return await _build_card_response(db, card)


@router.delete("/{card_id}", summary="删除卡定义（Admin，仅 draft 可删除）")
async def delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    res = await db.execute(select(CardDefinition).where(CardDefinition.id == card_id))
    card = res.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="卡不存在")
    if card.status != CardStatus.draft:
        raise HTTPException(status_code=400, detail="仅草稿状态的卡可删除，已上架/下架的卡请先下架并清理用户卡")
    if (card.sales_count or 0) > 0:
        raise HTTPException(status_code=400, detail="存在销售记录，不可删除")
    await db.delete(card)
    await db.commit()
    return {"success": True, "id": card_id}
