"""[PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料优化 API。

主要接口：
- GET    /api/health-archive-v5/overview?member_id=  4 卡片数据 + 预警横幅
- GET    /api/health-alerts                          预警列表（双 Tab + 类型筛选）
- POST   /api/health-alerts/{id}/resolve             标记已处理（不可撤销）
- POST   /api/health-alerts/resolve-all              全部标记已处理
- POST   /api/health-alerts/_seed                    （开发/测试用）批量创建预警

就医资料：
- GET    /api/medical-records?member_id=&category=   就医资料列表/分组
- GET    /api/medical-records/{id}                   详情
- POST   /api/medical-records                        新建（多文件）
- PATCH  /api/medical-records/{id}                   编辑标题/备注
- DELETE /api/medical-records/{id}                   软删除 → 回收站
- GET    /api/medical-records/trash                  回收站列表
- POST   /api/medical-records/{id}/restore           恢复
- DELETE /api/medical-records/{id}/permanent         立即彻底删除
- POST   /api/medical-records/_purge-expired         （维护任务）30 天自动清理
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health_archive_v5 import (
    HealthAlert,
    MedicalRecord,
    MedicalRecordFile,
)
from app.models.models import FamilyMember, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Health Archive V5"])

# ─────────────────────────── 通用工具 ───────────────────────────

CATEGORIES = ("case_note", "checkup_report", "drug", "other")
CATEGORY_LABELS = {
    "case_note": "病例单",
    "checkup_report": "体检报告",
    "drug": "药物",
    "other": "其他",
}
ALERT_TYPES = ("checkup", "medication", "device", "manual")
SOURCE_LABELS = {
    "ai_checkup": "AI 体检解读",
    "ai_drug": "AI 药物识别",
    "manual": "手动上传",
}
TRASH_KEEP_DAYS = 30


def _normalize_member_id(member_id: Optional[int]) -> Optional[int]:
    """member_id 规范化：0/<=0 → None（本人）。"""
    if member_id is None or member_id <= 0:
        return None
    return member_id


def _resolve_member_label(
    db: AsyncSession, user: User, member_id: Optional[int]
) -> str:
    """同步版的占位（实际调用时上游已 await fetched，此处不实际查询）。"""
    if member_id is None:
        return "本人"
    return f"成员#{member_id}"


# ─────────────────────────── Schema ───────────────────────────


class OverviewResp(BaseModel):
    member_id: Optional[int]
    is_self: bool
    alerts_unresolved: int = 0
    medication_plan_count: int = 0
    family_member_count: int = 0
    device_count: int = 0
    medical_records_total: int = 0
    medical_records_by_category: Dict[str, int] = Field(default_factory=dict)
    trash_count: int = 0
    show_alert_banner: bool = False
    banner_text: str = ""


class AlertItem(BaseModel):
    id: int
    member_id: Optional[int]
    alert_type: str
    indicator: str
    title: str
    detail: Optional[str]
    severity: str
    source_label: Optional[str]
    advice: Optional[str]
    merged_count: int
    last_occurred_at: datetime
    status: str
    resolved_at: Optional[datetime]
    ref_record_id: Optional[int]
    ref_plan_id: Optional[int]
    ref_device_id: Optional[int]
    raw_payload: Optional[Any]


class AlertListResp(BaseModel):
    total: int
    items: List[AlertItem]


class AlertSeedReq(BaseModel):
    """开发/测试入口：批量创建预警条目。"""
    member_id: Optional[int] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)


class RecordFile(BaseModel):
    id: Optional[int] = None
    file_url: str
    file_name: str
    file_type: str = "image"
    file_size: Optional[int] = None

    # [注] file_type 校验下沉到 router 层


class MedicalRecordCreate(BaseModel):
    member_id: Optional[int] = None
    category: str
    title: str
    record_date: Optional[date] = None
    source: str = "manual"
    files: List[RecordFile] = Field(default_factory=list)
    ai_interpretation: Optional[Any] = None
    remark: Optional[str] = None

    # [注] category/source 校验改为 router 层显式检查

    # [注] 9 文件上限改为在 router 层显式校验，避免 pydantic ValidationError
    # 经过 FastAPI exception handler 时触发 JSON 序列化失败的已知问题。


class MedicalRecordPatch(BaseModel):
    title: Optional[str] = None
    remark: Optional[str] = None
    record_date: Optional[date] = None


class MedicalRecordItem(BaseModel):
    id: int
    member_id: Optional[int]
    category: str
    category_label: str
    title: str
    record_date: Optional[date]
    source: str
    source_label: str
    has_ai_interpretation: bool
    file_count: int
    thumbnail_url: Optional[str] = None
    is_deleted: bool
    days_to_purge: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MedicalRecordDetail(MedicalRecordItem):
    files: List[RecordFile] = Field(default_factory=list)
    ai_interpretation: Optional[Any] = None
    remark: Optional[str] = None


class MedicalRecordListResp(BaseModel):
    total: int
    items: List[MedicalRecordItem]
    grouped: Dict[str, int]


# ─────────────────────────── 4 卡片 overview ───────────────────────────


@router.get("/health-archive-v5/overview", response_model=OverviewResp)
async def get_overview(
    member_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = _normalize_member_id(member_id)
    is_self = mid is None

    # 1. 未处理预警数
    res = await db.execute(
        select(func.count(HealthAlert.id)).where(
            HealthAlert.user_id == current_user.id,
            HealthAlert.member_id.is_(None) if mid is None else HealthAlert.member_id == mid,
            HealthAlert.status == "open",
        )
    )
    alerts_unresolved = int(res.scalar() or 0)

    # 2. 用药计划数（有效期未结束）
    # [BUG-MED-V1 2026-05-21 Bug5/6] 修复：原代码使用了不存在的字段 is_active / consultant_id
    #   实际模型字段是 status / family_member_id；以前每次都抛 AttributeError 被吞掉，
    #   导致 medication_plan_count 永远为 0。
    medication_plan_count = 0
    try:
        from app.models.models import MedicationReminder
        today = date.today()
        cond = [
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
        ]
        if mid is None:
            cond.append(MedicationReminder.family_member_id.is_(None))
        else:
            cond.append(MedicationReminder.family_member_id == mid)
        cond.append(or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ))
        r2 = await db.execute(select(func.count(MedicationReminder.id)).where(and_(*cond)))
        medication_plan_count = int(r2.scalar() or 0)
    except Exception as e:  # noqa: BLE001
        # 异常应当不会发生；用 exception 级别便于排错
        logger.exception("[overview] medication_plan_count query failed: %s", e)

    # 3. 家庭成员数（含本人）
    family_member_count = 0
    try:
        r3 = await db.execute(
            select(func.count(FamilyMember.id)).where(FamilyMember.user_id == current_user.id)
        )
        family_member_count = int(r3.scalar() or 0)
        if family_member_count == 0:
            family_member_count = 1  # 至少本人
    except Exception:  # noqa: BLE001
        family_member_count = 1

    # 4. 设备数（绑定中）
    device_count = 0
    try:
        from app.models.devices_v2 import DeviceUserBinding
        cond_d = [DeviceUserBinding.user_id == current_user.id, DeviceUserBinding.is_active == True]  # noqa: E712
        if mid is not None:
            cond_d.append(DeviceUserBinding.member_id == mid)
        r4 = await db.execute(select(func.count(DeviceUserBinding.id)).where(and_(*cond_d)))
        device_count = int(r4.scalar() or 0)
    except Exception as e:  # noqa: BLE001
        logger.debug("[overview] device_count fallback 0: %s", e)

    # 5. 就医资料统计 + 回收站
    base = [
        MedicalRecord.user_id == current_user.id,
        MedicalRecord.member_id.is_(None) if mid is None else MedicalRecord.member_id == mid,
    ]
    res5 = await db.execute(
        select(MedicalRecord.category, func.count(MedicalRecord.id)).where(
            and_(*base, MedicalRecord.is_deleted == 0)
        ).group_by(MedicalRecord.category)
    )
    grouped: Dict[str, int] = {c: 0 for c in CATEGORIES}
    total_records = 0
    for cat, cnt in res5.all():
        grouped[cat] = int(cnt)
        total_records += int(cnt)

    res6 = await db.execute(
        select(func.count(MedicalRecord.id)).where(and_(*base, MedicalRecord.is_deleted == 1))
    )
    trash_count = int(res6.scalar() or 0)

    return OverviewResp(
        member_id=mid,
        is_self=is_self,
        alerts_unresolved=alerts_unresolved,
        medication_plan_count=medication_plan_count,
        family_member_count=family_member_count,
        device_count=device_count,
        medical_records_total=total_records,
        medical_records_by_category=grouped,
        trash_count=trash_count,
        show_alert_banner=alerts_unresolved > 0,
        banner_text=(f"您有 {alerts_unresolved} 条未处理预警，立即查看" if alerts_unresolved > 0 else ""),
    )


# ─────────────────────────── 健康预警 ───────────────────────────


def _row_to_alert(row: HealthAlert) -> AlertItem:
    return AlertItem(
        id=row.id,
        member_id=row.member_id,
        alert_type=row.alert_type,
        indicator=row.indicator,
        title=row.title,
        detail=row.detail,
        severity=row.severity,
        source_label=row.source_label,
        advice=row.advice,
        merged_count=row.merged_count,
        last_occurred_at=row.last_occurred_at,
        status=row.status,
        resolved_at=row.resolved_at,
        ref_record_id=row.ref_record_id,
        ref_plan_id=row.ref_plan_id,
        ref_device_id=row.ref_device_id,
        raw_payload=row.raw_payload,
    )


@router.get("/health-alerts", response_model=AlertListResp)
async def list_alerts(
    member_id: Optional[int] = Query(None),
    status: str = Query("open", description="open / done / all"),
    alert_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = _normalize_member_id(member_id)
    cond = [HealthAlert.user_id == current_user.id]
    cond.append(HealthAlert.member_id.is_(None) if mid is None else HealthAlert.member_id == mid)
    if status != "all":
        cond.append(HealthAlert.status == status)
    if alert_type:
        if alert_type not in ALERT_TYPES:
            raise HTTPException(status_code=400, detail=f"alert_type 必须为 {ALERT_TYPES}")
        cond.append(HealthAlert.alert_type == alert_type)
    res = await db.execute(
        select(HealthAlert).where(and_(*cond)).order_by(HealthAlert.last_occurred_at.desc())
    )
    rows = list(res.scalars().all())
    return AlertListResp(total=len(rows), items=[_row_to_alert(r) for r in rows])


@router.post("/health-alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(HealthAlert).where(
            HealthAlert.id == alert_id, HealthAlert.user_id == current_user.id
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="预警不存在")
    if row.status == "done":
        return {"ok": True, "already_done": True}
    row.status = "done"
    row.resolved_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "id": row.id}


@router.post("/health-alerts/resolve-all")
async def resolve_all_alerts(
    member_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = _normalize_member_id(member_id)
    cond = [
        HealthAlert.user_id == current_user.id,
        HealthAlert.status == "open",
    ]
    cond.append(HealthAlert.member_id.is_(None) if mid is None else HealthAlert.member_id == mid)
    await db.execute(
        update(HealthAlert)
        .where(and_(*cond))
        .values(status="done", resolved_at=datetime.utcnow())
    )
    await db.commit()
    return {"ok": True}


@router.post("/health-alerts/_seed")
async def seed_alerts(
    payload: AlertSeedReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开发/测试用：批量创建预警条目（含 24h 合并）。"""
    mid = _normalize_member_id(payload.member_id)
    created, merged = 0, 0
    now = datetime.utcnow()
    window_start = now - timedelta(hours=24)
    for raw in payload.items:
        alert_type = raw.get("alert_type") or "manual"
        indicator = raw.get("indicator") or ""
        title = raw.get("title") or ""
        if alert_type not in ALERT_TYPES:
            continue
        # 合并键：user_id + member_id + alert_type + indicator + status=open + 24h
        existing_q = await db.execute(
            select(HealthAlert).where(
                HealthAlert.user_id == current_user.id,
                HealthAlert.member_id.is_(None) if mid is None else HealthAlert.member_id == mid,
                HealthAlert.alert_type == alert_type,
                HealthAlert.indicator == indicator,
                HealthAlert.status == "open",
                HealthAlert.last_occurred_at >= window_start,
            ).order_by(HealthAlert.last_occurred_at.desc()).limit(1)
        )
        existing = existing_q.scalars().first()
        if existing:
            existing.merged_count = (existing.merged_count or 1) + 1
            existing.last_occurred_at = now
            merged += 1
            continue
        row = HealthAlert(
            user_id=current_user.id,
            member_id=mid,
            alert_type=alert_type,
            indicator=indicator,
            title=title,
            detail=raw.get("detail"),
            severity=raw.get("severity") or "medium",
            source_label=raw.get("source_label"),
            advice=raw.get("advice") or _default_advice(alert_type, indicator),
            raw_payload=raw.get("raw_payload"),
            ref_record_id=raw.get("ref_record_id"),
            ref_plan_id=raw.get("ref_plan_id"),
            ref_device_id=raw.get("ref_device_id"),
        )
        db.add(row)
        created += 1
    await db.commit()
    return {"ok": True, "created": created, "merged": merged}


