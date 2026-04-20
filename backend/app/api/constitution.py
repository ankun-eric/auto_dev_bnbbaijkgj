"""体质测评优化一期 API。

接口职责（PRD v1.0 M2/M4/M5/M10 聚合）：
- GET /api/constitution/result/{diagnosis_id}
  结果页 6 屏所需全部数据一次性返回：
  1. 体质名片（名称/拟人形象/一句话/颜色/雷达图）
  2. 深度解读（特征/成因）
  3. 个性化养生方案（饮食宜忌/作息/运动/情志）
  4. 推荐膳食套餐（真实 SKU 优先，未命中退化为推荐模板）
  5. 广州门店服务（优惠券可领取状态 + 预约入口）
  6. 分享卡数据
- POST /api/constitution/coupon/claim
  领取"AI 精准检测体验券"（M5），每人限领 1 张，幂等
- GET /api/constitution/coupon/status
  查询当前用户该券领取与使用状态（用于结果页第五屏按钮文案切换）
- GET /api/constitution/archive
  我的体质档案列表（M10 最小版）
- GET /api/constitution/archive/{diagnosis_id}
  档案详情（复用结果页数据）

所有接口要求已登录。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ConstitutionAnswer,
    Coupon,
    CouponScope,
    CouponStatus,
    CouponType,
    FamilyMember,
    Product,
    ServiceItem,
    TCMDiagnosis,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.services.constitution_content import (
    DISCLAIMER,
    RADAR_DIMENSIONS,
    compute_radar_scores,
    get_content,
    get_package_mapping,
    get_persona,
    normalize_constitution_type,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/constitution", tags=["体质测评优化一期"])


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════

# AI 精准检测体验券的识别 name 关键词（优先匹配现有优惠券，未命中则动态兜底）
DETECTION_COUPON_KEYWORDS = ["AI 精准检测", "AI精准检测", "体质检测体验", "广州门店体验"]
DEFAULT_COUPON_NAME = "AI 精准检测体验券"
DEFAULT_COUPON_VALIDITY_DAYS = 30

# 广州门店专属标识（与门店登录系统对齐：这里暂以 city 字段为"广州"筛选）
GUANGZHOU_CITY_KEYWORDS = ["广州", "Guangzhou", "guangzhou"]


# ═══════════════════════════════════════════════════════════════════
# 工具方法
# ═══════════════════════════════════════════════════════════════════


async def _ensure_detection_coupon(db: AsyncSession) -> Optional[Coupon]:
    """确保"AI 精准检测体验券"存在。

    策略：
    1. 先按关键词查找已有 Coupon（不限管理员先配置的细节）
    2. 找不到则自动创建一张基础券：满 0 减 10（象征性表达"免费体验"）、
       有效期 30 天（`validity_days=30`）、无库存上限（total_count=0 = 不限）、
       scope=all（实际核销由门店系统负责）
    """
    q = select(Coupon).where(
        or_(*[Coupon.name.ilike(f"%{kw}%") for kw in DETECTION_COUPON_KEYWORDS])
    ).order_by(Coupon.id.asc())
    coupon = (await db.execute(q)).scalars().first()
    if coupon:
        return coupon

    # 自动创建兜底券：避免因为运营未配置导致结果页第五屏按钮不可用
    try:
        new_coupon = Coupon(
            name=DEFAULT_COUPON_NAME,
            type=CouponType.cash if hasattr(CouponType, "cash") else list(CouponType)[0],
            condition_amount=0,
            discount_value=10,
            discount_rate=1.0,
            scope=CouponScope.all,
            total_count=0,  # 0 表示无限量
            claimed_count=0,
            used_count=0,
            validity_days=DEFAULT_COUPON_VALIDITY_DAYS,
            status=CouponStatus.active,
            is_offline=False,
        )
        db.add(new_coupon)
        await db.flush()
        await db.refresh(new_coupon)
        return new_coupon
    except Exception as e:  # noqa: BLE001
        logger.warning("自动创建 AI 精准检测体验券失败：%s", e)
        return None


async def _load_diagnosis(db: AsyncSession, diagnosis_id: int, user_id: int) -> TCMDiagnosis:
    d = (await db.execute(
        select(TCMDiagnosis).where(TCMDiagnosis.id == diagnosis_id, TCMDiagnosis.user_id == user_id)
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="体质测评记录不存在")
    return d


async def _load_answers(db: AsyncSession, diagnosis_id: int) -> List[Dict[str, Any]]:
    rows = (await db.execute(
        select(ConstitutionAnswer).where(ConstitutionAnswer.diagnosis_id == diagnosis_id)
    )).scalars().all()
    return [{"question_id": r.question_id, "answer_value": r.answer_value} for r in rows]


async def _match_product_by_keywords(
    db: AsyncSession, keywords: List[str]
) -> Optional[Dict[str, Any]]:
    """根据套餐关键词优先匹配 Product 表，未命中再匹配 ServiceItem。"""
    if not keywords:
        return None

    # 1. Product
    try:
        product_q = select(Product).where(
            or_(*[Product.name.ilike(f"%{kw}%") for kw in keywords])
        ).order_by(Product.recommend_weight.desc(), Product.sales_count.desc()).limit(1)
        p = (await db.execute(product_q)).scalars().first()
        if p:
            img = None
            if isinstance(p.images, list) and p.images:
                img = p.images[0]
            elif isinstance(p.images, str):
                img = p.images
            return {
                "id": p.id,
                "kind": "product",
                "name": p.name,
                "price": float(p.sale_price) if p.sale_price is not None else 0.0,
                "original_price": float(p.original_price) if p.original_price is not None else None,
                "image": img,
                "description": (p.description or "")[:200],
            }
    except Exception as e:  # noqa: BLE001
        logger.warning("Product 匹配失败：%s", e)

    # 2. ServiceItem 兜底
    try:
        si_q = select(ServiceItem).where(
            or_(*[ServiceItem.name.ilike(f"%{kw}%") for kw in keywords])
        ).order_by(ServiceItem.sales_count.desc()).limit(1)
        s = (await db.execute(si_q)).scalars().first()
        if s:
            img = None
            if isinstance(s.images, list) and s.images:
                img = s.images[0]
            elif isinstance(s.images, str):
                img = s.images
            return {
                "id": s.id,
                "kind": "service",
                "name": s.name,
                "price": float(s.price) if s.price is not None else 0.0,
                "original_price": float(s.original_price) if s.original_price is not None else None,
                "image": img,
                "description": (s.description or "")[:200],
            }
    except Exception as e:  # noqa: BLE001
        logger.warning("ServiceItem 匹配失败：%s", e)

    return None


def _build_package_card(template: Dict[str, Any], matched: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把"推荐模板 + 数据库真实 SKU（如匹配到）"合并成结果页套餐卡。"""
    if matched:
        return {
            "sku_id": matched["id"],
            "sku_kind": matched["kind"],
            "name": matched["name"],
            "price": matched["price"],
            "original_price": matched.get("original_price"),
            "image": matched.get("image"),
            "description": matched.get("description"),
            "reason": template.get("reason"),
            "reason_tag_color": template.get("tag_color"),
            "matched": True,
        }
    # 未匹配到：返回"推荐模板占位"
    return {
        "sku_id": None,
        "sku_kind": None,
        "name": template.get("name"),
        "price": None,
        "original_price": None,
        "image": None,
        "description": None,
        "reason": template.get("reason"),
        "reason_tag_color": template.get("tag_color"),
        "matched": False,
    }


