import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    AllergyRecord,
    CheckupIndicator,
    CheckupReport,
    FamilyMedicalHistory,
    FamilyMember,
    HealthProfile,
    MedicalHistory,
    MedicationRecord,
    User,
    VisitRecord,
)
from app.schemas.health import (
    AllergyCreate,
    AllergyResponse,
    CheckupReportResponse,
    HealthProfileCreate,
    HealthProfileResponse,
    HealthProfileUpdate,
    MedicalHistoryCreate,
    MedicalHistoryResponse,
    MedicationCreate,
    MedicationResponse,
    VisitRecordCreate,
    VisitRecordResponse,
)
from app.schemas.health_v2 import (
    HealthProfileV2Response,
    HealthProfileV2Update,
)
from app.services.ai_service import analyze_checkup_report
from app.utils.cos_helper import try_cos_upload

router = APIRouter(prefix="/api/health", tags=["健康档案"])


# ── 健康档案 ──

@router.get("/profile", response_model=HealthProfileResponse)
async def get_health_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == 0,
        )
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")
    return HealthProfileResponse.model_validate(profile)


@router.post("/profile", response_model=HealthProfileResponse)
async def create_health_profile(
    data: HealthProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == 0,
        )
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="健康档案已存在，请使用更新接口")

    create_data = data.model_dump(exclude_unset=True)
    create_data.pop("family_member_id", None)
    profile = HealthProfile(user_id=current_user.id, family_member_id=0, **create_data)
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    try:
        from app.services.checkin_points_service import award_complete_profile_points
        await award_complete_profile_points(db, current_user, profile)
        await db.flush()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"完善健康档案积分发放异常: {e}")

    return HealthProfileResponse.model_validate(profile)


@router.put("/profile", response_model=HealthProfileResponse)
async def update_health_profile(
    data: HealthProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == 0,
        )
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在，请联系客服")

    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("family_member_id", None)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now()
    await db.flush()
    await db.refresh(profile)

    try:
        from app.services.checkin_points_service import award_complete_profile_points
        await award_complete_profile_points(db, current_user, profile)
        await db.flush()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"完善健康档案积分发放异常: {e}")

    return HealthProfileResponse.model_validate(profile)


