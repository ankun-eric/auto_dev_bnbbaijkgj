"""管理后台 - 优惠券模板管理 + 发放记录 + 4 种发放方式 + 兑换码 + 第三方合作方"""
import csv
import io
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    Coupon,
    CouponCodeBatch,
    CouponGrant,
    CouponOpLog,
    CouponRedeemCode,
    Partner,
    Product,
    ProductCategory,
    SystemConfig,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.coupons import (
    CodeBatchVoidRequest,
    CodeVoidRequest,
    COUPON_TYPE_DESCRIPTIONS,
    CouponCreate,
    CouponOfflineRequest,
    CouponResponse,
    CouponUpdate,
    DEFAULT_COUPON_EXCLUDE_MAX_PRODUCTS,
    DEFAULT_COUPON_SCOPE_MAX_PRODUCTS,
    DirectGrantRequest,
    GrantRecallRequest,
    OFFLINE_REASON_PRESETS,
    PartnerCreate,
    PartnerResponse,
    PartnerUpdate,
    RedeemCodeBatchCreate,
    VALIDITY_DAYS_OPTIONS,
)

admin_dep = require_role("admin")

router = APIRouter(prefix="/api/admin/coupons", tags=["管理后台-优惠券"])
partner_router = APIRouter(prefix="/api/admin/partners", tags=["管理后台-合作方"])
new_user_router = APIRouter(prefix="/api/admin/new-user-coupons", tags=["管理后台-新人券"])


def _calc_expire_at(coupon: Coupon, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.utcnow()
    days = coupon.validity_days or 30
    return base + timedelta(days=days)


def _coupon_to_dict(c: Coupon) -> dict:
    # 兼容历史 scope_ids：如果是字符串 "1,2,3" 自动转数组（PRD F7 兜底）
    raw_scope_ids = c.scope_ids
    if isinstance(raw_scope_ids, str):
        try:
            raw_scope_ids = [int(x.strip()) for x in raw_scope_ids.split(",") if x.strip()]
        except Exception:
            raw_scope_ids = None
    raw_exclude_ids = getattr(c, "exclude_ids", None)
    if isinstance(raw_exclude_ids, str):
        try:
            raw_exclude_ids = [int(x.strip()) for x in raw_exclude_ids.split(",") if x.strip()]
        except Exception:
            raw_exclude_ids = None
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type.value if hasattr(c.type, "value") else str(c.type),
        "condition_amount": float(c.condition_amount or 0),
        "discount_value": float(c.discount_value or 0),
        "discount_rate": float(c.discount_rate or 1.0),
        "scope": c.scope.value if hasattr(c.scope, "value") else str(c.scope),
        "scope_ids": raw_scope_ids,
        "exclude_ids": raw_exclude_ids,
        "total_count": c.total_count or 0,
        "claimed_count": c.claimed_count or 0,
        "used_count": c.used_count or 0,
        "validity_days": c.validity_days or 30,
        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
        # V2.1 下架字段
        "is_offline": bool(getattr(c, "is_offline", False)),
        "offline_reason": getattr(c, "offline_reason", None),
        "offline_at": c.offline_at.isoformat() if getattr(c, "offline_at", None) else None,
        "offline_by": getattr(c, "offline_by", None),
        "points_exchange_limit": getattr(c, "points_exchange_limit", None),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ─── V2.2 适用范围工具函数 ───


async def _get_int_config(db: AsyncSession, key: str, default: int) -> int:
    cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )).scalar_one_or_none()
    if not cfg or not cfg.config_value:
        return default
    try:
        return int(cfg.config_value)
    except (TypeError, ValueError):
        return default


def _normalize_int_list(value: Any) -> list[int]:
    """把任意输入（list / 字符串 "1,2,3" / None）规范为 list[int]，去重保序。"""
    if value is None:
        return []
    raw_iter: list[Any]
    if isinstance(value, (list, tuple, set)):
        raw_iter = list(value)
    elif isinstance(value, str):
        raw_iter = [x.strip() for x in value.split(",") if x.strip()]
    else:
        raw_iter = [value]
    out: list[int] = []
    seen: set[int] = set()
    for item in raw_iter:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _allowed_fulfillment_filter():
    """优惠券适用商品仅限：实物快递 + 到店服务（虚拟商品本期不纳入，PRD BR-5）。"""
    return Product.fulfillment_type.in_(("delivery", "in_store"))


