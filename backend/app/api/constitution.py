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

from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    ConstitutionAnswer,
    ConstitutionContentConfig,
    Coupon,
    CouponScope,
    CouponStatus,
    CouponType,
    FamilyMember,
    Product,
    QuestionnaireAnswer,
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
admin_router = APIRouter(
    prefix="/api/admin/constitution", tags=["管理后台-体质测评运营配置"]
)

# 9 种体质（供后台下拉枚举）
CONSTITUTION_TYPES = [
    "平和质", "气虚质", "阳虚质", "阴虚质",
    "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
]
CONTENT_SECTIONS = ["meal", "store"]


def build_member_label(fm: Optional[FamilyMember]) -> str:
    """根据 PRD v1.0 § 4.1 规则拼装咨询人标签：姓名（关系）。

    - is_self=True         → 姓名（本人）
    - relation 为空/None    → 姓名（未设置）
    - 其他                  → 姓名（关系名）
    - fm 为 None           → "未知"（容错）
    """
    if fm is None:
        return "未知"
    name = (fm.nickname or "").strip() or "成员"
    if getattr(fm, "is_self", False):
        return f"{name}（本人）"
    relation = (fm.relationship_type or "").strip() or None
    if not relation or relation.lower() == "self":
        return f"{name}（未设置）"
    return f"{name}（{relation}）"


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
    """按 diagnosis_id 加载。先直接查 TCMDiagnosis.id，
    未命中时兼容按 QuestionnaireAnswer.id 反查（历史数据中前端可能传的是 answer_id）。
    """
    d = (await db.execute(
        select(TCMDiagnosis).where(TCMDiagnosis.id == diagnosis_id, TCMDiagnosis.user_id == user_id)
    )).scalar_one_or_none()
    if d:
        return d

    # 兼容：把 diagnosis_id 当作 QuestionnaireAnswer.id 尝试匹配
    qa = (await db.execute(
        select(QuestionnaireAnswer).where(
            QuestionnaireAnswer.id == diagnosis_id,
            QuestionnaireAnswer.user_id == user_id,
        )
    )).scalar_one_or_none()
    if qa:
        # 查找该用户最近的、与该 answer 时间相近的 TCMDiagnosis 记录
        d = (await db.execute(
            select(TCMDiagnosis).where(
                TCMDiagnosis.user_id == user_id,
                TCMDiagnosis.constitution_type.isnot(None),
            ).order_by(TCMDiagnosis.id.desc())
        )).scalars().first()
        if d:
            return d

    raise HTTPException(status_code=404, detail="体质测评记录不存在")


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


def _build_poster_tips(content: Dict[str, Any]) -> List[str]:
    """[PRD-TIZHI-OPTIM-V1] 优化点 4 形态二海报：3 条按体质自动匹配的调理建议。

    优先取「作息建议(lifestyle)」「情志调养(emotion)」，并附一条饮食宜食建议，
    全部来自体质内容库（非写死），保证不同体质海报建议不同。
    """
    tips: List[str] = []
    for x in (content.get("lifestyle") or [])[:2]:
        if x:
            tips.append(str(x))
    for x in (content.get("emotion") or [])[:1]:
        if x and len(tips) < 3:
            tips.append(str(x))
    diet_good = (content.get("diet") or {}).get("good") or []
    if diet_good and len(tips) < 3:
        tips.append("宜食：" + "、".join([str(g) for g in diet_good[:4]]))
    # 兜底补足到 3 条
    fallback = ["规律作息，早睡早起", "适度运动，循序渐进", "饮食清淡，均衡营养"]
    i = 0
    while len(tips) < 3 and i < len(fallback):
        if fallback[i] not in tips:
            tips.append(fallback[i])
        i += 1
    return tips[:3]


async def _load_content_configs(
    db: AsyncSession, constitution_type: str, section: str
) -> List[Dict[str, Any]]:
    """[PRD-TIZHI-OPTIM-V1] 加载某体质 + 板块的「运营配置内容卡」（仅启用项，按 sort_order）。

    返回结果用于结果页详情的「专属膳食套餐 / 门店服务」两块；
    无任何启用项时返回空列表，前端据此整块隐藏（不展示占位假文案）。
    """
    try:
        q = (
            select(ConstitutionContentConfig)
            .where(
                ConstitutionContentConfig.constitution_type == constitution_type,
                ConstitutionContentConfig.section == section,
                ConstitutionContentConfig.enabled.is_(True),
            )
            .order_by(
                ConstitutionContentConfig.sort_order.asc(),
                ConstitutionContentConfig.id.asc(),
            )
        )
        rows = (await db.execute(q)).scalars().all()
    except Exception as e:  # noqa: BLE001
        logger.warning("加载体质运营配置失败 type=%s section=%s err=%s", constitution_type, section, e)
        return []

    items: List[Dict[str, Any]] = []
    for r in rows:
        items.append({
            "id": r.id,
            "title": r.title,
            "subtitle": r.subtitle,
            "image": r.image,
            "tag": r.tag,
            "tag_color": r.tag_color,
            "price": r.price,
            "original_price": r.original_price,
            "link_type": r.link_type or "none",
            "link_value": r.link_value,
            "button_text": r.button_text,
        })
    return items