# ═══════════════════════════════════════════════════════════════════
# 1. 结果页聚合接口
# ═══════════════════════════════════════════════════════════════════


@router.get("/result/{diagnosis_id}")
async def get_full_result(
    diagnosis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """体质测评结果页 6 屏聚合数据。"""
    d = await _load_diagnosis(db, diagnosis_id, current_user.id)

    c_type = normalize_constitution_type(d.constitution_type)
    persona = get_persona(c_type)
    content = get_content(c_type)
    mapping = get_package_mapping(c_type)

    # 答题数据 + 雷达图得分
    answers = await _load_answers(db, diagnosis_id)
    radar_scores = compute_radar_scores(answers, c_type)

    # 推荐套餐（真实 SKU 优先匹配）
    primary_tpl = mapping.get("primary") or {}
    backup_tpl = mapping.get("backup")
    primary_matched = await _match_product_by_keywords(db, primary_tpl.get("keywords", []) if primary_tpl else [])
    backup_matched = None
    if backup_tpl:
        backup_matched = await _match_product_by_keywords(db, backup_tpl.get("keywords", []))

    packages: List[Dict[str, Any]] = []
    if primary_tpl:
        packages.append(_build_package_card(primary_tpl, primary_matched))
    if backup_tpl:
        packages.append(_build_package_card(backup_tpl, backup_matched))

    # 咨询人信息（如有）
    member_label = "本人"
    if d.family_member_id:
        fm = (await db.execute(
            select(FamilyMember).where(FamilyMember.id == d.family_member_id)
        )).scalar_one_or_none()
        if fm:
            member_label = fm.nickname or fm.relationship_type or "家庭成员"

    # 优惠券状态
    coupon_state = await _compute_coupon_state(db, current_user.id)

    # 6 屏聚合返回
    return {
        "diagnosis_id": d.id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "member_label": member_label,

        # ─── 第一屏：体质名片 ───
        "screen1_card": {
            "type": c_type,
            "persona": persona,
            "one_line_desc": persona.get("one_line"),
            "short_desc": content.get("short_desc"),
            "color": persona.get("color"),
            "radar": {
                "dimensions": RADAR_DIMENSIONS,
                "scores": [radar_scores.get(k, 0) for k in RADAR_DIMENSIONS],
            },
        },

        # ─── 第二屏：深度解读 ───
        "screen2_analysis": {
            "features": content.get("features", {}),
            "causes": content.get("causes", {}),
            "ai_summary": d.syndrome_analysis or "",
        },

        # ─── 第三屏：个性化养生方案 ───
        "screen3_plan": {
            "diet": content.get("diet", {}),
            "lifestyle": content.get("lifestyle", []),
            "exercise": content.get("exercise", []),
            "emotion": content.get("emotion", []),
            "ai_extra": d.health_plan or "",
        },

        # ─── 第四屏：套餐推荐 ───
        "screen4_packages": packages,

        # ─── 第五屏：广州门店服务 ───
        "screen5_store": {
            "city_restricted": True,
            "available_city": "广州",
            "coupon": coupon_state,
            "appointment_hint": "可选「艾灸调理」或「AI 精准检测」，预约后到店享专业服务",
            "non_guangzhou_fallback_text": "广州门店专属，其他城市敬请期待",
        },

        # ─── 第六屏：分享卡数据 ───
        "screen6_share": {
            "title": c_type,
            "subtitle": persona.get("one_line"),
            "persona": persona,
            "radar_preview": {
                "dimensions": RADAR_DIMENSIONS,
                "scores": [radar_scores.get(k, 0) for k in RADAR_DIMENSIONS],
            },
            "slogan": "一起测，测完约个艾灸",
            "qr_hint": "扫码参与体质测评",
        },

        "disclaimer": DISCLAIMER,
    }


# ═══════════════════════════════════════════════════════════════════
# 2. 优惠券状态 + 领取
# ═══════════════════════════════════════════════════════════════════


async def _compute_coupon_state(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    coupon = await _ensure_detection_coupon(db)
    if not coupon:
        return {
            "available": False,
            "status": "unavailable",
            "message": "优惠券系统暂时不可用",
            "coupon_id": None,
        }

    # 是否已领取
    existing_q = select(UserCoupon).where(
        UserCoupon.user_id == user_id,
        UserCoupon.coupon_id == coupon.id,
    )
    existing = (await db.execute(existing_q)).scalars().first()

    if not existing:
        return {
            "available": True,
            "status": "claimable",
            "message": "凭报告到店享 AI 精准检测体验券",
            "coupon_id": coupon.id,
            "coupon_name": coupon.name,
            "validity_days": coupon.validity_days,
        }

    # 已领取 → 细分状态
    uc_status = existing.status.value if hasattr(existing.status, "value") else str(existing.status)
    if uc_status == UserCouponStatus.used.value:
        return {
            "available": False,
            "status": "used",
            "message": "您已使用过该体验券",
            "coupon_id": coupon.id,
            "user_coupon_id": existing.id,
            "used_at": existing.used_at.isoformat() if existing.used_at else None,
        }

    return {
        "available": False,
        "status": "claimed",
        "message": "您已领取该体验券，可到「我的优惠券」查看",
        "coupon_id": coupon.id,
        "user_coupon_id": existing.id,
        "expire_at": existing.expire_at.isoformat() if existing.expire_at else None,
    }


@router.get("/coupon/status")
async def get_coupon_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await _compute_coupon_state(db, current_user.id)
    return state


@router.post("/coupon/claim")
async def claim_detection_coupon(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """领取 AI 精准检测体验券（每人限 1 张，有效期 30 天）。"""
    coupon = await _ensure_detection_coupon(db)
    if not coupon:
        raise HTTPException(status_code=400, detail="体验券暂不可用，请稍后再试")

    # 幂等：已领过直接返回现有记录
    existing = (await db.execute(
        select(UserCoupon).where(
            UserCoupon.user_id == current_user.id,
            UserCoupon.coupon_id == coupon.id,
        )
    )).scalars().first()
    if existing:
        return {
            "success": True,
            "already_claimed": True,
            "user_coupon_id": existing.id,
            "coupon_id": coupon.id,
            "expire_at": existing.expire_at.isoformat() if existing.expire_at else None,
        }

    # 计算过期时间
    now = datetime.utcnow()
    expire_at = now + timedelta(days=coupon.validity_days or DEFAULT_COUPON_VALIDITY_DAYS)

    try:
        uc = UserCoupon(
            user_id=current_user.id,
            coupon_id=coupon.id,
            expire_at=expire_at,
            source="tizhi_test",
        )
        db.add(uc)
        coupon.claimed_count = (coupon.claimed_count or 0) + 1
        await db.commit()
        await db.refresh(uc)
    except Exception as e:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"领取失败：{e}")

    return {
        "success": True,
        "already_claimed": False,
        "user_coupon_id": uc.id,
        "coupon_id": coupon.id,
        "coupon_name": coupon.name,
        "expire_at": expire_at.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. 我的体质档案（M10 最小版）
# ═══════════════════════════════════════════════════════════════════


@router.get("/archive")
async def list_archive(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的体质档案——按时间倒序的全部测评历史。"""
    q_all = select(TCMDiagnosis).where(TCMDiagnosis.user_id == current_user.id)
    all_rows = (await db.execute(q_all)).scalars().all()
    # 仅保留包含 constitution_type 的记录（排除纯舌诊/面诊记录）
    test_rows = [r for r in all_rows if r.constitution_type]
    test_rows.sort(key=lambda r: r.created_at or datetime.min, reverse=True)

    total = len(test_rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = test_rows[start:end]

    # 聚合 member label
    member_ids = list({r.family_member_id for r in page_rows if r.family_member_id})
    member_map: Dict[int, str] = {}
    if member_ids:
        fms = (await db.execute(
            select(FamilyMember).where(FamilyMember.id.in_(member_ids))
        )).scalars().all()
        member_map = {fm.id: (fm.nickname or fm.relationship_type or "成员") for fm in fms}

    items = []
    for r in page_rows:
        c_type = normalize_constitution_type(r.constitution_type)
        persona = get_persona(c_type)
        items.append({
            "diagnosis_id": r.id,
            "constitution_type": c_type,
            "persona_emoji": persona.get("emoji"),
            "persona_color": persona.get("color"),
            "one_line_desc": persona.get("one_line"),
            "member_label": member_map.get(r.family_member_id, "本人"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/archive/{diagnosis_id}")
async def get_archive_detail(
    diagnosis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """档案详情——直接复用结果页聚合数据（只读模式）。"""
    return await get_full_result(diagnosis_id, current_user, db)


# ═══════════════════════════════════════════════════════════════════
# 4. 体质百科（预留给运营后续可单独查一种体质的内容）
# ═══════════════════════════════════════════════════════════════════


@router.get("/encyclopedia/{constitution_type}")
async def get_encyclopedia(
    constitution_type: str,
    current_user: User = Depends(get_current_user),
):
    """查询某个体质的完整内容 + 拟人形象（不含个人测评数据）。"""
    c = normalize_constitution_type(constitution_type)
    return {
        "type": c,
        "persona": get_persona(c),
        "content": get_content(c),
        "package_mapping_preview": {
            "primary_name": (get_package_mapping(c).get("primary") or {}).get("name"),
            "primary_reason": (get_package_mapping(c).get("primary") or {}).get("reason"),
        },
        "disclaimer": DISCLAIMER,
    }
