"""[PRD-469] 健康档案 v2 优化 —— 对齐 v5 设计稿。

本模块新增以下核心能力：
- 药品库联想搜索 + OCR 占位
- 健康信息（既往病史/过敏/家族病史/个人习惯）
- 关系选项 + 头像 emoji
- 设备绑定列表（10 项设备）
- 健康事件时间轴 + 手动日记
- 提醒规则配置
- 主页聚合数据接口
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    DeviceBinding,
    FamilyManagement,
    FamilyMember,
    HealthEvent,
    HealthInfoExtra,
    HealthProfile,
    MedicalRecordCard,
    MedicationLibrary,
    MedicationReminder,
    ReminderSetting,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prd469", tags=["PRD-469 健康档案 v2 优化"])


# ──────────────────────────────────────────────────────────
# [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 「在用药品」统一口径
# ──────────────────────────────────────────────────────────

async def _count_active_medications(db: AsyncSession, user_id: int) -> int:
    """统一「在用药品」计数口径。

    在用药品 = MedicationReminder WHERE
        user_id = current_user
        AND status = 'active'
        AND (long_term = True OR end_date IS NULL OR end_date >= TODAY)
    """
    today = date.today()
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    )
    res = await db.execute(stmt)
    return len(res.scalars().all())


# ──────────────────────────────────────────────────────────
# 关系选项 + 头像（M3）
# ──────────────────────────────────────────────────────────

RELATION_AVATAR_MAP: Dict[str, str] = {
    "本人": "🙂",
    "爸爸": "👨",
    "妈妈": "👩",
    "老公": "🤵",
    "老婆": "👰",
    "儿子": "👦",
    "女儿": "👧",
    "哥哥": "🧑‍🦱",
    "弟弟": "👨‍🦱",
    "姐姐": "👩‍🦰",
    "妹妹": "👧",
    "爷爷": "👴",
    "奶奶": "👵",
    "外公": "👴",
    "外婆": "👵",
    "其他": "🧑",
}


@router.get("/family-member/relation-options")
async def list_relation_options():
    """关系选项 + 头像 emoji（与 AI 对话页共用）。"""
    items = []
    for idx, (name, emoji) in enumerate(RELATION_AVATAR_MAP.items()):
        items.append(
            {
                "key": name,
                "name": name,
                "avatar": emoji,
                "is_other": name == "其他",
                "sort_order": idx,
            }
        )
    return {"items": items, "total": len(items)}


class CustomRelationCheck(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)


@router.post("/family-member/relation-custom/check")
async def check_custom_relation(
    body: CustomRelationCheck,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """校验「其他」自定义关系名是否与已有关系名冲突。"""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="关系名不能为空")
    if name in RELATION_AVATAR_MAP:
        return {"valid": False, "reason": f"关系『{name}』与预置关系名冲突，请换一个名称"}

    result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "bound",
            FamilyMember.nickname == name,
        )
    )
    if result.scalar_one_or_none() is not None:
        return {"valid": False, "reason": f"关系『{name}』已存在，请换一个名称（如『大儿子』『二儿子』）"}

    return {"valid": True}


# ──────────────────────────────────────────────────────────
# 药品库 M10
# ──────────────────────────────────────────────────────────


class MedicationLibItemOut(BaseModel):
    id: int
    name: str
    generic_name: Optional[str] = None
    spec: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    rx_type: Optional[str] = None
    disease_tags: Optional[List[str]] = None

    class Config:
        from_attributes = True


@router.get("/medication-library/search")
async def medication_library_search(
    kw: str = Query("", description="联想关键词"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """药品库联想搜索（基于药品名 / 通用名 / 商品名 三字段并行匹配）。"""
    kw = (kw or "").strip()
    if not kw:
        return {"items": [], "total": 0}

    pattern = f"%{kw}%"
    result = await db.execute(
        select(MedicationLibrary)
        .where(
            MedicationLibrary.is_active == True,  # noqa: E712
            or_(
                MedicationLibrary.name.ilike(pattern),
                MedicationLibrary.generic_name.ilike(pattern),
            ),
        )
        .limit(limit)
    )
    rows = result.scalars().all()
    return {
        "items": [MedicationLibItemOut.model_validate(r).model_dump() for r in rows],
        "total": len(rows),
    }


@router.get("/medication-library/stats")
async def medication_library_stats(db: AsyncSession = Depends(get_db)):
    """[PRD-469 M10 v2] 药品库统计：总条数 + 按 source 分组 + 按疾病标签分布。

    用于验证四源融合数据是否已成功入库，并暴露给运营后台监控。
    """
    from sqlalchemy import func as _func

    total_q = await db.execute(
        select(_func.count(MedicationLibrary.id)).where(
            MedicationLibrary.is_active == True  # noqa: E712
        )
    )
    total = int(total_q.scalar() or 0)

    src_q = await db.execute(
        select(MedicationLibrary.source, _func.count(MedicationLibrary.id))
        .where(MedicationLibrary.is_active == True)  # noqa: E712
        .group_by(MedicationLibrary.source)
    )
    by_source: Dict[str, int] = {}
    for src, cnt in src_q.all():
        by_source[src or "unknown"] = int(cnt)

    rx_q = await db.execute(
        select(MedicationLibrary.rx_type, _func.count(MedicationLibrary.id))
        .where(MedicationLibrary.is_active == True)  # noqa: E712
        .group_by(MedicationLibrary.rx_type)
    )
    by_rx_type: Dict[str, int] = {}
    for rx, cnt in rx_q.all():
        by_rx_type[rx or "unknown"] = int(cnt)

    return {
        "total": total,
        "by_source": by_source,
        "by_rx_type": by_rx_type,
        "four_sources_present": all(
            s in by_source for s in ("medi_catalog", "essential_drugs", "nmpa", "top1000")
        ),
        "meets_3000_target": total >= 3000,
    }


@router.get("/medication-library/{drug_id}")
async def medication_library_detail(
    drug_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationLibrary).where(MedicationLibrary.id == drug_id)
    )
    drug = result.scalar_one_or_none()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    return {
        "id": drug.id,
        "name": drug.name,
        "generic_name": drug.generic_name,
        "spec": drug.spec,
        "manufacturer": drug.manufacturer,
        "approval_no": drug.approval_no,
        "category": drug.category,
        "rx_type": drug.rx_type,
        "disease_tags": drug.disease_tags or [],
        "indications": drug.indications,
        "usage": drug.usage,
        "contraindications": drug.contraindications,
        "adverse_reactions": drug.adverse_reactions,
        "notes": drug.notes,
        "source": drug.source,
    }


class OcrRecognizeRequest(BaseModel):
    image_text: Optional[str] = Field(None, description="百度 OCR 返回的文字片段（前端调用 OCR 后回传）")


@router.post("/medication-library/ocr")
async def medication_library_ocr(
    body: OcrRecognizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """拍照识药：基于 OCR 文字在药品库内做模糊匹配，返回 Top 5 候选。

    本期对接百度 OCR 由前端负责调用既有 /api/ocr 通用接口，本端点专注库内匹配。
    """
    text = (body.image_text or "").strip()
    if not text:
        return {"items": [], "total": 0, "reason": "OCR 文字为空"}

    tokens = [t for t in text.replace("\n", " ").split(" ") if len(t) >= 2][:8]
    if not tokens:
        return {"items": [], "total": 0, "reason": "未提取到有效药名候选"}

    candidates: List[MedicationLibrary] = []
    seen_ids = set()
    for tok in tokens:
        pattern = f"%{tok}%"
        result = await db.execute(
            select(MedicationLibrary)
            .where(
                MedicationLibrary.is_active == True,  # noqa: E712
                or_(
                    MedicationLibrary.name.ilike(pattern),
                    MedicationLibrary.generic_name.ilike(pattern),
                ),
            )
            .limit(5)
        )
        for r in result.scalars().all():
            if r.id not in seen_ids:
                candidates.append(r)
                seen_ids.add(r.id)
        if len(candidates) >= 5:
            break

    return {
        "items": [MedicationLibItemOut.model_validate(r).model_dump() for r in candidates[:5]],
        "total": min(5, len(candidates)),
        "matched_tokens": tokens,
    }


# ──────────────────────────────────────────────────────────
# [AI对话模式优化 PRD v1.0 §9] 拍照识药 —— 一站式 /recognize
# 设计要点：
#   - 前端只调一次接口，传入 image 文件 + prompt_template_id
#   - 后端内部完成：（未来）扫码 → OCR → 模糊匹配 → AI 解读
#   - 本期固定走 OCR 单路径，barcode 字段已在 schema 预留
#   - 返回：drug_candidates + ai_response 一站式数据
# ──────────────────────────────────────────────────────────


from fastapi import File, UploadFile, Form  # noqa: E402


@router.post("/medication-library/recognize")
async def medication_library_recognize(
    image: Optional[UploadFile] = File(None, description="药品图片文件 multipart"),
    image_url: Optional[str] = Form(None, description="替代 image 的图片 URL（已上传后回填）"),
    image_text: Optional[str] = Form(None, description="替代 image 的预 OCR 文字（兼容旧前端）"),
    prompt_template_id: Optional[int] = Form(None, description="关联 Prompt 模板 ID"),
    db: AsyncSession = Depends(get_db),
):
    """[AI对话模式优化 PRD v1.0 §9.2] 一站式识药接口。

    - 前端单次调用即可拿到完整结果（drug_candidates + ai_response）
    - 内部目前固定走 OCR 路径，barcode/扫码识别为未来扩展点
    - method 字段用于告知前端本次使用的识别路径（"ocr" / "barcode"）
    """
    from app.services.ai_service import call_ai_model

    ocr_text = (image_text or "").strip()

    # 路径 1（未来）：扫码识药 —— 占位，barcode 字段已在 MedicationLibrary 中预留
    matched_by_barcode = None

    # 路径 2（本期）：OCR + 模糊匹配
    if not ocr_text and image is not None:
        # 本期不在 recognize 内部直跑 OCR（避免引入新的服务依赖与超时风险），
        # 推荐前端先调通用 /api/ocr/recognize 拿到 image_text 再回传到本接口。
        # 这里仅做兜底：若客户端只传了文件而没传 image_text，则置空走 AI 兜底。
        try:
            _ = await image.read()  # 读出但暂不消费，保证文件流闭合
        except Exception:
            pass
        ocr_text = ""

    candidates: List[MedicationLibrary] = []
    matched_tokens: List[str] = []
    if ocr_text:
        tokens = [t for t in ocr_text.replace("\n", " ").split(" ") if len(t) >= 2][:8]
        matched_tokens = tokens
        seen_ids: set = set()
        for tok in tokens:
            pattern = f"%{tok}%"
            res = await db.execute(
                select(MedicationLibrary)
                .where(
                    MedicationLibrary.is_active == True,  # noqa: E712
                    or_(
                        MedicationLibrary.name.ilike(pattern),
                        MedicationLibrary.generic_name.ilike(pattern),
                    ),
                )
                .limit(5)
            )
            for r in res.scalars().all():
                if r.id not in seen_ids:
                    candidates.append(r)
                    seen_ids.add(r.id)
            if len(candidates) >= 5:
                break

    drug_candidates = [
        MedicationLibItemOut.model_validate(r).model_dump() for r in candidates[:5]
    ]

    # AI 解读：用关联的 Prompt 模板（若指定），否则使用通用药品识别 prompt
    system_prompt = (
        "你是一位专业的药品识别 AI 助手。请根据用户提供的药品候选列表与 OCR 文字，"
        "给出药品名称归类、用法用量、注意事项等关键信息，所有内容仅供参考，"
        "具体用药请严格遵医嘱。"
    )
    if prompt_template_id:
        try:
            from app.models.models import PromptTemplate  # type: ignore
            pt_res = await db.execute(
                select(PromptTemplate).where(PromptTemplate.id == prompt_template_id)
            )
            pt = pt_res.scalar_one_or_none()
            if pt and getattr(pt, "content", None):
                system_prompt = pt.content
        except Exception as exc:  # noqa: BLE001
            logger.debug("[recognize] PromptTemplate 加载失败：%s", exc)

    user_prompt = (
        f"OCR 识别文字：{ocr_text or '（无）'}\n"
        f"候选药品（共 {len(drug_candidates)} 条）：\n"
        + "\n".join(
            f"- {c['name']} {c.get('spec') or ''} {c.get('manufacturer') or ''}"
            for c in drug_candidates
        )
        + "\n\n请基于以上信息给出该药品的简明分析、用法用量与注意事项。"
    )

    ai_response = ""
    try:
        ai_result = await call_ai_model(
            [{"role": "user", "content": user_prompt}],
            system_prompt,
            db,
            return_usage=True,
        )
        ai_response = ai_result["content"] if isinstance(ai_result, dict) else (ai_result or "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[recognize] AI 解读失败：%s", exc)
        ai_response = "AI 解读暂不可用，请稍后再试或联系客服。"

    return {
        "code": 0,
        "data": {
            "recognized": bool(drug_candidates) or bool(matched_by_barcode),
            "method": "barcode" if matched_by_barcode else "ocr",
            "drug_candidates": drug_candidates,
            "ai_response": ai_response,
            "matched_tokens": matched_tokens,
        },
    }


# ──────────────────────────────────────────────────────────
# 健康信息 M6
# ──────────────────────────────────────────────────────────


class HealthInfoBody(BaseModel):
    chronic_diseases: Optional[List[Dict[str, Any]]] = None
    surgery_history: Optional[List[Dict[str, Any]]] = None
    drug_allergies: Optional[List[str]] = None
    food_allergies: Optional[List[str]] = None
    other_allergies: Optional[List[str]] = None
    family_history: Optional[List[Dict[str, Any]]] = None
    habit_smoking: Optional[str] = None
    habit_drinking: Optional[str] = None
    habit_exercise: Optional[str] = None
    habit_diet: Optional[str] = None


async def _get_or_create_health_info(db: AsyncSession, profile_id: int) -> HealthInfoExtra:
    result = await db.execute(
        select(HealthInfoExtra).where(HealthInfoExtra.profile_id == profile_id)
    )
    info = result.scalar_one_or_none()
    if info is None:
        info = HealthInfoExtra(profile_id=profile_id)
        db.add(info)
        await db.flush()
    return info


@router.get("/health-info/{profile_id}")
async def get_health_info(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id, HealthProfile.user_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")

    info = await _get_or_create_health_info(db, profile_id)
    return {
        "profile_id": profile_id,
        "chronic_diseases": info.chronic_diseases or [],
        "surgery_history": info.surgery_history or [],
        "drug_allergies": info.drug_allergies or [],
        "food_allergies": info.food_allergies or [],
        "other_allergies": info.other_allergies or [],
        "family_history": info.family_history or [],
        "habit_smoking": info.habit_smoking,
        "habit_drinking": info.habit_drinking,
        "habit_exercise": info.habit_exercise,
        "habit_diet": info.habit_diet,
    }


@router.put("/health-info/{profile_id}")
async def update_health_info(
    profile_id: int,
    body: HealthInfoBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id, HealthProfile.user_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")

    info = await _get_or_create_health_info(db, profile_id)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(info, key, value)
    await db.flush()
    return {"message": "已保存", "profile_id": profile_id}


# ──────────────────────────────────────────────────────────
# 设备绑定列表 M9
# ──────────────────────────────────────────────────────────

DEVICE_CATALOG = [
    {"key": "huawei_band", "name": "华为手环", "status": "connected", "icon": "⌚"},
    {"key": "mi_band", "name": "小米手环", "status": "coming_soon", "icon": "⌚"},
    {"key": "apple_watch", "name": "Apple Watch", "status": "coming_soon", "icon": "⌚"},
    {"key": "huawei_watch_gt", "name": "华为手表 GT", "status": "coming_soon", "icon": "⌚"},
    {"key": "sannuo_glucose", "name": "三诺血糖仪", "status": "coming_soon", "icon": "🩸"},
    {"key": "yuyue_bp", "name": "鱼跃血压计", "status": "coming_soon", "icon": "💓"},
    {"key": "omron_bp", "name": "欧姆龙血压计", "status": "coming_soon", "icon": "💓"},
    {"key": "yuyue_spo2", "name": "鱼跃血氧仪", "status": "coming_soon", "icon": "🫁"},
    {"key": "mi_scale", "name": "小米体重秤", "status": "coming_soon", "icon": "⚖️"},
    {"key": "huawei_scale", "name": "华为体脂秤", "status": "coming_soon", "icon": "⚖️"},
]


@router.get("/device/list")
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设备绑定列表：10 项固定清单 + 用户已绑定的设备状态。"""
    result = await db.execute(
        select(DeviceBinding).where(
            DeviceBinding.user_id == current_user.id,
            DeviceBinding.status == "active",
        )
    )
    bound: Dict[str, DeviceBinding] = {
        b.device_type: b for b in result.scalars().all()
    }

    items = []
    for d in DEVICE_CATALOG:
        item = dict(d)
        bind = bound.get(d["key"])
        if bind is not None and d["status"] == "connected":
            item["bound"] = True
            item["bound_at"] = bind.bound_at.isoformat() if bind.bound_at else None
            item["last_sync_at"] = (
                bind.last_sync_at.isoformat() if bind.last_sync_at else None
            )
        else:
            item["bound"] = False
        items.append(item)
    return {"items": items, "total": len(items)}