# ═══════════════════════════════════════════════════════════════════
# 0. answer_id → diagnosis_id 反查接口（兼容历史数据）
# ═══════════════════════════════════════════════════════════════════


@router.get("/diagnosis-by-answer/{answer_id}")
async def get_diagnosis_by_answer_id(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通过 QuestionnaireAnswer.id 反查对应的 TCMDiagnosis.id。"""
    d = (await db.execute(
        select(TCMDiagnosis).where(
            TCMDiagnosis.user_id == current_user.id,
            TCMDiagnosis.constitution_type.isnot(None),
        ).order_by(TCMDiagnosis.id.desc())
    )).scalars().first()
    if not d:
        raise HTTPException(status_code=404, detail="未找到对应的体质测评记录")
    return {"diagnosis_id": d.id, "answer_id": answer_id}


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

    # 答题数据 + 雷达图得分
    answers = await _load_answers(db, diagnosis_id)
    radar_scores = compute_radar_scores(answers, c_type)

    # [PRD-TIZHI-OPTIM-V1] 优化点 2：专属膳食套餐 / 门店服务改为后台可运营配置，
    # 按体质类型智能匹配；无配置则整块隐藏（前端据空列表隐藏，不再有占位假文案）。
    meal_packages = await _load_content_configs(db, c_type, "meal")
    store_services = await _load_content_configs(db, c_type, "store")

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

        # ─── 第四屏：专属膳食套餐（后台运营配置驱动，按体质匹配；无内容则整块隐藏）───
        "screen4_packages": meal_packages,

        # ─── 第五屏：门店服务（后台运营配置驱动，按体质匹配；无内容则整块隐藏）───
        "screen5_store": {
            "services": store_services,
            "coupon": coupon_state,
        },

        # ─── 第六屏：分享卡数据（优化点 4：标题动态带体质 + 固定精美封面 + 品牌天蓝）───
        "screen6_share": {
            "title": c_type,
            # 好友/群转发卡片标题：动态带上用户体质
            "share_title": f"我的体质是「{c_type}」，快来测测你是什么体质？",
            "subtitle": persona.get("one_line"),
            "persona": persona,
            "brand": "宾尼小康",
            # 统一固定精美封面图：与关怀模式欢迎区一致的圆形头像 Logo（各分享形态统一）
            "cover_image": "/binni-xiaokang-logo.png",
            "logo_image": "/binni-xiaokang-logo.png",
            "radar_preview": {
                "dimensions": RADAR_DIMENSIONS,
                "scores": [radar_scores.get(k, 0) for k in RADAR_DIMENSIONS],
            },
            # 海报下部 3 条按体质自动匹配的调理建议（非写死，取内容库 lifestyle/emotion/diet）
            "poster_tips": _build_poster_tips(content),
            "slogan": "长按识别测测你的体质",
            "qr_hint": "长按识别测测你的体质",
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

    # 聚合 member label（按 PRD v1.0 规则拼装：姓名（本人/关系/未设置））
    member_ids = list({r.family_member_id for r in page_rows if r.family_member_id})
    member_map: Dict[int, str] = {}
    if member_ids:
        fms = (await db.execute(
            select(FamilyMember).where(FamilyMember.id.in_(member_ids))
        )).scalars().all()
        member_map = {fm.id: build_member_label(fm) for fm in fms}

    items = []
    for r in page_rows:
        c_type = normalize_constitution_type(r.constitution_type)
        persona = get_persona(c_type)
        # 当 family_member_id 为空或对应档案不存在时，默认归为"本人"
        label = member_map.get(r.family_member_id) if r.family_member_id else None
        if not label:
            # 家庭档案已被删除 / 无 family_member_id 的历史记录：兜底"未知"或"本人"
            label = "本人" if not r.family_member_id else "未知"
        items.append({
            "diagnosis_id": r.id,
            "constitution_type": c_type,
            "persona_emoji": persona.get("emoji"),
            "persona_color": persona.get("color"),
            "one_line_desc": persona.get("one_line"),
            "member_label": label,
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
        "disclaimer": DISCLAIMER,
    }


# ═══════════════════════════════════════════════════════════════════
# 5. 后台运营配置 CRUD（[PRD-TIZHI-OPTIM-V1] 优化点 2）
#    专属膳食套餐 / 门店服务 按体质类型可运营维护
# ═══════════════════════════════════════════════════════════════════


class ContentConfigIn(BaseModel):
    constitution_type: str
    section: str  # meal | store
    title: str
    subtitle: Optional[str] = None
    image: Optional[str] = None
    tag: Optional[str] = None
    tag_color: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    link_type: Optional[str] = "none"
    link_value: Optional[str] = None
    button_text: Optional[str] = None
    sort_order: Optional[int] = 0
    enabled: Optional[bool] = True


def _serialize_config(r: ConstitutionContentConfig) -> Dict[str, Any]:
    return {
        "id": r.id,
        "constitution_type": r.constitution_type,
        "section": r.section,
        "title": r.title,
        "subtitle": r.subtitle,
        "image": r.image,
        "tag": r.tag,
        "tag_color": r.tag_color,
        "price": r.price,
        "original_price": r.original_price,
        "link_type": r.link_type or "none",
        "link_value": r.link_value,
        "button_text": r.button_text,
        "sort_order": r.sort_order or 0,
        "enabled": bool(r.enabled),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _validate_type_section(constitution_type: str, section: str) -> None:
    if constitution_type not in CONSTITUTION_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的体质类型：{constitution_type}")
    if section not in CONTENT_SECTIONS:
        raise HTTPException(status_code=422, detail="section 只能是 meal 或 store")


@admin_router.get("/meta")
async def admin_config_meta(_=Depends(require_role("admin"))):
    """下拉枚举：体质类型 + 板块。"""
    return {
        "constitution_types": CONSTITUTION_TYPES,
        "sections": [
            {"value": "meal", "label": "专属膳食套餐"},
            {"value": "store", "label": "门店服务"},
        ],
        "link_types": [
            {"value": "none", "label": "无跳转"},
            {"value": "product", "label": "商品详情"},
            {"value": "service", "label": "服务详情"},
            {"value": "order", "label": "预约下单"},
            {"value": "coupon", "label": "领券"},
            {"value": "url", "label": "外链"},
        ],
    }


@admin_router.get("/content-configs")
async def admin_list_content_configs(
    constitution_type: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    _=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(ConstitutionContentConfig)
    if constitution_type:
        q = q.where(ConstitutionContentConfig.constitution_type == constitution_type)
    if section:
        q = q.where(ConstitutionContentConfig.section == section)
    q = q.order_by(
        ConstitutionContentConfig.constitution_type.asc(),
        ConstitutionContentConfig.section.asc(),
        ConstitutionContentConfig.sort_order.asc(),
        ConstitutionContentConfig.id.asc(),
    )
    rows = (await db.execute(q)).scalars().all()
    return {"items": [_serialize_config(r) for r in rows], "total": len(rows)}


@admin_router.post("/content-configs")
async def admin_create_content_config(
    data: ContentConfigIn,
    _=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    _validate_type_section(data.constitution_type, data.section)
    row = ConstitutionContentConfig(
        constitution_type=data.constitution_type,
        section=data.section,
        title=data.title,
        subtitle=data.subtitle,
        image=data.image,
        tag=data.tag,
        tag_color=data.tag_color,
        price=data.price,
        original_price=data.original_price,
        link_type=data.link_type or "none",
        link_value=data.link_value,
        button_text=data.button_text,
        sort_order=data.sort_order or 0,
        enabled=True if data.enabled is None else bool(data.enabled),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_config(row)


@admin_router.put("/content-configs/{config_id}")
async def admin_update_content_config(
    config_id: int,
    data: ContentConfigIn,
    _=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    _validate_type_section(data.constitution_type, data.section)
    row = (await db.execute(
        select(ConstitutionContentConfig).where(ConstitutionContentConfig.id == config_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    row.constitution_type = data.constitution_type
    row.section = data.section
    row.title = data.title
    row.subtitle = data.subtitle
    row.image = data.image
    row.tag = data.tag
    row.tag_color = data.tag_color
    row.price = data.price
    row.original_price = data.original_price
    row.link_type = data.link_type or "none"
    row.link_value = data.link_value
    row.button_text = data.button_text
    row.sort_order = data.sort_order or 0
    if data.enabled is not None:
        row.enabled = bool(data.enabled)
    await db.commit()
    await db.refresh(row)
    return _serialize_config(row)


@admin_router.delete("/content-configs/{config_id}")
async def admin_delete_content_config(
    config_id: int,
    _=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(ConstitutionContentConfig).where(ConstitutionContentConfig.id == config_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    await db.delete(row)
    await db.commit()
    return {"success": True}