async def _validate_scope_payload(
    db: AsyncSession,
    scope: str,
    scope_ids: Any,
    exclude_ids: Any,
    *,
    coupon_type: Optional[str] = None,
):
    """V2.2：保存优惠券前的适用范围 / 排除商品综合校验（PRD F9）。

    返回规范化后的 (scope_ids_list, exclude_ids_list)。
    """
    scope_ids_list = _normalize_int_list(scope_ids)
    exclude_ids_list = _normalize_int_list(exclude_ids)
    scope_max = await _get_int_config(db, "coupon_scope_max_products", DEFAULT_COUPON_SCOPE_MAX_PRODUCTS)
    exclude_max = await _get_int_config(db, "coupon_exclude_max_products", DEFAULT_COUPON_EXCLUDE_MAX_PRODUCTS)

    if scope == "category":
        if not scope_ids_list:
            raise HTTPException(status_code=400, detail="请至少选择 1 个分类")
        rs = await db.execute(
            select(ProductCategory.id).where(ProductCategory.id.in_(scope_ids_list))
        )
        existing = {r[0] for r in rs.all()}
        missing = [i for i in scope_ids_list if i not in existing]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"分类 {missing} 不存在或已删除，请重新选择",
            )
    elif scope == "product":
        if not scope_ids_list:
            raise HTTPException(status_code=400, detail="请至少选择 1 个商品")
        if len(scope_ids_list) > scope_max:
            raise HTTPException(
                status_code=400,
                detail=f"适用商品最多 {scope_max} 个，建议改用指定分类模式",
            )
        rs = await db.execute(
            select(Product.id, Product.fulfillment_type).where(Product.id.in_(scope_ids_list))
        )
        rows = rs.all()
        existing_ids = {r[0] for r in rows}
        missing = [i for i in scope_ids_list if i not in existing_ids]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"商品 {missing} 不存在或已删除，请重新选择",
            )
        # 虚拟商品过滤：禁止把 virtual 商品加入适用范围
        bad_virtual = []
        for pid, ft in rows:
            ft_val = ft.value if hasattr(ft, "value") else str(ft)
            if ft_val not in ("delivery", "in_store"):
                bad_virtual.append(pid)
        if bad_virtual:
            raise HTTPException(
                status_code=400,
                detail=f"商品 {bad_virtual} 为虚拟商品，本期不支持加入优惠券适用范围",
            )

    # 排除商品仅在 all/category 时允许；scope=product 时强制清空
    if scope == "product":
        exclude_ids_list = []

    if exclude_ids_list:
        if len(exclude_ids_list) > exclude_max:
            raise HTTPException(
                status_code=400,
                detail=f"排除商品最多 {exclude_max} 个",
            )
        rs = await db.execute(
            select(Product.id, Product.category_id, Product.fulfillment_type)
            .where(Product.id.in_(exclude_ids_list))
        )
        rows = rs.all()
        existing_ids = {r[0] for r in rows}
        missing = [i for i in exclude_ids_list if i not in existing_ids]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"排除商品 {missing} 不存在或已删除",
            )
        # 排除不能与"指定商品"列表重叠（防御，scope=product 已清空）
        if scope == "product" and (set(exclude_ids_list) & set(scope_ids_list)):
            raise HTTPException(
                status_code=422,
                detail="排除商品与已选商品冲突",
            )
        # category 模式下，排除商品必须实际属于已选分类范围（含一级 + 子分类）
        if scope == "category":
            allowed_cats = await _expand_category_ids_with_children(db, scope_ids_list)
            for pid, cat_id, _ in rows:
                if cat_id not in allowed_cats:
                    raise HTTPException(
                        status_code=400,
                        detail=f"排除商品 [ID:{pid}] 不在已选分类范围内，无法排除",
                    )

    if coupon_type == "free_trial" and scope == "all":
        # 黄色警告由前端展示二次确认，这里仅在 scope=all + free_trial 时不阻断保存
        pass

    return scope_ids_list, exclude_ids_list


async def _expand_category_ids_with_children(
    db: AsyncSession, category_ids: list[int]
) -> set[int]:
    """把分类 ID 列表扩展为「自身 + 其全部子分类」。本项目分类层级最多 2 级（level=1/2），
    一次 IN 查询 children 即可覆盖。"""
    base = set(category_ids)
    if not base:
        return base
    rs = await db.execute(
        select(ProductCategory.id).where(ProductCategory.parent_id.in_(category_ids))
    )
    base.update({r[0] for r in rs.all()})
    return base


def _mask_code(code: str) -> str:
    """V2.1：兑换码脱敏：ABCD****1234（前 4 + 后 4，中间 4 星）"""
    if not code:
        return ""
    if len(code) <= 8:
        return code[:2] + "****" + code[-2:] if len(code) >= 4 else "****"
    return f"{code[:4]}****{code[-4:]}"


async def _add_op_log(
    db: AsyncSession,
    op_type: str,
    target_type: str,
    target_id: int,
    operator: User,
    reason: Optional[str] = None,
    extra: Optional[dict] = None,
):
    db.add(CouponOpLog(
        op_type=op_type,
        target_type=target_type,
        target_id=target_id,
        operator_id=operator.id,
        operator_name=operator.nickname or operator.phone or f"admin#{operator.id}",
        reason=reason,
        extra=extra,
    ))


async def _is_new_user_coupon(db: AsyncSession, coupon_id: int) -> bool:
    """V2.1：判断该券是否在当前 NEW_USER_COUPON_KEY 配置中。"""
    cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "new_user_coupon_ids")
    )).scalar_one_or_none()
    if not cfg or not cfg.config_value:
        return False
    try:
        import json as _json
        ids = _json.loads(cfg.config_value)
        return coupon_id in ids
    except Exception:
        return False


# ─── 优惠券模板 CRUD ───


