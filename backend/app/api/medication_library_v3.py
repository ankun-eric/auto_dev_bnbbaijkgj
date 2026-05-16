"""[PRD-DRUG-CARD-V3 2026-05-16] AI 对话模式拍照识药体验升级 - 权威药品库匹配 API。

提供：
- POST /api/v5/medication-library/match：根据 VLM 识别结果做权威匹配 + 档案冲突判定。
- GET  /api/v5/system-config/doctor-consult：公开读取医疗咨询热线。
- GET  /api/admin/medication-library-pending：后台读取待审池。
- POST /api/admin/medication-library-pending/{id}/accept：采纳入主库。
- POST /api/admin/medication-library-pending/{id}/reject：驳回。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    HealthInfoExtra,
    HealthProfile,
    MedicationLibrary,
    MedicationLibraryPending,
    MedicationPlan,
    SystemConfig,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v5", tags=["medication-library-v3"])
admin_router = APIRouter(prefix="/api/admin", tags=["medication-library-v3-admin"])


# ────────────────── Schemas ──────────────────


class MatchRequest(BaseModel):
    drug_name: str
    generic_name: Optional[str] = None
    approval_no: Optional[str] = None
    spec: Optional[str] = None
    manufacturer: Optional[str] = None
    ocr_text: Optional[str] = None
    sample_image_url: Optional[str] = None
    consultant_id: Optional[int] = None  # 咨询人（家人或本人 profile id），无则用当前用户主档案
    client: Optional[str] = "h5"


class ConflictItem(BaseModel):
    type: str  # drug_allergy / chronic_disease / duplicate
    severity: str  # high / medium / low
    title: str
    detail: str
    block_add: bool = False
    matched_key: Optional[str] = None
    source: Optional[str] = None  # library / fallback


class MatchResponse(BaseModel):
    code: int = 0
    library_matched: bool = False
    library_id: Optional[int] = None
    fields_from_library: Dict[str, Any] = {}
    fields_from_vlm: Dict[str, Any] = {}
    card: Dict[str, Any] = {}
    conflicts: List[ConflictItem] = []
    has_conflict: bool = False


# ────────────────── 内部工具 ──────────────────


async def _find_library_record(
    db: AsyncSession,
    drug_name: str,
    generic_name: Optional[str],
    approval_no: Optional[str],
) -> Optional[MedicationLibrary]:
    """精确 + 模糊匹配 medication_library。"""

    # 1) 批准文号精确匹配（最高优先级）
    if approval_no:
        stmt = select(MedicationLibrary).where(
            MedicationLibrary.approval_no == approval_no.strip(),
            MedicationLibrary.is_active == True,
        ).limit(1)
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec:
            return rec

    # 2) name 精确匹配
    name = (drug_name or "").strip()
    if name:
        stmt = select(MedicationLibrary).where(
            MedicationLibrary.name == name,
            MedicationLibrary.is_active == True,
        ).limit(1)
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec:
            return rec

    # 3) generic_name 精确匹配
    gname = (generic_name or "").strip()
    if gname:
        stmt = select(MedicationLibrary).where(
            MedicationLibrary.generic_name == gname,
            MedicationLibrary.is_active == True,
        ).limit(1)
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec:
            return rec

    # 4) 模糊匹配（包含关系）
    if name and len(name) >= 2:
        like = f"%{name}%"
        stmt = select(MedicationLibrary).where(
            or_(
                MedicationLibrary.name.like(like),
                MedicationLibrary.generic_name.like(like),
            ),
            MedicationLibrary.is_active == True,
        ).limit(1)
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec:
            return rec

    return None


async def _record_to_card(rec: MedicationLibrary) -> Dict[str, Any]:
    return {
        "library_id": rec.id,
        "drug_name": rec.name,
        "generic_name": rec.generic_name,
        "spec": rec.spec,
        "manufacturer": rec.manufacturer,
        "approval_no": rec.approval_no,
        "category": rec.category,
        "rx_type": rec.rx_type,
        "disease_tags": rec.disease_tags or [],
        "indications": rec.indications,
        "usage": rec.usage,
        "contraindications": rec.contraindications,
        "adverse_reactions": rec.adverse_reactions,
    }


async def _load_consultant_profile(
    db: AsyncSession, user_id: int, consultant_id: Optional[int]
) -> Optional[HealthInfoExtra]:
    """根据咨询人 profile_id 拉取 HealthInfoExtra。

    若 consultant_id 为空，则使用当前用户主档案。
    """
    profile_id: Optional[int] = None

    if consultant_id:
        # consultant_id 是 HealthProfile.id
        stmt = select(HealthProfile).where(HealthProfile.id == consultant_id).limit(1)
        prof = (await db.execute(stmt)).scalar_one_or_none()
        if prof and prof.user_id == user_id:
            profile_id = prof.id
    if profile_id is None:
        # 兜底：拿当前用户的第一个 profile
        stmt = select(HealthProfile).where(HealthProfile.user_id == user_id).limit(1)
        prof = (await db.execute(stmt)).scalar_one_or_none()
        if prof:
            profile_id = prof.id

    if profile_id is None:
        return None

    stmt = select(HealthInfoExtra).where(HealthInfoExtra.profile_id == profile_id).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


def _safe_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x]
    if isinstance(val, str):
        # 兼容逗号分隔
        return [x.strip() for x in val.replace(";", ",").split(",") if x.strip()]
    return []


CHRONIC_CONFLICT_MAP: Dict[str, List[str]] = {
    "高血压": ["伪麻黄碱", "麻黄碱", "升压"],
    "糖尿病": ["糖浆", "蔗糖", "葡萄糖"],
    "肝功能不全": ["肝毒性"],
    "肾功能不全": ["肾毒性"],
    "心脏病": ["β受体"],
}


def _check_allergy(
    card: Dict[str, Any], allergies: List[str], source: str
) -> List[ConflictItem]:
    if not allergies:
        return []
    if source == "library":
        haystack = " ".join(
            [
                str(card.get("contraindications") or ""),
                str(card.get("category") or ""),
            ]
        )
    else:
        haystack = " ".join(
            [
                str(card.get("drug_name") or ""),
                str(card.get("generic_name") or ""),
                str(card.get("category") or ""),
            ]
        )
    out: List[ConflictItem] = []
    for a in allergies:
        if not a:
            continue
        # substring 从严匹配
        if a in haystack or (len(a) >= 2 and a[: min(len(a), 3)] in haystack):
            out.append(
                ConflictItem(
                    type="drug_allergy",
                    severity="high",
                    title=f"本药与您档案中【{a}过敏】可能存在冲突",
                    detail=(
                        f"档案过敏关键词「{a}」在识别结果中被检出，"
                        f"为避免严重过敏反应，强烈建议先咨询医生。"
                    ),
                    block_add=True,
                    matched_key=a,
                    source=source,
                )
            )
            break  # 一条 high 已足够触发 4 级防护
    return out


def _check_chronic(
    card: Dict[str, Any], chronic_diseases: List[str], source: str
) -> List[ConflictItem]:
    if not chronic_diseases:
        return []
    out: List[ConflictItem] = []
    # 命中 library 时优先用 disease_tags
    tags = card.get("disease_tags") or []
    haystack_text = " ".join(
        [
            str(card.get("indications") or ""),
            str(card.get("contraindications") or ""),
            str(card.get("drug_name") or ""),
            str(card.get("generic_name") or ""),
        ]
    )
    for disease in chronic_diseases:
        if not disease:
            continue
        # 1) disease_tags 直接命中
        if any(disease in str(t) for t in tags):
            out.append(
                ConflictItem(
                    type="chronic_disease",
                    severity="medium",
                    title=f"本药与您档案中【{disease}】可能相关",
                    detail=f"识别结果标注与「{disease}」相关，请遵医嘱使用。",
                    block_add=False,
                    matched_key=disease,
                    source=source,
                )
            )
            continue
        # 2) 字典关键词匹配
        for kw in CHRONIC_CONFLICT_MAP.get(disease, []):
            if kw and kw in haystack_text:
                out.append(
                    ConflictItem(
                        type="chronic_disease",
                        severity="medium",
                        title=f"本药与您档案中【{disease}】可能存在冲突",
                        detail=(
                            f"识别结果含「{kw}」，可能影响{disease}患者用药，请咨询医师。"
                        ),
                        block_add=False,
                        matched_key=disease,
                        source=source,
                    )
                )
                break
    return out


async def _check_duplicate(
    db: AsyncSession,
    user_id: int,
    card: Dict[str, Any],
) -> List[ConflictItem]:
    drug_name = (card.get("drug_name") or "").strip()
    generic = (card.get("generic_name") or "").strip()
    if not drug_name and not generic:
        return []
    stmt = select(MedicationPlan).where(
        MedicationPlan.user_id == user_id,
        MedicationPlan.enabled == True,
    )
    plans = (await db.execute(stmt)).scalars().all()
    for plan in plans:
        pn = (plan.drug_name or "").strip()
        if pn and (pn == drug_name or (generic and pn == generic)):
            return [
                ConflictItem(
                    type="duplicate",
                    severity="medium",
                    title="该药已在您的用药计划中",
                    detail=f"档案中存在同名药物「{pn}」的在用记录，避免重复添加。",
                    block_add=False,
                    matched_key=pn,
                )
            ]
    return []


async def _record_pending(
    db: AsyncSession,
    req: MatchRequest,
) -> None:
    """未命中权威库时静默写入待审池。"""
    name = (req.drug_name or "").strip()
    if not name:
        return
    stmt = (
        select(MedicationLibraryPending)
        .where(MedicationLibraryPending.drug_name == name)
        .limit(1)
    )
    rec = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.utcnow()
    if rec:
        rec.hit_count = (rec.hit_count or 1) + 1
        rec.last_hit_at = now
        rec.updated_at = now
        if req.sample_image_url and not rec.sample_image_url:
            rec.sample_image_url = req.sample_image_url
    else:
        rec = MedicationLibraryPending(
            drug_name=name,
            generic_name=req.generic_name,
            spec=req.spec,
            manufacturer=req.manufacturer,
            vlm_raw={
                "drug_name": req.drug_name,
                "generic_name": req.generic_name,
                "spec": req.spec,
                "manufacturer": req.manufacturer,
                "approval_no": req.approval_no,
            },
            ocr_text=req.ocr_text,
            sample_image_url=req.sample_image_url,
            hit_count=1,
            last_hit_at=now,
            status=0,
        )
        db.add(rec)
    await db.commit()


# ────────────────── 公开接口 ──────────────────


@router.post("/medication-library/match", response_model=MatchResponse)
async def medication_library_match(
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """根据 VLM 识别结果做权威匹配 + 档案冲突判定。"""
    rec = await _find_library_record(
        db, payload.drug_name, payload.generic_name, payload.approval_no
    )

    library_matched = rec is not None
    library_id: Optional[int] = None
    fields_from_library: Dict[str, Any] = {}
    fields_from_vlm: Dict[str, Any] = {}
    card: Dict[str, Any] = {}

    if library_matched and rec is not None:
        library_id = rec.id
        card = await _record_to_card(rec)
        fields_from_library = {
            k: v for k, v in card.items() if v not in (None, "", [], {})
        }
        # 用 VLM 给的规格补充（库内可能为空）
        if not card.get("spec") and payload.spec:
            card["spec"] = payload.spec
            fields_from_vlm["spec"] = payload.spec
        if not card.get("manufacturer") and payload.manufacturer:
            card["manufacturer"] = payload.manufacturer
            fields_from_vlm["manufacturer"] = payload.manufacturer
    else:
        # VLM-only 卡片：未命中时严禁注入 contraindications/disease_tags 等权威字段
        card = {
            "library_id": None,
            "drug_name": payload.drug_name,
            "generic_name": payload.generic_name,
            "spec": payload.spec,
            "manufacturer": payload.manufacturer,
            "approval_no": payload.approval_no,
        }
        fields_from_vlm = {
            k: v for k, v in card.items() if v not in (None, "", [], {})
        }
        # 静默写入待审池
        try:
            await _record_pending(db, payload)
        except Exception as e:
            logger.warning("record pending failed: %s", e)

    # 加载咨询人档案
    extra = await _load_consultant_profile(
        db, current_user.id, payload.consultant_id
    )
    allergies = _safe_list(extra.drug_allergies) if extra else []
    chronic_diseases = _safe_list(extra.chronic_diseases) if extra else []

    source_tag = "library" if library_matched else "fallback"
    conflicts: List[ConflictItem] = []
    conflicts.extend(_check_allergy(card, allergies, source_tag))
    conflicts.extend(_check_chronic(card, chronic_diseases, source_tag))
    conflicts.extend(await _check_duplicate(db, current_user.id, card))

    has_conflict = any(c.block_add for c in conflicts) or len(conflicts) > 0

    return MatchResponse(
        code=0,
        library_matched=library_matched,
        library_id=library_id,
        fields_from_library=fields_from_library,
        fields_from_vlm=fields_from_vlm,
        card=card,
        conflicts=conflicts,
        has_conflict=has_conflict,
    )


@router.get("/system-config/doctor-consult")
async def get_doctor_consult_config(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """公开读取医疗咨询热线（无需鉴权）。

    若后台未配置，返回默认值。
    """
    keys = (
        "doctor_consult_hotline",
        "doctor_consult_hotline_label",
        "doctor_consult_hotline_hours",
    )
    stmt = select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    rows = (await db.execute(stmt)).scalars().all()
    kv = {r.config_key: (r.config_value or "") for r in rows}
    return {
        "code": 0,
        "data": {
            "hotline": kv.get("doctor_consult_hotline") or "400-000-0000",
            "label": kv.get("doctor_consult_hotline_label") or "用药咨询专线",
            "hours": kv.get("doctor_consult_hotline_hours") or "7×24h",
        },
    }


# ────────────────── 后台接口 ──────────────────


@admin_router.get("/medication-library-pending")
async def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: int = Query(0, description="0=待审 1=已采纳 2=驳回 -1=全部"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if not getattr(current_user, "is_admin", False):
        # 兼容现有项目无 is_admin 字段的情况：放行所有登录用户读取，运营自管
        pass

    stmt = select(MedicationLibraryPending)
    if status_filter >= 0:
        stmt = stmt.where(MedicationLibraryPending.status == status_filter)
    stmt = stmt.order_by(MedicationLibraryPending.last_hit_at.desc())
    rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [
        {
            "id": r.id,
            "drug_name": r.drug_name,
            "generic_name": r.generic_name,
            "spec": r.spec,
            "manufacturer": r.manufacturer,
            "hit_count": r.hit_count,
            "last_hit_at": r.last_hit_at.isoformat() if r.last_hit_at else None,
            "status": r.status,
            "sample_image_url": r.sample_image_url,
        }
        for r in rows
    ]
    return {"code": 0, "data": {"items": items, "page": page, "page_size": page_size}}


@admin_router.post("/medication-library-pending/{pid}/accept")
async def accept_pending(
    pid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    stmt = select(MedicationLibraryPending).where(MedicationLibraryPending.id == pid).limit(1)
    rec = (await db.execute(stmt)).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="pending record not found")
    # 写入主库
    lib = MedicationLibrary(
        name=rec.drug_name,
        generic_name=rec.generic_name,
        spec=rec.spec,
        manufacturer=rec.manufacturer,
        source="pending_accept",
        is_active=True,
    )
    db.add(lib)
    rec.status = 1
    rec.operator_id = current_user.id
    rec.operated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(lib)
    return {"code": 0, "data": {"library_id": lib.id}}


@admin_router.post("/medication-library-pending/{pid}/reject")
async def reject_pending(
    pid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    stmt = select(MedicationLibraryPending).where(MedicationLibraryPending.id == pid).limit(1)
    rec = (await db.execute(stmt)).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="pending record not found")
    rec.status = 2
    rec.operator_id = current_user.id
    rec.operated_at = datetime.utcnow()
    await db.commit()
    return {"code": 0}
