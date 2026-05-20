"""[PRD-TAG-RECOMMEND-V1 2026-05-20]
标签管理 + 问卷推荐配置 API

包含：
- 管理端标签 CRUD / 合并 / 查关联商品
- 管理端商品-标签关联读写
- 管理端问卷推荐配置 CRUD / 预览
- 用户端 /api/questionnaire/submit 内部使用的推荐计算工具
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    FulfillmentType,
    GoodsTag,
    Product,
    ProductStatus,
    QuestionnaireClassificationRule,
    QuestionnaireRecommendConfig,
    QuestionnaireTemplate,
    Tag,
)
from app.schemas.tag_recommend import (
    GoodsTagsUpdate,
    RecommendConfigBulkUpdate,
    RecommendConfigResponse,
    RecommendGoodsItem,
    RecommendPreviewRequest,
    RecommendPreviewResponse,
    TagCreate,
    TagMergeRequest,
    TagResponse,
    TagUpdate,
    TAG_CATEGORIES,
)

router = APIRouter(
    prefix="/api/admin/tags", tags=["标签管理-管理后台"]
)
goods_tags_router = APIRouter(
    prefix="/api/admin/goods", tags=["商品标签-管理后台"]
)
recommend_router = APIRouter(
    prefix="/api/admin/questionnaire", tags=["问卷推荐-管理后台"]
)
admin_dep = require_role("admin")


# 履约方式正名（PRD 模块 4）
FULFILLMENT_LABEL_MAP = {
    "in_store": "到店服务",
    "delivery": "实物配送",
    "on_site": "上门服务",
    "virtual": "权益服务",
}


# ════════════════════════════════════════
# 标签 CRUD
# ════════════════════════════════════════


@router.get("")
async def list_tags(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Tag)
    count_stmt = select(func.count(Tag.id))
    conds = []
    if category:
        conds.append(Tag.category == category)
    if keyword:
        conds.append(Tag.name.like(f"%{keyword}%"))
    if status is not None:
        conds.append(Tag.status == status)
    if conds:
        cond = and_(*conds)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(
            stmt.order_by(Tag.category.asc(), Tag.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    # 同步 goods_count
    tag_ids = [t.id for t in rows]
    counts: dict[int, int] = {}
    if tag_ids:
        gc_rows = (
            await db.execute(
                select(GoodsTag.tag_id, func.count(GoodsTag.goods_id))
                .where(GoodsTag.tag_id.in_(tag_ids))
                .group_by(GoodsTag.tag_id)
            )
        ).all()
        counts = {tid: int(c) for tid, c in gc_rows}
    items = []
    for t in rows:
        c = counts.get(t.id, 0)
        if t.goods_count != c:
            t.goods_count = c
        items.append(TagResponse.model_validate(t))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=TagResponse)
async def create_tag(
    payload: TagCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if payload.category not in TAG_CATEGORIES:
        raise HTTPException(400, f"无效分类，必须是 {TAG_CATEGORIES} 之一")
    # 重名检查
    exists = (
        await db.execute(
            select(Tag).where(Tag.category == payload.category, Tag.name == payload.name)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "同分类下标签名重复")
    t = Tag(**payload.model_dump(exclude_unset=True))
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return TagResponse.model_validate(t)


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: int,
    payload: TagUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Tag, tag_id)
    if not t:
        raise HTTPException(404, "标签不存在")
    data = payload.model_dump(exclude_unset=True)
    if "category" in data and data["category"] not in TAG_CATEGORIES:
        raise HTTPException(400, f"无效分类，必须是 {TAG_CATEGORIES} 之一")
    # 重名检查
    new_name = data.get("name", t.name)
    new_cat = data.get("category", t.category)
    if new_name != t.name or new_cat != t.category:
        dup = (
            await db.execute(
                select(Tag).where(
                    Tag.category == new_cat,
                    Tag.name == new_name,
                    Tag.id != tag_id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(400, "同分类下标签名重复")
    for k, v in data.items():
        setattr(t, k, v)
    await db.flush()
    await db.refresh(t)
    return TagResponse.model_validate(t)


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Tag, tag_id)
    if not t:
        raise HTTPException(404, "标签不存在")
    # 同时删除关联记录
    await db.execute(delete(GoodsTag).where(GoodsTag.tag_id == tag_id))
    await db.delete(t)
    return {"ok": True}


@router.post("/{tag_id}/merge")
async def merge_tag(
    tag_id: int,
    payload: TagMergeRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """将 tag_id 合并到 target_id：所有商品关联从 tag_id 改为 target_id"""
    if tag_id == payload.target_id:
        raise HTTPException(400, "不能合并到自己")
    src = await db.get(Tag, tag_id)
    tgt = await db.get(Tag, payload.target_id)
    if not src or not tgt:
        raise HTTPException(404, "源或目标标签不存在")
    # 找出 src 下所有商品
    src_goods = (
        await db.execute(select(GoodsTag.goods_id).where(GoodsTag.tag_id == tag_id))
    ).scalars().all()
    # 找出已关联 target 的商品避免冲突
    tgt_goods = set(
        (
            await db.execute(
                select(GoodsTag.goods_id).where(GoodsTag.tag_id == payload.target_id)
            )
        ).scalars().all()
    )
    moved = 0
    for gid in src_goods:
        if gid in tgt_goods:
            continue
        db.add(GoodsTag(goods_id=gid, tag_id=payload.target_id))
        moved += 1
    # 删除源标签所有关联
    await db.execute(delete(GoodsTag).where(GoodsTag.tag_id == tag_id))
    await db.delete(src)
    await db.flush()
    return {"ok": True, "merged_goods": moved}


@router.get("/{tag_id}/goods")
async def list_tag_goods(
    tag_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Tag, tag_id)
    if not t:
        raise HTTPException(404, "标签不存在")
    sub = select(GoodsTag.goods_id).where(GoodsTag.tag_id == tag_id)
    total = (
        await db.execute(select(func.count()).select_from(sub.subquery()))
    ).scalar() or 0
    gid_rows = (
        await db.execute(
            sub.offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    items: list[dict[str, Any]] = []
    if gid_rows:
        prods = (
            await db.execute(select(Product).where(Product.id.in_(gid_rows)))
        ).scalars().all()
        for p in prods:
            items.append({"id": p.id, "name": p.name, "sale_price": float(p.sale_price or 0)})
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ════════════════════════════════════════
# 商品-标签关联
# ════════════════════════════════════════


@goods_tags_router.get("/{goods_id}/tags")
async def get_goods_tags(
    goods_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(GoodsTag.tag_id).where(GoodsTag.goods_id == goods_id))
    ).scalars().all()
    tags: list[TagResponse] = []
    if rows:
        ts = (
            await db.execute(select(Tag).where(Tag.id.in_(rows)))
        ).scalars().all()
        tags = [TagResponse.model_validate(t) for t in ts]
    return {"tag_ids": list(rows), "tags": tags}


@goods_tags_router.put("/{goods_id}/tags")
async def update_goods_tags(
    goods_id: int,
    payload: GoodsTagsUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 校验商品存在
    p = await db.get(Product, goods_id)
    if not p:
        raise HTTPException(404, "商品不存在")
    # 清除并重新插入
    await db.execute(delete(GoodsTag).where(GoodsTag.goods_id == goods_id))
    seen: set[int] = set()
    for tid in payload.tag_ids:
        if tid in seen:
            continue
        seen.add(tid)
        db.add(GoodsTag(goods_id=goods_id, tag_id=tid))
    await db.flush()
    return {"ok": True, "tag_ids": list(seen)}


# ════════════════════════════════════════
# 问卷推荐配置
# ════════════════════════════════════════


@recommend_router.get("/templates/{template_id}/recommend")
async def get_recommend_config(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "问卷模板不存在")
    rows = (
        await db.execute(
            select(QuestionnaireRecommendConfig)
            .where(QuestionnaireRecommendConfig.template_id == template_id)
        )
    ).scalars().all()
    # 分型列表
    cls_rows = (
        await db.execute(
            select(QuestionnaireClassificationRule)
            .where(QuestionnaireClassificationRule.template_id == template_id)
            .order_by(QuestionnaireClassificationRule.sort_order.asc())
        )
    ).scalars().all()
    return {
        "template": {
            "id": tpl.id,
            "code": tpl.code,
            "name": tpl.name,
            "result_display_mode": tpl.result_display_mode or "simple",
            "ai_followup_enabled": bool(tpl.ai_followup_enabled) if tpl.ai_followup_enabled is not None else True,
            "recommend_click_mode": tpl.recommend_click_mode or "drawer",
            "recommend_display_count": tpl.recommend_display_count or 6,
        },
        "classifications": [
            {"code": c.code, "name": c.name, "description": c.description}
            for c in cls_rows
        ],
        "configs": [
            RecommendConfigResponse.model_validate(r) for r in rows
        ],
    }


@recommend_router.put("/templates/{template_id}/recommend")
async def update_recommend_config(
    template_id: int,
    payload: RecommendConfigBulkUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "问卷模板不存在")
    # 全量覆盖：先删除原有，再插入新的
    await db.execute(
        delete(QuestionnaireRecommendConfig).where(
            QuestionnaireRecommendConfig.template_id == template_id
        )
    )
    for it in payload.items:
        if it.mode not in (1, 2, 3):
            raise HTTPException(400, f"无效 mode={it.mode}")
        cfg = QuestionnaireRecommendConfig(
            template_id=template_id,
            result_key=it.result_key,
            mode=it.mode,
            filter_json=it.filter_json,
            manual_goods_ids=it.manual_goods_ids,
        )
        db.add(cfg)
    await db.flush()
    return {"ok": True, "count": len(payload.items)}


async def _compute_recommend_goods(
    db: AsyncSession,
    mode: int,
    filter_json: Optional[dict[str, Any]],
    manual_goods_ids: Optional[list[int]],
    limit: int = 6,
) -> list[RecommendGoodsItem]:
    """核心推荐计算：返回去重 + 排序后的商品列表"""
    goods_hit: dict[int, int] = {}  # goods_id -> 命中标签数
    candidate_ids: set[int] = set()

    if mode == 3:
        # 手动挑商品：按用户配置顺序保留
        ids = manual_goods_ids or []
        for gid in ids:
            candidate_ids.add(gid)
            goods_hit[gid] = 1
    else:
        # 模式 1/2：标签智能匹配 / 标签固定推荐
        fj = filter_json or {}
        cat_ids = fj.get("category_ids") or []
        ff_types = fj.get("fulfillment_types") or []
        tag_ids = fj.get("tag_ids") or []
        # 通过标签找商品 + 命中数
        if tag_ids:
            rows = (
                await db.execute(
                    select(GoodsTag.goods_id, func.count(GoodsTag.tag_id))
                    .where(GoodsTag.tag_id.in_(tag_ids))
                    .group_by(GoodsTag.goods_id)
                )
            ).all()
            for gid, c in rows:
                goods_hit[gid] = int(c)
                candidate_ids.add(gid)
        # 如果未指定标签但指定了类目/履约，则候选取所有上架商品
        if not tag_ids and (cat_ids or ff_types):
            q = select(Product.id).where(Product.status == ProductStatus.active)
            if cat_ids:
                q = q.where(Product.category_id.in_(cat_ids))
            if ff_types:
                # 履约：直接按字符串匹配 enum value
                q = q.where(Product.fulfillment_type.in_(ff_types))
            rows2 = (await db.execute(q)).scalars().all()
            for gid in rows2:
                candidate_ids.add(gid)
                goods_hit.setdefault(gid, 0)

    if not candidate_ids:
        return []

    # 加载商品详情
    prods = (
        await db.execute(
            select(Product).where(
                Product.id.in_(candidate_ids),
                Product.status == ProductStatus.active,
            )
        )
    ).scalars().all()

    # 进一步按 filter_json 中的 category/fulfillment 过滤（模式 1）
    if mode in (1, 2):
        fj = filter_json or {}
        cat_ids = set(fj.get("category_ids") or [])
        ff_types = set(fj.get("fulfillment_types") or [])
        if cat_ids:
            prods = [p for p in prods if p.category_id in cat_ids]
        if ff_types:
            prods = [p for p in prods if (p.fulfillment_type.value if hasattr(p.fulfillment_type, "value") else str(p.fulfillment_type)) in ff_types]

    # 排序：命中标签数多 > 销量高 > 上架时间新
    def sort_key(p: Product):
        return (
            -goods_hit.get(p.id, 0),
            -(p.sales_count or 0),
            -int((p.created_at or datetime.min).timestamp()),
        )

    prods.sort(key=sort_key)

    # 去重（按 id 自然去重，set 已保证）+ 限量
    items: list[RecommendGoodsItem] = []
    seen: set[int] = set()
    for p in prods[: max(limit, 1) * 3]:
        if p.id in seen:
            continue
        seen.add(p.id)
        first_image: Optional[str] = None
        try:
            imgs = p.images
            if isinstance(imgs, list) and imgs:
                first_image = str(imgs[0])
        except Exception:
            pass
        ff = p.fulfillment_type.value if hasattr(p.fulfillment_type, "value") else str(p.fulfillment_type or "")
        items.append(
            RecommendGoodsItem(
                id=p.id,
                name=p.name,
                sale_price=float(p.sale_price or 0),
                original_price=float(p.original_price) if p.original_price else None,
                image=first_image,
                fulfillment_type=ff,
                fulfillment_label=FULFILLMENT_LABEL_MAP.get(ff, ff),
                sales_count=p.sales_count or 0,
                hit_tags=goods_hit.get(p.id, 0),
            )
        )
        if len(items) >= limit:
            break

    return items


@recommend_router.post("/templates/{template_id}/recommend/preview")
async def preview_recommend(
    template_id: int,
    payload: RecommendPreviewRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "问卷模板不存在")
    limit = payload.limit or tpl.recommend_display_count or 6
    if limit < 1:
        limit = 6
    if limit > 20:
        limit = 20
    items = await _compute_recommend_goods(
        db,
        mode=payload.mode,
        filter_json=payload.filter_json,
        manual_goods_ids=payload.manual_goods_ids,
        limit=limit,
    )
    return RecommendPreviewResponse(items=items, total=len(items))


# ════════════════════════════════════════
# 给问卷 submit 使用的公开推荐计算工具
# ════════════════════════════════════════


async def compute_recommend_for_submit(
    db: AsyncSession,
    template_id: int,
    classification_code: Optional[str],
) -> tuple[list[dict[str, Any]], str, int]:
    """供 /api/questionnaire/submit 调用：返回 (商品卡列表, click_mode, display_count)"""
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        return [], "drawer", 6
    click_mode = tpl.recommend_click_mode or "drawer"
    limit = tpl.recommend_display_count or 6

    if not classification_code:
        # 兜底：销量 Top
        prods = (
            await db.execute(
                select(Product)
                .where(Product.status == ProductStatus.active)
                .order_by(Product.sales_count.desc().nullslast())
                .limit(limit)
            )
        ).scalars().all()
        items: list[dict[str, Any]] = []
        for p in prods:
            first_image: Optional[str] = None
            try:
                if isinstance(p.images, list) and p.images:
                    first_image = str(p.images[0])
            except Exception:
                pass
            ff = p.fulfillment_type.value if hasattr(p.fulfillment_type, "value") else str(p.fulfillment_type or "")
            items.append({
                "id": p.id,
                "name": p.name,
                "sale_price": float(p.sale_price or 0),
                "original_price": float(p.original_price) if p.original_price else None,
                "image": first_image,
                "fulfillment_type": ff,
                "fulfillment_label": FULFILLMENT_LABEL_MAP.get(ff, ff),
                "sales_count": p.sales_count or 0,
            })
        return items, click_mode, limit

    cfg = (
        await db.execute(
            select(QuestionnaireRecommendConfig).where(
                QuestionnaireRecommendConfig.template_id == template_id,
                QuestionnaireRecommendConfig.result_key == classification_code,
            )
        )
    ).scalar_one_or_none()
    if not cfg:
        # 未配置该分型 -> 销量 Top
        return await compute_recommend_for_submit(db, template_id, None)

    cards = await _compute_recommend_goods(
        db,
        mode=cfg.mode,
        filter_json=cfg.filter_json,
        manual_goods_ids=cfg.manual_goods_ids,
        limit=limit,
    )
    return [c.model_dump() for c in cards], click_mode, limit