@router.get("")
async def list_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    is_offline: Optional[bool] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Coupon)
    count_query = select(func.count(Coupon.id))
    if status:
        query = query.where(Coupon.status == status)
        count_query = count_query.where(Coupon.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(Coupon.name.like(like))
        count_query = count_query.where(Coupon.name.like(like))
    # V2.1：按已下架筛选
    if is_offline is not None:
        query = query.where(Coupon.is_offline == is_offline)
        count_query = count_query.where(Coupon.is_offline == is_offline)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Coupon.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [_coupon_to_dict(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/validity-options")
async def get_validity_options(_: User = Depends(admin_dep)):
    """有效期 8 档下拉选项"""
    return {"options": VALIDITY_DAYS_OPTIONS}


# ─── V2.2：优惠券类型说明（PRD F1）───
# 注：此处为静态路径端点，必须声明在 `@router.put("/{coupon_id}")` 之前，
# 否则会被 path 通配吃掉返回 405。


@router.get("/type-descriptions")
async def get_type_descriptions(_: User = Depends(admin_dep)):
    """优惠券 4 种类型说明（用于"?" 信息图标弹窗）。"""
    return {"items": COUPON_TYPE_DESCRIPTIONS}


# ─── V2.2：适用范围相关上限配置（PRD F5/F6）───


@router.get("/scope-limits")
async def get_scope_limits(
    _: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """读取后台动态配置的适用商品 / 排除商品上限。"""
    scope_max = await _get_int_config(db, "coupon_scope_max_products", DEFAULT_COUPON_SCOPE_MAX_PRODUCTS)
    exclude_max = await _get_int_config(db, "coupon_exclude_max_products", DEFAULT_COUPON_EXCLUDE_MAX_PRODUCTS)
    return {
        "scope_max_products": scope_max,
        "exclude_max_products": exclude_max,
    }


# ─── V2.2：商品弹窗选择器（PRD F4）───


@router.get("/product-picker")
async def coupon_product_picker(
    fulfillment_type: str = Query("all"),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    selected_ids: Optional[str] = Query(None, description="已选商品 ID 数组，逗号分隔（用于批量回显）"),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """优惠券适用商品 / 排除商品弹窗选择器数据源。

    强制只查 status=active + fulfillment_type∈{delivery,in_store}（虚拟商品本期不纳入）。
    selected_ids 仅用于"批量回显已选商品详情"，不影响主列表分页。
    """
    base_filter = and_(
        Product.status == "active",
        _allowed_fulfillment_filter(),
    )
    query = select(Product).where(base_filter)
    count_query = select(func.count(Product.id)).where(base_filter)

    if fulfillment_type in ("delivery", "in_store"):
        query = query.where(Product.fulfillment_type == fulfillment_type)
        count_query = count_query.where(Product.fulfillment_type == fulfillment_type)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.where(Product.name.like(like))
        count_query = count_query.where(Product.name.like(like))
    if category_id:
        cat_ids = await _expand_category_ids_with_children(db, [category_id])
        query = query.where(Product.category_id.in_(cat_ids))
        count_query = count_query.where(Product.category_id.in_(cat_ids))

    total = (await db.execute(count_query)).scalar() or 0
    rs = await db.execute(
        query.order_by(Product.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    products = rs.scalars().all()

    cat_ids_to_load = list({p.category_id for p in products if p.category_id})
    cat_map: dict[int, str] = {}
    if cat_ids_to_load:
        rs2 = await db.execute(
            select(ProductCategory.id, ProductCategory.name)
            .where(ProductCategory.id.in_(cat_ids_to_load))
        )
        cat_map = {row[0]: row[1] for row in rs2.all()}

    def _row(p: Product) -> dict:
        ft = p.fulfillment_type.value if hasattr(p.fulfillment_type, "value") else str(p.fulfillment_type)
        images = p.images if isinstance(p.images, list) else []
        return {
            "id": p.id,
            "name": p.name,
            "image": images[0] if images else None,
            "category_id": p.category_id,
            "category_name": cat_map.get(p.category_id),
            "price": float(p.sale_price or 0),
            "stock": p.stock if ft == "delivery" else None,
            "fulfillment_type": ft,
        }

    items = [_row(p) for p in products]

    selected_items: list[dict] = []
    if selected_ids:
        sel_ids = _normalize_int_list(selected_ids)
        if sel_ids:
            rs3 = await db.execute(select(Product).where(Product.id.in_(sel_ids)))
            sel_products = {p.id: p for p in rs3.scalars().all()}
            sel_cat_ids = list({p.category_id for p in sel_products.values() if p.category_id})
            sel_cat_map: dict[int, str] = {}
            if sel_cat_ids:
                rs4 = await db.execute(
                    select(ProductCategory.id, ProductCategory.name)
                    .where(ProductCategory.id.in_(sel_cat_ids))
                )
                sel_cat_map = {row[0]: row[1] for row in rs4.all()}
            for sid in sel_ids:
                p = sel_products.get(sid)
                if not p:
                    selected_items.append({
                        "id": sid,
                        "name": None,
                        "missing": True,
                        "deleted": True,
                        "off_shelf": False,
                    })
                    continue
                ft = p.fulfillment_type.value if hasattr(p.fulfillment_type, "value") else str(p.fulfillment_type)
                status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
                images = p.images if isinstance(p.images, list) else []
                selected_items.append({
                    "id": p.id,
                    "name": p.name,
                    "image": images[0] if images else None,
                    "category_id": p.category_id,
                    "category_name": sel_cat_map.get(p.category_id),
                    "price": float(p.sale_price or 0),
                    "stock": p.stock if ft == "delivery" else None,
                    "fulfillment_type": ft,
                    "missing": False,
                    "deleted": False,
                    "off_shelf": status_val != "active",
                })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "selected_items": selected_items,
    }


# ─── V2.2：分类树形选择器 + 按 IDs 批量查（PRD F3 / F7）───


@router.get("/category-tree")
async def coupon_category_tree(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """优惠券分类树形选择器数据源（仅 active 分类）。"""
    rs = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.status == "active")
        .order_by(ProductCategory.level.asc(), ProductCategory.sort_order.asc())
    )
    cats = rs.scalars().all()
    nodes: dict[int, dict] = {}
    roots: list[dict] = []
    for c in cats:
        nodes[c.id] = {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "level": c.level,
            "children": [],
        }
    for c in cats:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return {"items": roots}


@router.get("/categories-by-ids")
async def coupon_categories_by_ids(
    ids: str = Query(..., description="分类 ID 列表，逗号分隔（用于编辑回填）"),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """按 ID 批量查分类详情（编辑历史优惠券回填用）。已删除的分类标记 missing=true。"""
    id_list = _normalize_int_list(ids)
    if not id_list:
        return {"items": []}
    rs = await db.execute(
        select(ProductCategory).where(ProductCategory.id.in_(id_list))
    )
    found = {c.id: c for c in rs.scalars().all()}
    items = []
    for cid in id_list:
        c = found.get(cid)
        if not c:
            items.append({"id": cid, "name": None, "missing": True})
            continue
        items.append({
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "level": c.level,
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "missing": False,
        })
    return {"items": items}


# ─── V2.2：分类下商品数统计（PRD F8 适用范围预览）───


@router.get("/category-product-count")
async def coupon_category_product_count(
    category_ids: str = Query(..., description="分类 ID 列表，逗号分隔"),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """统计「这些分类（含子分类）+ 实物快递/到店服务 + active」对应的商品数。"""
    id_list = _normalize_int_list(category_ids)
    if not id_list:
        return {"category_count": 0, "product_count": 0}
    expanded = await _expand_category_ids_with_children(db, id_list)
    cnt = (await db.execute(
        select(func.count(Product.id)).where(
            Product.status == "active",
            _allowed_fulfillment_filter(),
            Product.category_id.in_(expanded),
        )
    )).scalar() or 0
    return {
        "category_count": len(id_list),
        "product_count": int(cnt),
    }


@router.get("/active-product-count")
async def coupon_active_product_count(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """全店在售商品数（用于 scope=all 的预览）。"""
    cnt = (await db.execute(
        select(func.count(Product.id)).where(
            Product.status == "active",
            _allowed_fulfillment_filter(),
        )
    )).scalar() or 0
    return {"product_count": int(cnt)}


@router.post("")
async def create_coupon(
    data: CouponCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.validity_days not in VALIDITY_DAYS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"有效期天数必须为 {VALIDITY_DAYS_OPTIONS} 之一")
    # V2.2 适用范围 / 排除商品综合校验
    scope_ids_list, exclude_ids_list = await _validate_scope_payload(
        db, data.scope, data.scope_ids, data.exclude_ids, coupon_type=data.type,
    )
    c = Coupon(
        name=data.name,
        type=data.type,
        condition_amount=data.condition_amount,
        discount_value=data.discount_value,
        discount_rate=data.discount_rate,
        scope=data.scope,
        scope_ids=scope_ids_list if scope_ids_list else None,
        exclude_ids=exclude_ids_list if exclude_ids_list else None,
        total_count=data.total_count,
        validity_days=data.validity_days,
        status=data.status,
        points_exchange_limit=data.points_exchange_limit,
    )
    db.add(c)
    await db.flush()
    return _coupon_to_dict(c)


@router.put("/{coupon_id}")
async def update_coupon(
    coupon_id: int,
    data: CouponUpdate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    if data.validity_days is not None and data.validity_days not in VALIDITY_DAYS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"有效期天数必须为 {VALIDITY_DAYS_OPTIONS} 之一")

    # 计算保存后的 scope / scope_ids / exclude_ids 三元组并统一校验
    new_scope = data.scope if data.scope is not None else (
        c.scope.value if hasattr(c.scope, "value") else str(c.scope)
    )
    new_scope_ids = data.scope_ids if data.scope_ids is not None else c.scope_ids
    new_exclude_ids = data.exclude_ids if data.exclude_ids is not None else c.exclude_ids
    new_type = data.type if data.type is not None else (
        c.type.value if hasattr(c.type, "value") else str(c.type)
    )
    scope_ids_list, exclude_ids_list = await _validate_scope_payload(
        db, new_scope, new_scope_ids, new_exclude_ids, coupon_type=new_type,
    )

    for f in ("name", "type", "condition_amount", "discount_value", "discount_rate",
              "total_count", "validity_days", "status", "points_exchange_limit"):
        v = getattr(data, f)
        if v is not None:
            setattr(c, f, v)
    # 适用范围相关字段统一覆盖（即使未传也按校验后的结果写回，确保 product↔category 切换时清理 exclude_ids）
    c.scope = new_scope
    c.scope_ids = scope_ids_list if scope_ids_list else None
    c.exclude_ids = exclude_ids_list if exclude_ids_list else None
    return _coupon_to_dict(c)


# ─── V2.1：禁删除，仅下架 ───
# 注意：原 DELETE /api/admin/coupons/{id} 接口已**移除**。
# 改用 POST /api/admin/coupons/{id}/offline + POST /api/admin/coupons/{id}/online。


@router.get("/offline-reason-options")
async def get_offline_reason_options(_: User = Depends(admin_dep)):
    """V2.1：下架原因预设选项"""
    return {"options": OFFLINE_REASON_PRESETS}


@router.post("/{coupon_id}/offline")
async def offline_coupon(
    coupon_id: int,
    data: CouponOfflineRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：下架优惠券（仅超级管理员）。

    强校验：
    - 仅 is_superuser=True 可操作
    - 该券不能是当前 NEW_USER_COUPON_KEY 引用的券
    - reason_type 必须为预设之一；'其他' 必填 reason_detail（最少 5 字）
    """
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行下架操作")

    if data.reason_type not in OFFLINE_REASON_PRESETS:
        raise HTTPException(status_code=400, detail=f"下架原因必须为 {OFFLINE_REASON_PRESETS} 之一")

    if data.reason_type == "其他":
        detail = (data.reason_detail or "").strip()
        if len(detail) < 5:
            raise HTTPException(status_code=422, detail='选择"其他"时，原因备注最少 5 字')

    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    # 新人券强校验
    if await _is_new_user_coupon(db, coupon_id):
        raise HTTPException(status_code=422, detail="该券是当前新人券，请先在新人券配置页切换到另一张券再下架")

    if c.is_offline:
        return {"message": "该券已经处于下架状态", "id": c.id, "is_offline": True}

    full_reason = data.reason_type
    if data.reason_type == "其他" and data.reason_detail:
        full_reason = f"其他：{data.reason_detail.strip()}"

    c.is_offline = True
    c.offline_reason = full_reason
    c.offline_at = datetime.utcnow()
    c.offline_by = current_user.id

    await _add_op_log(db, "offline", "coupon", c.id, current_user, reason=full_reason)
    return {"message": "下架成功", "id": c.id, "is_offline": True, "offline_reason": full_reason}


@router.post("/{coupon_id}/online")
async def online_coupon(
    coupon_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：重新上架优惠券（仅超级管理员）"""
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行上架操作")

    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    if not c.is_offline:
        return {"message": "该券已是上架状态", "id": c.id, "is_offline": False}

    c.is_offline = False
    c.offline_reason = None
    c.offline_at = None
    c.offline_by = None

    await _add_op_log(db, "online", "coupon", c.id, current_user, reason="重新上架")
    return {"message": "上架成功", "id": c.id, "is_offline": False}


# ─── 发放记录 ───


@router.get("/{coupon_id}/grants")
async def list_coupon_grants(
    coupon_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    phone: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """4 维筛选：手机号 / 状态 / 时间 / 方式"""
    query = select(CouponGrant).where(CouponGrant.coupon_id == coupon_id)
    count_query = select(func.count(CouponGrant.id)).where(CouponGrant.coupon_id == coupon_id)
    conds = []
    if phone:
        conds.append(CouponGrant.user_phone.like(f"%{phone}%"))
    if status:
        conds.append(CouponGrant.status == status)
    if method:
        conds.append(CouponGrant.method == method)
    if start:
        conds.append(CouponGrant.granted_at >= start)
    if end:
        conds.append(CouponGrant.granted_at <= end)
    if conds:
        query = query.where(and_(*conds))
        count_query = count_query.where(and_(*conds))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(CouponGrant.granted_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for g in result.scalars().all():
        items.append({
            "id": g.id,
            "coupon_id": g.coupon_id,
            "user_id": g.user_id,
            "user_phone": g.user_phone,
            "method": g.method,
            "status": g.status,
            "granted_at": g.granted_at.isoformat() if g.granted_at else None,
            "used_at": g.used_at.isoformat() if g.used_at else None,
            "order_no": g.order_no,
            "operator_name": g.operator_name,
            "redeem_code": g.redeem_code,
            "recall_reason": g.recall_reason,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{coupon_id}/grants/export")
async def export_coupon_grants(
    coupon_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """导出发放记录为 CSV（Excel 兼容）"""
    result = await db.execute(
        select(CouponGrant).where(CouponGrant.coupon_id == coupon_id)
        .order_by(CouponGrant.granted_at.desc()).limit(10000)
    )
    grants = result.scalars().all()

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(buf)
    writer.writerow(["发放ID", "用户ID", "手机号", "发放时间", "发放方式", "状态",
                     "使用时间", "订单号", "操作人", "兑换码", "回收原因"])
    for g in grants:
        writer.writerow([
            g.id, g.user_id or "", g.user_phone or "",
            g.granted_at.strftime("%Y-%m-%d %H:%M:%S") if g.granted_at else "",
            g.method, g.status,
            g.used_at.strftime("%Y-%m-%d %H:%M:%S") if g.used_at else "",
            g.order_no or "", g.operator_name or "",
            g.redeem_code or "", g.recall_reason or "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=coupon_grants_{coupon_id}.csv"}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@router.post("/grants/recall")
async def recall_grants(
    data: GrantRecallRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """单/批量回收（必填原因）"""
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="回收原因必填")
    result = await db.execute(select(CouponGrant).where(CouponGrant.id.in_(data.grant_ids)))
    grants = result.scalars().all()
    if not grants:
        raise HTTPException(status_code=404, detail="未找到对应发放记录")

    recalled = 0
    for g in grants:
        if g.status in ("used", "recalled"):
            continue
        g.status = "recalled"
        g.recall_reason = data.reason
        # 同步将 user_coupon 标为过期
        if g.user_coupon_id:
            uc = (await db.execute(select(UserCoupon).where(UserCoupon.id == g.user_coupon_id))).scalar_one_or_none()
            if uc and uc.status == UserCouponStatus.unused:
                uc.status = UserCouponStatus.expired
        recalled += 1
    return {"message": f"成功回收 {recalled} 条", "recalled": recalled}


# ─── 4 种发放方式 ───


@router.post("/{coupon_id}/grant/direct")
async def grant_direct(
    coupon_id: int,
    data: DirectGrantRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """B 定向发放：根据 user_ids / phones / 标签筛选"""
    coupon = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    # 收集目标用户
    users: list[User] = []
    if data.user_ids:
        rs = await db.execute(select(User).where(User.id.in_(data.user_ids)))
        users.extend(rs.scalars().all())
    if data.phones:
        rs = await db.execute(select(User).where(User.phone.in_(data.phones)))
        users.extend(rs.scalars().all())
    if data.filter_tags:
        # 标签维度：用户等级 + 注册时长 + 消费行为
        tag_query = select(User)
        conds = []
        lvl = data.filter_tags.get("member_level")
        if lvl is not None:
            conds.append(User.member_level == int(lvl))
        reg_days = data.filter_tags.get("registered_within_days")
        if reg_days:
            since = datetime.utcnow() - timedelta(days=int(reg_days))
            conds.append(User.created_at >= since)
        if conds:
            tag_query = tag_query.where(and_(*conds))
            rs = await db.execute(tag_query.limit(5000))
            users.extend(rs.scalars().all())

    if not users:
        raise HTTPException(status_code=400, detail="没有匹配到任何用户")

    # 去重
    seen = set()
    uniq_users: list[User] = []
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        uniq_users.append(u)

    granted = 0
    skipped = 0
    now = datetime.utcnow()
    for u in uniq_users:
        # 限领规则：每人每券 1 张
        existing = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == u.id, UserCoupon.coupon_id == coupon_id
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        uc = UserCoupon(
            user_id=u.id, coupon_id=coupon_id,
            expire_at=_calc_expire_at(coupon, now),
            source="direct",
        )
        db.add(uc)
        await db.flush()
        coupon.claimed_count += 1
        db.add(CouponGrant(
            coupon_id=coupon_id, user_id=u.id, user_phone=u.phone,
            method="direct", status="granted", granted_at=now,
            user_coupon_id=uc.id,
            operator_id=current_user.id, operator_name=current_user.nickname or current_user.phone,
        ))
        granted += 1

    return {"message": f"成功发放 {granted} 张，跳过 {skipped} 个已领用户", "granted": granted, "skipped": skipped}


# ─── D 新人券规则 ───


NEW_USER_COUPON_KEY = "new_user_coupon_ids"


@new_user_router.get("")
async def get_new_user_coupons(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.config_key == NEW_USER_COUPON_KEY))).scalar_one_or_none()
    ids: list[int] = []
    if cfg and cfg.config_value:
        try:
            import json as _json
            ids = _json.loads(cfg.config_value)
        except Exception:
            ids = []
    coupons = []
    if ids:
        rs = await db.execute(select(Coupon).where(Coupon.id.in_(ids)))
        coupons = [_coupon_to_dict(c) for c in rs.scalars().all()]
    return {"coupon_ids": ids, "coupons": coupons}


class NewUserCouponSet(BaseModel):
    coupon_ids: list[int]


@new_user_router.put("")
async def set_new_user_coupons(
    data: NewUserCouponSet,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    import json as _json
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.config_key == NEW_USER_COUPON_KEY))).scalar_one_or_none()
    val = _json.dumps(data.coupon_ids)
    if cfg:
        cfg.config_value = val
    else:
        db.add(SystemConfig(config_key=NEW_USER_COUPON_KEY, config_value=val, config_type="coupon"))
    return {"coupon_ids": data.coupon_ids}


# ─── F 兑换码批次 ───


def _gen_unique_code(length: int = 16) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # 排除易混淆字符 0/O/1/I
    alphabet = alphabet.translate(str.maketrans("", "", "0O1I"))
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _gen_batch_no(batch_id: int, when: Optional[datetime] = None) -> str:
    when = when or datetime.utcnow()
    return f"BATCH-{when.strftime('%Y%m%d')}-{batch_id:04d}"


@router.post("/redeem-code-batches")
async def create_redeem_batch(
    data: RedeemCodeBatchCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    coupon = (await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))).scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    if data.code_type not in ("universal", "unique"):
        raise HTTPException(status_code=400, detail="code_type 仅支持 universal / unique")

    universal_code = data.universal_code
    claim_limit = data.claim_limit
    if data.code_type == "universal":
        if not universal_code:
            universal_code = _gen_unique_code(12)
        # V2.1：一码通用必填 claim_limit
        if not claim_limit or claim_limit <= 0:
            raise HTTPException(status_code=400, detail='一码通用类型必须填写"领取上限 claim_limit"')
    else:
        if not data.total_count or data.total_count <= 0:
            raise HTTPException(status_code=400, detail="一次性唯一码必须指定 total_count")
        if data.total_count > 100000:
            raise HTTPException(status_code=400, detail="单批最多 100000 个")
        # 一次性唯一码 claim_limit 自动 = total_count
        claim_limit = data.total_count

    batch = CouponCodeBatch(
        coupon_id=data.coupon_id,
        code_type=data.code_type,
        name=data.name,
        total_count=data.total_count or 0,
        universal_code=universal_code if data.code_type == "universal" else None,
        per_user_limit=data.per_user_limit if data.code_type == "universal" else 1,
        partner_id=data.partner_id,
        status="active",
        created_by=current_user.id,
        claim_limit=claim_limit,
        expire_at=data.expire_at,
    )
    db.add(batch)
    await db.flush()
    # 回写 batch_no（依赖自增 id）
    batch.batch_no = _gen_batch_no(batch.id, batch.created_at)

    # unique 模式批量生成
    if data.code_type == "unique":
        existing_codes: set[str] = set()
        codes_to_add = []
        target = data.total_count
        while len(codes_to_add) < target:
            c = _gen_unique_code(16)
            if c in existing_codes:
                continue
            existing_codes.add(c)
            codes_to_add.append(c)
        # 检查数据库已存在的码
        rs = await db.execute(select(CouponRedeemCode.code).where(CouponRedeemCode.code.in_(list(existing_codes))))
        dup_in_db = {r[0] for r in rs.all()}
        codes_to_add = [c for c in codes_to_add if c not in dup_in_db]
        for c in codes_to_add:
            db.add(CouponRedeemCode(
                batch_id=batch.id, coupon_id=data.coupon_id,
                code=c, status="available",
                partner_id=data.partner_id,
            ))
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "code_type": batch.code_type,
        "universal_code": batch.universal_code,
        "total_count": batch.total_count,
        "claim_limit": batch.claim_limit,
        "partner_id": batch.partner_id,
    }


def _batch_to_dict(b: CouponCodeBatch, coupon_name: Optional[str] = None,
                   used: int = 0, available: int = 0, voided: int = 0) -> dict:
    return {
        "id": b.id,
        "batch_no": b.batch_no or _gen_batch_no(b.id, b.created_at or datetime.utcnow()),
        "coupon_id": b.coupon_id,
        "coupon_name": coupon_name,
        "code_type": b.code_type,
        "name": b.name,
        "total_count": b.total_count or 0,
        "used_count": b.used_count or 0,
        "available_count": available,
        "voided_count": voided,
        "used_codes_count": used,
        "universal_code": b.universal_code,
        "claim_limit": b.claim_limit,
        "per_user_limit": b.per_user_limit,
        "partner_id": b.partner_id,
        "status": b.status,
        "expire_at": b.expire_at.isoformat() if b.expire_at else None,
        "voided_at": b.voided_at.isoformat() if b.voided_at else None,
        "voided_by": b.voided_by,
        "void_reason": b.void_reason,
        "created_by": b.created_by,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/redeem-code-batches")
async def list_redeem_batches(
    coupon_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：批次列表（含批次编号、关联券名、码类型、生成时间、生成人、总数、已用、未用、已作废、有效期）。"""
    query = select(CouponCodeBatch)
    count_query = select(func.count(CouponCodeBatch.id))
    if coupon_id:
        query = query.where(CouponCodeBatch.coupon_id == coupon_id)
        count_query = count_query.where(CouponCodeBatch.coupon_id == coupon_id)
    total = (await db.execute(count_query)).scalar() or 0
    rs = await db.execute(
        query.order_by(CouponCodeBatch.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    batches = rs.scalars().all()

    # 预加载所有相关 coupon name + 各批次统计
    items = []
    coupon_ids = list({b.coupon_id for b in batches})
    coupon_map = {}
    if coupon_ids:
        rs2 = await db.execute(select(Coupon).where(Coupon.id.in_(coupon_ids)))
        coupon_map = {c.id: c.name for c in rs2.scalars().all()}

    for b in batches:
        # 一次性唯一码：聚合统计
        used_codes = 0
        avail_codes = 0
        voided_codes = 0
        if b.code_type == "unique":
            agg = await db.execute(
                select(CouponRedeemCode.status, func.count(CouponRedeemCode.id))
                .where(CouponRedeemCode.batch_id == b.id)
                .group_by(CouponRedeemCode.status)
            )
            for s, cnt in agg.all():
                if s == "used":
                    used_codes = cnt
                elif s == "available":
                    avail_codes = cnt
                elif s == "disabled":
                    voided_codes = cnt
            # 也统计 voided_at 非空但 status 仍是 available 的（兼容）
            v2 = await db.execute(
                select(func.count(CouponRedeemCode.id)).where(
                    CouponRedeemCode.batch_id == b.id,
                    CouponRedeemCode.voided_at.isnot(None),
                )
            )
            voided_v = v2.scalar() or 0
            if voided_v > voided_codes:
                voided_codes = voided_v
        else:
            # 一码通用：用 used_count + claim_limit 统计
            used_codes = b.used_count or 0
            avail_codes = max(0, (b.claim_limit or 0) - used_codes)
            voided_codes = 1 if b.voided_at else 0

        items.append(_batch_to_dict(
            b, coupon_name=coupon_map.get(b.coupon_id),
            used=used_codes, available=avail_codes, voided=voided_codes,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ─── V2.1 兑换码批次明细 ───


@router.get("/redeem-code-batches/{batch_id}/codes")
async def list_batch_codes(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    reveal: bool = False,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：批次明细。

    - 一码通用：返回 1 行码 + 已用 / 上限 + 兑换记录列表
    - 一次性唯一码：返回 N 行码（默认脱敏，reveal=true 解码）
    """
    batch = (await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.id == batch_id))).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    if batch.code_type == "universal":
        # 一码通用：1 行 + 兑换记录
        total_used = (await db.execute(
            select(func.count(CouponGrant.id)).where(
                CouponGrant.batch_id == batch.id,
                CouponGrant.method == "redeem_code",
            )
        )).scalar() or 0
        # 兑换记录列表
        rs = await db.execute(
            select(CouponGrant).where(
                CouponGrant.batch_id == batch.id,
                CouponGrant.method == "redeem_code",
            ).order_by(CouponGrant.granted_at.desc()).limit(200)
        )
        records = []
        for g in rs.scalars().all():
            records.append({
                "user_id": g.user_id,
                "user_phone": g.user_phone,
                "redeemed_at": g.granted_at.isoformat() if g.granted_at else None,
                "status": g.status,
            })
        the_code = batch.universal_code or ""
        return {
            "code_type": "universal",
            "claim_limit": batch.claim_limit or 0,
            "used": total_used,
            "voided_at": batch.voided_at.isoformat() if batch.voided_at else None,
            "code": the_code if reveal else _mask_code(the_code),
            "items": [{
                "id": batch.id,
                "code": the_code if reveal else _mask_code(the_code),
                "code_full": the_code if reveal else None,
                "status": "voided" if batch.voided_at else "active",
                "voided_at": batch.voided_at.isoformat() if batch.voided_at else None,
                "void_reason": batch.void_reason,
            }],
            "records": records,
            "total": 1,
        }

    # unique
    total = (await db.execute(
        select(func.count(CouponRedeemCode.id)).where(CouponRedeemCode.batch_id == batch_id)
    )).scalar() or 0
    rs = await db.execute(
        select(CouponRedeemCode).where(CouponRedeemCode.batch_id == batch_id)
        .order_by(CouponRedeemCode.id.asc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    codes = rs.scalars().all()
    items = []
    user_phones: dict[int, str] = {}
    user_ids = [c.used_by_user_id for c in codes if c.used_by_user_id]
    if user_ids:
        rs2 = await db.execute(select(User.id, User.phone).where(User.id.in_(user_ids)))
        user_phones = {row[0]: row[1] for row in rs2.all()}
    for c in codes:
        is_voided = bool(c.voided_at)
        items.append({
            "id": c.id,
            "code": c.code if reveal else _mask_code(c.code),
            "code_full": c.code if reveal else None,
            "status": "voided" if is_voided else c.status,
            "sold_at": c.sold_at.isoformat() if c.sold_at else None,
            "used_at": c.used_at.isoformat() if c.used_at else None,
            "used_by_user_id": c.used_by_user_id,
            "used_by_user_phone": user_phones.get(c.used_by_user_id) if c.used_by_user_id else None,
            "voided_at": c.voided_at.isoformat() if c.voided_at else None,
            "void_reason": c.void_reason,
        })
    return {
        "code_type": "unique",
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/redeem-code-batches/{batch_id}/void")
async def void_redeem_batch(
    batch_id: int,
    data: CodeBatchVoidRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：作废整批（强二次确认 + 必填原因）。

    校验：batch_no_confirm 必须与 batch.batch_no 完全一致
    作废只阻止"未来兑换"，已领的券正常保留可用
    """
    batch = (await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.id == batch_id))).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    bn = batch.batch_no or _gen_batch_no(batch.id, batch.created_at or datetime.utcnow())
    if data.batch_no_confirm.strip() != bn:
        raise HTTPException(status_code=400, detail=f"批次编号不匹配（应为 {bn}）")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="作废原因必填")

    if batch.voided_at:
        return {"ok": True, "voided_count": 0, "message": "该批次已作废"}

    now = datetime.utcnow()
    batch.voided_at = now
    batch.voided_by = current_user.id
    batch.void_reason = data.reason
    batch.status = "disabled"

    # 同步把所有 available 的码作废
    voided_count = 0
    if batch.code_type == "unique":
        rs = await db.execute(
            select(CouponRedeemCode).where(
                CouponRedeemCode.batch_id == batch_id,
                CouponRedeemCode.status.in_(("available", "sold")),
            )
        )
        for c in rs.scalars().all():
            c.voided_at = now
            c.voided_by = current_user.id
            c.void_reason = data.reason
            c.status = "disabled"
            voided_count += 1
    else:
        voided_count = 1

    await _add_op_log(db, "void_batch", "batch", batch.id, current_user, reason=data.reason,
                       extra={"batch_no": bn, "voided_codes": voided_count})
    return {"ok": True, "voided_count": voided_count, "batch_no": bn}


@router.post("/codes/{code_id}/void")
async def void_single_code(
    code_id: int,
    data: CodeVoidRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """V2.1：作废单个码（必填原因 + 操作日志）。"""
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="作废原因必填")
    rc = (await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.id == code_id))).scalar_one_or_none()
    if not rc:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if rc.voided_at:
        return {"ok": True, "message": "该码已作废"}
    if rc.status == "used":
        raise HTTPException(status_code=400, detail="已使用的码不能作废")

    rc.voided_at = datetime.utcnow()
    rc.voided_by = current_user.id
    rc.void_reason = data.reason
    rc.status = "disabled"

    await _add_op_log(db, "void_code", "code", rc.id, current_user, reason=data.reason)
    return {"ok": True}


@router.get("/redeem-code-batches/{batch_id}/codes/export")
async def export_batch_codes(
    batch_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """导出批次内所有码为 CSV"""
    rs = await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.batch_id == batch_id).limit(200000))
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["code", "status", "sold_at", "used_at"])
    for c in rs.scalars().all():
        writer.writerow([
            c.code, c.status,
            c.sold_at.strftime("%Y-%m-%d %H:%M:%S") if c.sold_at else "",
            c.used_at.strftime("%Y-%m-%d %H:%M:%S") if c.used_at else "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=batch_{batch_id}_codes.csv"}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


# ─── 第三方合作方管理 ───


def _gen_api_key() -> str:
    return "pk_" + secrets.token_urlsafe(24)


def _gen_api_secret() -> str:
    return secrets.token_urlsafe(32)


@partner_router.get("")
async def list_partners(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(Partner).order_by(Partner.created_at.desc()).limit(500))
    items = [PartnerResponse.model_validate(p).model_dump() for p in rs.scalars().all()]
    return {"items": items}


@partner_router.post("")
async def create_partner(
    data: PartnerCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = Partner(
        name=data.name, contact_name=data.contact_name, contact_phone=data.contact_phone,
        mode=data.mode, notes=data.notes, status="active",
        api_key=_gen_api_key(), api_secret=_gen_api_secret(),
    )
    db.add(p)
    await db.flush()
    return PartnerResponse.model_validate(p).model_dump()


@partner_router.put("/{partner_id}")
async def update_partner(
    partner_id: int,
    data: PartnerUpdate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    for f in ("name", "contact_name", "contact_phone", "mode", "status", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(p, f, v)
    return PartnerResponse.model_validate(p).model_dump()


@partner_router.post("/{partner_id}/regenerate-key")
async def regenerate_partner_key(
    partner_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    p.api_key = _gen_api_key()
    p.api_secret = _gen_api_secret()
    return {"api_key": p.api_key, "api_secret": p.api_secret}


@partner_router.delete("/{partner_id}")
async def delete_partner(
    partner_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    await db.delete(p)
    return {"message": "删除成功"}


@partner_router.get("/{partner_id}/reconciliation")
async def partner_reconciliation(
    partner_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """合作方对账数据：批次发放/售出/核销统计"""
    batches = (await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.partner_id == partner_id))).scalars().all()
    batch_ids = [b.id for b in batches]
    total_codes = 0
    sold = 0
    used = 0
    if batch_ids:
        total_codes = (await db.execute(select(func.count(CouponRedeemCode.id)).where(CouponRedeemCode.batch_id.in_(batch_ids)))).scalar() or 0
        sold = (await db.execute(select(func.count(CouponRedeemCode.id)).where(
            CouponRedeemCode.batch_id.in_(batch_ids), CouponRedeemCode.status.in_(("sold", "used"))
        ))).scalar() or 0
        used = (await db.execute(select(func.count(CouponRedeemCode.id)).where(
            CouponRedeemCode.batch_id.in_(batch_ids), CouponRedeemCode.status == "used"
        ))).scalar() or 0
    return {
        "partner_id": partner_id,
        "batches": len(batches),
        "total_codes": total_codes,
        "sold": sold,
        "used": used,
        "unsold": total_codes - sold,
    }