@router.get("/profile/member/{member_id}", response_model=HealthProfileV2Response)
async def get_member_health_profile(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取家庭成员的 HealthProfile。

    [Bug-2] 修复：当管理方查看被守护人档案时，应用被守护人的 user_id 查询 profile，
    而非管理方自己的 user_id。确保「本人 Tab」的数据合并后能正确展示。
    """
    # [PRD-FAMILY-V3-EMERGENCY-FIX 2026-06-03]
    # 对齐家人 Tab 的过滤口径，仅排除已软删除成员。
    # unbound 成员（已解绑/未绑定）应在列表中可见，可重新发起邀请。
    # V3 升级后统一使用 deleted，不再兼容 removed。
    from app.services.family_status_constants import DELETED_STATUSES
    member_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
            FamilyMember.status.notin_(DELETED_STATUSES),
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    # [Bug-2] 确定 profile 所属的 user_id：
    # - 如果 member.member_user_id 存在且与 current_user 不同（即该成员代表另一个真实用户），
    #   使用 member.member_user_id（被守护人的 user_id）
    # - 否则使用 current_user.id（成员主人即当前用户）
    profile_user_id = current_user.id
    if member.member_user_id and member.member_user_id != current_user.id:
        profile_user_id = member.member_user_id

    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == profile_user_id,
            HealthProfile.family_member_id == member_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = HealthProfile(
            user_id=profile_user_id,
            family_member_id=member_id,
            name=member.nickname,
            gender=member.gender,
            birthday=member.birthday,
            height=member.height,
            weight=member.weight,
            medical_histories=member.medical_histories,
            allergies=member.allergies,
        )
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return HealthProfileV2Response.model_validate(profile)


@router.put("/profile/member/{member_id}", response_model=HealthProfileV2Response)
async def upsert_member_health_profile(
    member_id: int,
    data: HealthProfileV2Update,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新家庭成员的 HealthProfile。

    [Bug-2] 修复：与 GET 对称，当管理方修改被守护人档案时使用被守护人的 user_id。
    """
    # [PRD-FAMILY-V3-EMERGENCY-FIX 2026-06-03] 同 GET /profile/member/{member_id}，仅排除已软删除成员
    from app.services.family_status_constants import DELETED_STATUSES
    member_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
            FamilyMember.status.notin_(DELETED_STATUSES),
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    # [Bug-2] 确定 profile 所属的 user_id
    profile_user_id = current_user.id
    if member.member_user_id and member.member_user_id != current_user.id:
        profile_user_id = member.member_user_id

    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == profile_user_id,
            HealthProfile.family_member_id == member_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = HealthProfile(user_id=profile_user_id, family_member_id=member_id)
        db.add(profile)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now()

    if any(k in update_data for k in ("name", "gender", "birthday")):
        if "name" in update_data:
            member.nickname = update_data["name"]
        if "gender" in update_data:
            member.gender = update_data["gender"]
        if "birthday" in update_data:
            member.birthday = update_data["birthday"]

    await db.flush()
    await db.refresh(profile)
    return HealthProfileV2Response.model_validate(profile)


# ── 过敏记录 ──

@router.get("/allergies")
async def list_allergies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(AllergyRecord.id)).where(AllergyRecord.user_id == current_user.id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(AllergyRecord)
        .where(AllergyRecord.user_id == current_user.id)
        .order_by(AllergyRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [AllergyResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/allergies", response_model=AllergyResponse)
async def create_allergy(
    data: AllergyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = AllergyRecord(user_id=current_user.id, **data.model_dump())
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return AllergyResponse.model_validate(record)


@router.delete("/allergies/{allergy_id}")
async def delete_allergy(
    allergy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AllergyRecord).where(AllergyRecord.id == allergy_id, AllergyRecord.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(record)
    return {"message": "删除成功"}


# ── 病史记录 ──

@router.get("/medical-history")
async def list_medical_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(MedicalHistory.id)).where(MedicalHistory.user_id == current_user.id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(MedicalHistory)
        .where(MedicalHistory.user_id == current_user.id)
        .order_by(MedicalHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [MedicalHistoryResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/medical-history", response_model=MedicalHistoryResponse)
async def create_medical_history(
    data: MedicalHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = MedicalHistory(user_id=current_user.id, **data.model_dump())
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return MedicalHistoryResponse.model_validate(record)


@router.delete("/medical-history/{record_id}")
async def delete_medical_history(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicalHistory).where(MedicalHistory.id == record_id, MedicalHistory.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(record)
    return {"message": "删除成功"}


# ── 用药记录 ──

@router.get("/medications")
async def list_medications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(MedicationRecord.id)).where(MedicationRecord.user_id == current_user.id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(MedicationRecord)
        .where(MedicationRecord.user_id == current_user.id)
        .order_by(MedicationRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [MedicationResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/medications", response_model=MedicationResponse)
async def create_medication(
    data: MedicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = MedicationRecord(user_id=current_user.id, **data.model_dump())
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return MedicationResponse.model_validate(record)


@router.delete("/medications/{record_id}")
async def delete_medication(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationRecord).where(MedicationRecord.id == record_id, MedicationRecord.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(record)
    return {"message": "删除成功"}


# ── 就诊记录 ──

@router.get("/visits")
async def list_visits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(VisitRecord.id)).where(VisitRecord.user_id == current_user.id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(VisitRecord)
        .where(VisitRecord.user_id == current_user.id)
        .order_by(VisitRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [VisitRecordResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/visits", response_model=VisitRecordResponse)
async def create_visit(
    data: VisitRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = VisitRecord(user_id=current_user.id, **data.model_dump())
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return VisitRecordResponse.model_validate(record)


@router.delete("/visits/{record_id}")
async def delete_visit(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VisitRecord).where(VisitRecord.id == record_id, VisitRecord.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(record)
    return {"message": "删除成功"}


# ── 体检报告 ──

@router.get("/checkup-reports")
async def list_checkup_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(CheckupReport.id)).where(CheckupReport.user_id == current_user.id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(CheckupReport)
        .where(CheckupReport.user_id == current_user.id)
        .order_by(CheckupReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CheckupReportResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/checkup-reports/{report_id}", response_model=CheckupReportResponse)
async def get_checkup_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CheckupReport).where(CheckupReport.id == report_id, CheckupReport.user_id == current_user.id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return CheckupReportResponse.model_validate(report)


@router.post("/checkup-reports", response_model=CheckupReportResponse)
async def upload_checkup_report(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()

    cos_url = await try_cos_upload(db, content, file.filename or "file", file.content_type, "checkup/")
    if cos_url:
        file_url = cos_url
    else:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "file")[1]
        filename = f"checkup_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        file_url = f"/uploads/{filename}"

    ocr_text = "体检报告OCR文本提取结果（实际环境中接入OCR服务）"

    profile_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == 0,
        )
    )
    profile = profile_result.scalars().first()
    user_profile = None
    if profile:
        user_profile = {
            "gender": profile.gender,
            "birthday": str(profile.birthday) if profile.birthday else None,
            "height": profile.height,
            "weight": profile.weight,
        }

    ai_analysis = await analyze_checkup_report(ocr_text, user_profile, db)

    report = CheckupReport(
        user_id=current_user.id,
        report_date=datetime.now().date(),
        report_type="general",
        file_url=file_url,
        ocr_result={"text": ocr_text},
        ai_analysis=ai_analysis,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return CheckupReportResponse.model_validate(report)
