"""服务列表带券过滤接口（OPT-1: 我的优惠券「去使用」入口）。

新接口：``GET /api/services/list?coupon_id={user_coupon_id}&page=&size=``

设计要点：
- 输入 ``coupon_id`` 是 **UserCoupon.id**（不是 Coupon 模板 ID），因此鉴权必须校验
  user_coupon 属于当前用户。不存在 / 已使用 / 已过期 → 返回 404。
- 根据 user_coupon → coupon 模板 → 按 scope 过滤服务列表：
  * scope=product → coupon.scope_ids 命中的 product 才返回
  * scope=category → coupon.scope_ids 命中的 category 下的全部商品才返回
  * scope=all → 全场通用，不过滤
- 返回顶部 ``coupon_banner``，前端用于显示"使用 XX 券下单"提示。
- 不传 coupon_id 时退化为无过滤的服务列表（与 /api/products 等价的轻量版本）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    CouponType,
    Product,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.products import ProductResponse

router = APIRouter(prefix="/api/services", tags=["服务列表（带券过滤）"])


def _normalize_int_list(raw) -> list[int]:
    """统一把 JSON / list / 逗号分隔字符串 / dict 转成 List[int]（保持顺序去重）。"""
    out: list[int] = []
    seen: set[int] = set()

    def _add(v):
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return
        if iv in seen:
            return
        seen.add(iv)
        out.append(iv)

    if raw is None:
        return out
    if isinstance(raw, list):
        for x in raw:
            _add(x)
    elif isinstance(raw, str):
        for x in raw.split(","):
            x = x.strip()
            if x:
                _add(x)
    elif isinstance(raw, dict):
        ids = raw.get("ids") if isinstance(raw, dict) else None
        if isinstance(ids, list):
            for x in ids:
                _add(x)
    return out


def _coupon_type_value(c: Coupon) -> str:
    return c.type.value if hasattr(c.type, "value") else str(c.type)


def _coupon_scope_value(c: Coupon) -> str:
    return c.scope.value if hasattr(c.scope, "value") else str(c.scope)


def _build_banner_subtitle(coupon: Coupon) -> str:
    """构建顶部券横幅副标题。

    - free_trial → "免费体验券，下单 0 元"
    - full_reduction → "满 X 减 Y"
    - discount → "X 折券" (rate=0.8 → 8 折)
    - voucher → "代金券：减 X 元"（无门槛）/ "满 X 减 Y"（有门槛）
    其中 free_trial 文案 改为"免费体验"以匹配 OPT-3。
    """
    t = _coupon_type_value(coupon)
    cond = float(coupon.condition_amount or 0)
    val = float(coupon.discount_value or 0)
    rate = float(coupon.discount_rate or 1.0)
    if t == "free_trial":
        return "免费体验券，下单 0 元抵扣"
    if t == "full_reduction":
        return f"满 {cond:g} 减 {val:g}"
    if t == "discount":
        zhe = round(rate * 10, 1)
        zhe_str = f"{zhe:g}"
        if cond > 0:
            return f"满 {cond:g} 享 {zhe_str} 折"
        return f"{zhe_str} 折券"
    if t == "voucher":
        if cond > 0:
            return f"满 {cond:g} 减 {val:g}"
        return f"无门槛代金券：减 {val:g} 元"
    return "优惠券"


def _build_coupon_banner(user_coupon: UserCoupon, coupon: Coupon) -> dict:
    scope = _coupon_scope_value(coupon)
    if scope == "all":
        title_suffix = "（全场通用）"
    elif scope == "product":
        title_suffix = "（指定服务可用）"
    elif scope == "category":
        title_suffix = "（指定品类可用）"
    else:
        title_suffix = ""
    return {
        "coupon_id": user_coupon.id,
        "title": f"使用「{coupon.name}」{title_suffix}",
        "subtitle": _build_banner_subtitle(coupon),
        "scope": scope,
        "type": _coupon_type_value(coupon),
    }


@router.get("/list")
async def list_services_with_coupon_filter(
    coupon_id: Optional[int] = Query(None, description="UserCoupon.id（不是 Coupon 模板 id）"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """OPT-1：服务列表 + 优惠券适用范围过滤。

    - 不传 ``coupon_id`` → 返回当前可购的服务列表（status=active），不过滤
    - 传 ``coupon_id`` → 校验 user_coupon 属于当前用户、状态可用，再按 scope 过滤
      * scope=product → 仅返回 coupon.scope_ids 命中的服务
      * scope=category → 仅返回该 category（含子类 ID 已固化）下的服务
      * scope=all → 全场通用，不过滤
      并在响应顶部附 ``coupon_banner``。
    """
    coupon_banner: Optional[dict] = None
    product_id_filter: Optional[list[int]] = None
    category_id_filter: Optional[list[int]] = None

    if coupon_id is not None:
        # 校验 user_coupon 属于当前用户 + 状态可用
        rs = await db.execute(
            select(UserCoupon).where(
                UserCoupon.id == int(coupon_id),
                UserCoupon.user_id == current_user.id,
            )
        )
        uc: Optional[UserCoupon] = rs.scalar_one_or_none()
        if not uc:
            raise HTTPException(status_code=404, detail="优惠券不存在或不属于当前用户")
        # 已使用 / 已过期 → 业务码错误（404）
        uc_status = uc.status.value if hasattr(uc.status, "value") else str(uc.status)
        if uc_status != "unused":
            raise HTTPException(status_code=404, detail="该优惠券已使用或已过期")
        if uc.expire_at is not None and uc.expire_at < datetime.utcnow():
            raise HTTPException(status_code=404, detail="该优惠券已过期")

        coupon_rs = await db.execute(select(Coupon).where(Coupon.id == uc.coupon_id))
        coupon: Optional[Coupon] = coupon_rs.scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=404, detail="优惠券模板不存在")

        coupon_banner = _build_coupon_banner(uc, coupon)
        scope = _coupon_scope_value(coupon)
        ids = _normalize_int_list(coupon.scope_ids)
        if scope == "product":
            product_id_filter = ids if ids else [-1]  # 空 → 强制空集
        elif scope == "category":
            category_id_filter = ids if ids else [-1]
        # scope=all → 不过滤

    # ── 构建查询 ──
    query = (
        select(Product)
        .options(selectinload(Product.skus))
        .where(Product.status == "active")
    )
    count_query = select(func.count(Product.id)).where(Product.status == "active")
    if product_id_filter is not None:
        query = query.where(Product.id.in_(product_id_filter))
        count_query = count_query.where(Product.id.in_(product_id_filter))
    if category_id_filter is not None:
        query = query.where(Product.category_id.in_(category_id_filter))
        count_query = count_query.where(Product.category_id.in_(category_id_filter))

    total = (await db.execute(count_query)).scalar() or 0

    rs = await db.execute(
        query.order_by(
            Product.recommend_weight.desc(),
            Product.sort_order.asc(),
            Product.sales_count.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [ProductResponse.model_validate(p).model_dump() for p in rs.scalars().all()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "coupon_banner": coupon_banner,
    }