def _default_advice(alert_type: str, indicator: str) -> str:
    if alert_type == "checkup":
        return f"建议关注「{indicator}」相关指标，必要时咨询医生。"
    if alert_type == "medication":
        return "请按时服药，连续漏服或发现冲突请及时联系医生。"
    if alert_type == "device":
        return f"「{indicator}」检测异常，建议重测或咨询医生。"
    return "请关注此项异常，必要时上传完整资料让 AI 进一步解读。"


# ─────────────────────────── 就医资料 ───────────────────────────


def _to_record_item(row: MedicalRecord, file_count: int, thumb: Optional[str]) -> MedicalRecordItem:
    days_to_purge: Optional[int] = None
    if row.is_deleted and row.deleted_at is not None:
        deadline = row.deleted_at + timedelta(days=TRASH_KEEP_DAYS)
        days_to_purge = max((deadline - datetime.utcnow()).days, 0)
    return MedicalRecordItem(
        id=row.id,
        member_id=row.member_id,
        category=row.category,
        category_label=CATEGORY_LABELS.get(row.category, row.category),
        title=row.title,
        record_date=row.record_date,
        source=row.source,
        source_label=SOURCE_LABELS.get(row.source, "手动上传"),
        has_ai_interpretation=bool(row.ai_interpretation),
        file_count=file_count,
        thumbnail_url=thumb,
        is_deleted=bool(row.is_deleted),
        days_to_purge=days_to_purge,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load_files_map(
    db: AsyncSession, record_ids: List[int]
) -> Dict[int, List[MedicalRecordFile]]:
    if not record_ids:
        return {}
    res = await db.execute(
        select(MedicalRecordFile).where(MedicalRecordFile.record_id.in_(record_ids))
        .order_by(MedicalRecordFile.record_id, MedicalRecordFile.sort_order, MedicalRecordFile.id)
    )
    out: Dict[int, List[MedicalRecordFile]] = {}
    for f in res.scalars().all():
        out.setdefault(f.record_id, []).append(f)
    return out


@router.get("/medical-records", response_model=MedicalRecordListResp)
async def list_records(
    member_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = _normalize_member_id(member_id)
    cond = [
        MedicalRecord.user_id == current_user.id,
        MedicalRecord.is_deleted == 0,
    ]
    cond.append(MedicalRecord.member_id.is_(None) if mid is None else MedicalRecord.member_id == mid)
    if category:
        if category not in CATEGORIES:
            raise HTTPException(status_code=400, detail=f"category 必须是 {CATEGORIES}")
        cond.append(MedicalRecord.category == category)

    res = await db.execute(
        select(MedicalRecord).where(and_(*cond)).order_by(MedicalRecord.created_at.desc())
    )
    rows = list(res.scalars().all())

    files_map = await _load_files_map(db, [r.id for r in rows])
    items: List[MedicalRecordItem] = []
    for r in rows:
        flist = files_map.get(r.id, [])
        thumb: Optional[str] = None
        for f in flist:
            if f.file_type == "image":
                thumb = f.file_url
                break
        items.append(_to_record_item(r, len(flist), thumb))

    grouped: Dict[str, int] = {c: 0 for c in CATEGORIES}
    for it in items:
        grouped[it.category] = grouped.get(it.category, 0) + 1

    return MedicalRecordListResp(total=len(items), items=items, grouped=grouped)


@router.get("/medical-records/trash")
async def list_trash(
    member_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = _normalize_member_id(member_id)
    cond = [
        MedicalRecord.user_id == current_user.id,
        MedicalRecord.is_deleted == 1,
    ]
    cond.append(MedicalRecord.member_id.is_(None) if mid is None else MedicalRecord.member_id == mid)
    res = await db.execute(
        select(MedicalRecord).where(and_(*cond)).order_by(MedicalRecord.deleted_at.desc())
    )
    rows = list(res.scalars().all())
    files_map = await _load_files_map(db, [r.id for r in rows])
    items = []
    for r in rows:
        flist = files_map.get(r.id, [])
        thumb = next((f.file_url for f in flist if f.file_type == "image"), None)
        items.append(_to_record_item(r, len(flist), thumb))
    return {"total": len(items), "items": [it.dict() for it in items]}


@router.get("/medical-records/{record_id}", response_model=MedicalRecordDetail)
async def get_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.user_id == current_user.id,
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    files_map = await _load_files_map(db, [row.id])
    flist = files_map.get(row.id, [])
    thumb = next((f.file_url for f in flist if f.file_type == "image"), None)
    base = _to_record_item(row, len(flist), thumb)
    return MedicalRecordDetail(
        **base.dict(),
        files=[
            RecordFile(
                id=f.id,
                file_url=f.file_url,
                file_name=f.file_name,
                file_type=f.file_type,
                file_size=f.file_size,
            )
            for f in flist
        ],
        ai_interpretation=row.ai_interpretation,
        remark=row.remark,
    )


@router.post("/medical-records", response_model=MedicalRecordDetail)
async def create_record(
    payload: MedicalRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(payload.files) > 9:
        raise HTTPException(status_code=400, detail="一份资料最多 9 个文件")
    if payload.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category 必须是 {CATEGORIES}")
    if payload.source not in SOURCE_LABELS:
        raise HTTPException(status_code=400, detail=f"source 必须是 {tuple(SOURCE_LABELS.keys())}")
    for f in payload.files:
        if f.file_type not in ("image", "pdf"):
            raise HTTPException(status_code=400, detail="file_type 必须为 image / pdf")
    mid = _normalize_member_id(payload.member_id)
    row = MedicalRecord(
        user_id=current_user.id,
        member_id=mid,
        category=payload.category,
        title=payload.title.strip(),
        record_date=payload.record_date,
        source=payload.source,
        ai_interpretation=payload.ai_interpretation,
        remark=payload.remark,
    )
    db.add(row)
    await db.flush()
    for idx, f in enumerate(payload.files):
        if not f.file_url:
            continue
        db.add(
            MedicalRecordFile(
                record_id=row.id,
                file_url=f.file_url,
                file_name=f.file_name or f"file_{idx + 1}",
                file_type=f.file_type,
                file_size=f.file_size,
                sort_order=idx,
            )
        )
    await db.commit()
    return await get_record(row.id, db, current_user)


@router.patch("/medical-records/{record_id}", response_model=MedicalRecordDetail)
async def patch_record(
    record_id: int,
    payload: MedicalRecordPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.user_id == current_user.id,
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.remark is not None:
        row.remark = payload.remark
    if payload.record_date is not None:
        row.record_date = payload.record_date
    await db.commit()
    return await get_record(record_id, db, current_user)


@router.delete("/medical-records/{record_id}")
async def soft_delete_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.user_id == current_user.id,
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    if row.is_deleted:
        return {"ok": True, "already_deleted": True}
    row.is_deleted = 1
    row.deleted_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "id": row.id, "purge_after_days": TRASH_KEEP_DAYS}


@router.post("/medical-records/{record_id}/restore", response_model=MedicalRecordDetail)
async def restore_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.user_id == current_user.id,
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    row.is_deleted = 0
    row.deleted_at = None
    await db.commit()
    return await get_record(record_id, db, current_user)


@router.delete("/medical-records/{record_id}/permanent")
async def permanent_delete_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.user_id == current_user.id,
        )
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="资料不存在")
    # 物理删除文件 + 主表
    await db.execute(
        MedicalRecordFile.__table__.delete().where(MedicalRecordFile.record_id == row.id)
    )
    await db.execute(MedicalRecord.__table__.delete().where(MedicalRecord.id == row.id))
    await db.commit()
    return {"ok": True, "id": record_id}


@router.post("/medical-records/_purge-expired")
async def purge_expired(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """到期 30 天的回收站物理清理（任何登录用户可调用，仅清理自己的）。"""
    deadline = datetime.utcnow() - timedelta(days=TRASH_KEEP_DAYS)
    res = await db.execute(
        select(MedicalRecord.id).where(
            MedicalRecord.user_id == current_user.id,
            MedicalRecord.is_deleted == 1,
            MedicalRecord.deleted_at != None,  # noqa: E711
            MedicalRecord.deleted_at <= deadline,
        )
    )
    ids = [r[0] for r in res.all()]
    if ids:
        await db.execute(
            MedicalRecordFile.__table__.delete().where(MedicalRecordFile.record_id.in_(ids))
        )
        await db.execute(MedicalRecord.__table__.delete().where(MedicalRecord.id.in_(ids)))
        await db.commit()
    return {"ok": True, "purged": len(ids)}