class DeviceSubscribeBody(BaseModel):
    device_key: str


@router.post("/device/subscribe")
async def subscribe_device(
    body: DeviceSubscribeBody,
    current_user: User = Depends(get_current_user),
):
    """敬请期待设备的「上线后通知我」订阅入口（占位实现）。"""
    return {"message": f"已记录订阅，设备上线后将通过站内消息通知您", "device_key": body.device_key}


# ──────────────────────────────────────────────────────────
# 健康事件 M8
# ──────────────────────────────────────────────────────────


class HealthEventCreate(BaseModel):
    event_type: str = Field(..., description="diary/medication/abnormal/upload/note")
    title: Optional[str] = None
    content: Optional[str] = None
    event_date: Optional[date] = None
    tags: Optional[List[str]] = None
    profile_id: Optional[int] = None


@router.get("/health-event/timeline")
async def get_event_timeline(
    profile_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(HealthEvent).where(HealthEvent.user_id == current_user.id)
    if profile_id is not None:
        stmt = stmt.where(HealthEvent.profile_id == profile_id)
    if event_type:
        stmt = stmt.where(HealthEvent.event_type == event_type)
    stmt = stmt.order_by(HealthEvent.event_date.desc(), HealthEvent.id.desc()).limit(limit)
    result = await db.execute(stmt)
    items = []
    for e in result.scalars().all():
        items.append(
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title,
                "content": e.content,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "tags": e.tags or [],
                "extra_data": e.extra_data or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
        )
    return {"items": items, "total": len(items)}


@router.post("/health-event")
async def create_health_event(
    body: HealthEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = HealthEvent(
        user_id=current_user.id,
        profile_id=body.profile_id,
        event_type=body.event_type,
        title=body.title,
        content=body.content,
        event_date=body.event_date or date.today(),
        tags=body.tags,
    )
    db.add(event)
    await db.flush()
    return {"id": event.id, "message": "已添加"}


# ──────────────────────────────────────────────────────────
# 提醒规则 M7
# ──────────────────────────────────────────────────────────


class ReminderSettingBody(BaseModel):
    miss_threshold_days: Optional[int] = Field(None, ge=1, le=30)
    push_inapp: Optional[bool] = None
    push_wechat: Optional[bool] = None
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None
    notify_caregivers: Optional[bool] = None
    # [PRD-MED-PLAN-V1 2026-05-16] 用药 AI 外呼提醒全局开关
    medication_ai_call_enabled: Optional[bool] = None


async def _get_or_create_reminder(db: AsyncSession, user_id: int) -> ReminderSetting:
    result = await db.execute(
        select(ReminderSetting).where(ReminderSetting.user_id == user_id)
    )
    s = result.scalar_one_or_none()
    if s is None:
        s = ReminderSetting(user_id=user_id)
        db.add(s)
        await db.flush()
    return s


@router.get("/reminder-setting")
async def get_reminder_setting(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_or_create_reminder(db, current_user.id)
    return {
        "miss_threshold_days": s.miss_threshold_days,
        "push_inapp": s.push_inapp,
        "push_wechat": s.push_wechat,
        "silent_start": s.silent_start,
        "silent_end": s.silent_end,
        "notify_caregivers": s.notify_caregivers,
        # [PRD-MED-PLAN-V1 2026-05-16] 用药 AI 外呼提醒全局开关
        "medication_ai_call_enabled": bool(getattr(s, "medication_ai_call_enabled", False) or False),
    }


@router.put("/reminder-setting")
async def update_reminder_setting(
    body: ReminderSettingBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_or_create_reminder(db, current_user.id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    return {"message": "已保存"}


# ──────────────────────────────────────────────────────────
# [PRD-MED-PLAN-V1 2026-05-16] 用药 AI 外呼提醒全局开关
# 在「健康提醒」与「共管」两个模块共用同一份数据：
# - GET  /api/prd469/medication-ai-call          → 读取
# - PUT  /api/prd469/medication-ai-call          → 写入
# - GET  /api/prd469/care/medication-ai-call     → 共管模块读取（同上）
# - PUT  /api/prd469/care/medication-ai-call     → 共管模块写入（同上）
# ──────────────────────────────────────────────────────────


class MedicationAiCallBody(BaseModel):
    enabled: bool


async def _read_med_ai_call(db: AsyncSession, user_id: int) -> dict:
    s = await _get_or_create_reminder(db, user_id)
    return {"enabled": bool(getattr(s, "medication_ai_call_enabled", False) or False)}


async def _write_med_ai_call(db: AsyncSession, user_id: int, enabled: bool) -> dict:
    s = await _get_or_create_reminder(db, user_id)
    s.medication_ai_call_enabled = bool(enabled)
    await db.flush()
    return {"enabled": bool(s.medication_ai_call_enabled)}


@router.get("/medication-ai-call")
async def get_medication_ai_call(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _read_med_ai_call(db, current_user.id)


@router.put("/medication-ai-call")
async def update_medication_ai_call(
    body: MedicationAiCallBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _write_med_ai_call(db, current_user.id, body.enabled)


@router.get("/care/medication-ai-call")
async def get_medication_ai_call_care(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """共管模块入口（与健康提醒入口共用同一份数据）。"""
    return await _read_med_ai_call(db, current_user.id)


@router.put("/care/medication-ai-call")
async def update_medication_ai_call_care(
    body: MedicationAiCallBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """共管模块入口（与健康提醒入口共用同一份数据）。"""
    return await _write_med_ai_call(db, current_user.id, body.enabled)


# ──────────────────────────────────────────────────────────
# 家族病史独立 CRUD（M6 P0）
# ──────────────────────────────────────────────────────────


class FamilyHistoryItem(BaseModel):
    relation: str = Field(..., min_length=1, max_length=32)
    disease: str = Field(..., min_length=1, max_length=64)
    note: Optional[str] = Field(None, max_length=128)


@router.get("/health-info/{profile_id}/family-history")
async def get_family_history(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = info.family_history or []
    return {"items": items, "total": len(items)}


@router.post("/health-info/{profile_id}/family-history")
async def add_family_history(
    profile_id: int,
    body: FamilyHistoryItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.family_history or [])
    items.append(body.model_dump())
    info.family_history = items
    await db.flush()
    return {"message": "已添加", "items": items, "total": len(items)}


@router.put("/health-info/{profile_id}/family-history/{item_index}")
async def update_family_history(
    profile_id: int,
    item_index: int,
    body: FamilyHistoryItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.family_history or [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="条目不存在")
    items[item_index] = body.model_dump()
    info.family_history = items
    await db.flush()
    return {"message": "已更新", "items": items, "total": len(items)}


@router.delete("/health-info/{profile_id}/family-history/{item_index}")
async def delete_family_history(
    profile_id: int,
    item_index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.family_history or [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="条目不存在")
    items.pop(item_index)
    info.family_history = items
    await db.flush()
    return {"message": "已删除", "items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────
# 手术史独立 CRUD（M6 P0）
# ──────────────────────────────────────────────────────────


class SurgeryHistoryItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    time: Optional[str] = Field(None, max_length=32)
    note: Optional[str] = Field(None, max_length=128)


@router.get("/health-info/{profile_id}/surgery-history")
async def get_surgery_history(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = info.surgery_history or []
    return {"items": items, "total": len(items)}


@router.post("/health-info/{profile_id}/surgery-history")
async def add_surgery_history(
    profile_id: int,
    body: SurgeryHistoryItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.surgery_history or [])
    items.append(body.model_dump())
    info.surgery_history = items
    await db.flush()
    return {"message": "已添加", "items": items, "total": len(items)}


@router.put("/health-info/{profile_id}/surgery-history/{item_index}")
async def update_surgery_history(
    profile_id: int,
    item_index: int,
    body: SurgeryHistoryItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.surgery_history or [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="条目不存在")
    items[item_index] = body.model_dump()
    info.surgery_history = items
    await db.flush()
    return {"message": "已更新", "items": items, "total": len(items)}


@router.delete("/health-info/{profile_id}/surgery-history/{item_index}")
async def delete_surgery_history(
    profile_id: int,
    item_index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    items = list(info.surgery_history or [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="条目不存在")
    items.pop(item_index)
    info.surgery_history = items
    await db.flush()
    return {"message": "已删除", "items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────
# M2 Hero 四格健康摘要统计（P1）
# ──────────────────────────────────────────────────────────


@router.get("/summary-stats/{profile_id}")
async def get_summary_stats(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await _get_or_create_health_info(db, profile_id)
    chronic_count = len(info.chronic_diseases or [])
    allergy_count = (
        len(info.drug_allergies or [])
        + len(info.food_allergies or [])
        + len(info.other_allergies or [])
    )
    family_history_count = len(info.family_history or [])

    # [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 「在用药品」统一口径
    long_term_med_count = await _count_active_medications(db, current_user.id)

    return {
        "chronic_count": chronic_count,
        "allergy_count": allergy_count,
        "family_history_count": family_history_count,
        "long_term_med_count": long_term_med_count,
        "active_med_count": long_term_med_count,
    }


# ──────────────────────────────────────────────────────────
# M2 编辑基本信息（P1）
# ──────────────────────────────────────────────────────────


class ProfileBasicInfoUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    gender: Optional[str] = Field(None, max_length=8)
    birthday: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = Field(None, max_length=8)


@router.put("/profile/{profile_id}/basic-info")
async def update_profile_basic_info(
    profile_id: int,
    body: ProfileBasicInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id,
            HealthProfile.user_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "birthday" and v:
            try:
                from datetime import date as _date
                v = _date.fromisoformat(v)
            except ValueError:
                raise HTTPException(status_code=400, detail="生日格式无效，请使用 YYYY-MM-DD")
        setattr(profile, k, v)
    await db.flush()
    return {"message": "已保存", "profile_id": profile_id}


# ──────────────────────────────────────────────────────────
# M7 共管与权限（P1）
# ──────────────────────────────────────────────────────────


@router.get("/care-partners")
async def list_care_partners(
    profile_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FamilyManagement).where(
        FamilyManagement.user_id == current_user.id,
        FamilyManagement.status == "active",
    )
    if profile_id is not None:
        stmt = stmt.where(FamilyManagement.managed_member_id == profile_id)
    result = await db.execute(stmt)
    items = []
    for m in result.scalars().all():
        items.append({
            "id": m.id,
            "managed_member_id": m.managed_member_id,
            "name": m.caregiver_name or "",
            "relation": m.relation_type or "共管人",
            "avatar": RELATION_AVATAR_MAP.get(m.relation_type, "🧑"),
            "status": m.status,
            "can_edit": m.can_edit if hasattr(m, "can_edit") and m.can_edit is not None else True,
            "can_view": m.can_view if hasattr(m, "can_view") and m.can_view is not None else True,
        })
    return {"items": items, "total": len(items)}


class CarePartnerPermissionUpdate(BaseModel):
    can_edit: Optional[bool] = None
    can_view: Optional[bool] = None


@router.put("/care-partners/{management_id}/permissions")
async def update_care_partner_permissions(
    management_id: int,
    body: CarePartnerPermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.id == management_id,
            FamilyManagement.user_id == current_user.id,
        )
    )
    mgmt = result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="共管关系不存在")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if hasattr(mgmt, k):
            setattr(mgmt, k, v)
    await db.flush()
    return {"message": "权限已更新", "management_id": management_id}


# ──────────────────────────────────────────────────────────
# 病历卡 + OCR（M8 P0）
# ──────────────────────────────────────────────────────────


class MedicalRecordCreate(BaseModel):
    profile_id: Optional[int] = None
    image_url: Optional[str] = None
    ocr_text: Optional[str] = None
    title: Optional[str] = None
    note: Optional[str] = None
    parsed_hospital: Optional[str] = None
    parsed_department: Optional[str] = None
    parsed_diagnosis: Optional[str] = None
    parsed_visit_date: Optional[date] = None
    parsed_doctor: Optional[str] = None
    parsed_prescription: Optional[str] = None


def _ocr_parse_medical_record(ocr_text: str) -> Dict[str, Any]:
    """从 OCR 文本中提取病历卡关键字段（简化版规则提取）。"""
    text = (ocr_text or "").strip()
    if not text:
        return {}

    parsed: Dict[str, Any] = {}
    lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]

    for line in lines:
        if "医院" in line and "parsed_hospital" not in parsed:
            parsed["parsed_hospital"] = line[:64]
        if "科" in line and ("内" in line or "外" in line or "儿" in line or "妇" in line) and "parsed_department" not in parsed:
            parsed["parsed_department"] = line[:32]
        if ("诊断" in line or "印象" in line) and "parsed_diagnosis" not in parsed:
            idx = max(line.find("诊断"), line.find("印象"))
            parsed["parsed_diagnosis"] = line[idx:][:256] if idx >= 0 else line[:256]
        if ("医师" in line or "医生" in line) and "parsed_doctor" not in parsed:
            parsed["parsed_doctor"] = line[:32]
        if ("处方" in line or "用药" in line) and "parsed_prescription" not in parsed:
            parsed["parsed_prescription"] = line[:512]

    import re

    date_match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if date_match:
        try:
            from datetime import date as _date
            parsed["parsed_visit_date"] = _date(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3)),
            )
        except Exception:
            pass

    return parsed


@router.post("/medical-record")
async def create_medical_record(
    body: MedicalRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """新建病历卡（支持 OCR 文本自动解析）。

    前端调用流程：
    1. 用户拍照 / 上传图片 → 调通用 /api/ocr/recognize 获取 ocr_text + 图片 URL
    2. 调本接口，提交 ocr_text + image_url（也可提交手工编辑后的字段覆盖）
    3. 后端规则提取关键字段，落地病历卡，并自动同步一条 health_event（type=upload）
    """
    parsed = _ocr_parse_medical_record(body.ocr_text or "") if body.ocr_text else {}
    # 用户手工字段覆盖优先
    user_fields = body.model_dump(exclude_unset=True, exclude={"ocr_text", "image_url", "profile_id", "title", "note"})
    parsed.update({k: v for k, v in user_fields.items() if v is not None})

    card = MedicalRecordCard(
        user_id=current_user.id,
        profile_id=body.profile_id,
        image_url=body.image_url,
        ocr_text=body.ocr_text,
        title=body.title or (parsed.get("parsed_hospital") or "病历卡"),
        note=body.note,
        parsed_hospital=parsed.get("parsed_hospital"),
        parsed_department=parsed.get("parsed_department"),
        parsed_diagnosis=parsed.get("parsed_diagnosis"),
        parsed_visit_date=parsed.get("parsed_visit_date"),
        parsed_doctor=parsed.get("parsed_doctor"),
        parsed_prescription=parsed.get("parsed_prescription"),
        parse_status="parsed" if body.ocr_text else "pending",
    )
    db.add(card)
    await db.flush()

    # 同步到健康事件时间轴
    event = HealthEvent(
        user_id=current_user.id,
        profile_id=body.profile_id,
        event_type="upload",
        title=card.title or "病历卡",
        content=(card.parsed_diagnosis or card.note or "")[:512],
        event_date=card.parsed_visit_date or date.today(),
        tags=["病历卡"],
        extra_data={"medical_record_id": card.id, "image_url": card.image_url},
    )
    db.add(event)
    await db.flush()

    card.related_event_id = event.id
    await db.flush()

    return {
        "id": card.id,
        "event_id": event.id,
        "title": card.title,
        "parsed_hospital": card.parsed_hospital,
        "parsed_department": card.parsed_department,
        "parsed_diagnosis": card.parsed_diagnosis,
        "parsed_visit_date": card.parsed_visit_date.isoformat() if card.parsed_visit_date else None,
        "parsed_doctor": card.parsed_doctor,
        "parsed_prescription": card.parsed_prescription,
        "parse_status": card.parse_status,
        "image_url": card.image_url,
    }


@router.get("/medical-record/list")
async def list_medical_records(
    profile_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MedicalRecordCard).where(MedicalRecordCard.user_id == current_user.id)
    if profile_id is not None:
        stmt = stmt.where(MedicalRecordCard.profile_id == profile_id)
    stmt = stmt.order_by(MedicalRecordCard.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    items = []
    for c in result.scalars().all():
        items.append({
            "id": c.id,
            "title": c.title,
            "image_url": c.image_url,
            "parsed_hospital": c.parsed_hospital,
            "parsed_department": c.parsed_department,
            "parsed_diagnosis": c.parsed_diagnosis,
            "parsed_visit_date": c.parsed_visit_date.isoformat() if c.parsed_visit_date else None,
            "parsed_doctor": c.parsed_doctor,
            "parse_status": c.parse_status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"items": items, "total": len(items)}


@router.get("/medical-record/{record_id}")
async def get_medical_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicalRecordCard).where(
            MedicalRecordCard.id == record_id,
            MedicalRecordCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="病历卡不存在")
    return {
        "id": card.id,
        "title": card.title,
        "image_url": card.image_url,
        "ocr_text": card.ocr_text,
        "note": card.note,
        "parsed_hospital": card.parsed_hospital,
        "parsed_department": card.parsed_department,
        "parsed_diagnosis": card.parsed_diagnosis,
        "parsed_visit_date": card.parsed_visit_date.isoformat() if card.parsed_visit_date else None,
        "parsed_doctor": card.parsed_doctor,
        "parsed_prescription": card.parsed_prescription,
        "parse_status": card.parse_status,
        "related_event_id": card.related_event_id,
    }


@router.delete("/medical-record/{record_id}")
async def delete_medical_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicalRecordCard).where(
            MedicalRecordCard.id == record_id,
            MedicalRecordCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="病历卡不存在")
    await db.delete(card)
    await db.flush()
    return {"message": "已删除"}


# ──────────────────────────────────────────────────────────
# 主页聚合接口（健康摘要胶囊 + 设备区数据）
# ──────────────────────────────────────────────────────────


@router.get("/summary/{profile_id}")
async def get_v5_summary(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """主页 v5 聚合：健康标签胶囊摘要 + 关键基础信息。"""
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id, HealthProfile.user_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")

    info = await _get_or_create_health_info(db, profile_id)

    capsules: List[Dict[str, str]] = []
    if info.habit_smoking == "无":
        capsules.append({"icon": "🚭", "label": "不吸烟"})
    elif info.habit_smoking == "有":
        capsules.append({"icon": "🚬", "label": "吸烟"})
    if info.habit_drinking == "有":
        capsules.append({"icon": "🍷", "label": "饮酒"})
    elif info.habit_drinking == "无":
        capsules.append({"icon": "🚫", "label": "不饮酒"})
    if info.habit_exercise:
        capsules.append({"icon": "🏃", "label": f"运动:{info.habit_exercise}"})
    if info.habit_diet:
        capsules.append({"icon": "🍚", "label": info.habit_diet})

    for d in (info.drug_allergies or [])[:3]:
        capsules.append({"icon": "⚠️", "label": f"{d}过敏"})

    for cd in (info.chronic_diseases or [])[:3]:
        name = cd.get("name") if isinstance(cd, dict) else str(cd)
        if name:
            capsules.append({"icon": "🩺", "label": name})

    # [PRD-469 v2 P1] Hero 四格健康摘要指标
    chronic_count = len(info.chronic_diseases or [])
    allergy_count = (
        len(info.drug_allergies or [])
        + len(info.food_allergies or [])
        + len(info.other_allergies or [])
    )
    family_count = len(info.family_history or [])

    # 在用药品数量（[BUG-HEALTH-ARCHIVE-V2 2026-05-16] 统一口径）
    med_count = await _count_active_medications(db, current_user.id)

    hero_metrics = [
        {"label": "既往病史", "count": chronic_count, "unit": "项"},
        {"label": "过敏史", "count": allergy_count, "unit": "项"},
        {"label": "家族遗传", "count": family_count, "unit": "项"},
        {"label": "在用药品", "count": med_count, "unit": "种"},
    ]

    return {
        "profile_id": profile_id,
        "name": profile.name,
        "gender": profile.gender,
        "birthday": profile.birthday.isoformat() if profile.birthday else None,
        "height": profile.height,
        "weight": profile.weight,
        "blood_type": profile.blood_type,
        "capsules": capsules,
        "hero_metrics": hero_metrics,
    }
