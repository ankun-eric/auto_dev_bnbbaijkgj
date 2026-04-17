from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ChatMessage,
    ChatSession,
    ConstitutionAnswer,
    ConstitutionQuestion,
    HealthProfile,
    MessageRole,
    SessionType,
    TCMDiagnosis,
    User,
)
from app.schemas.tcm import (
    ConstitutionQuestionResponse,
    ConstitutionTestRequest,
    TCMDiagnosisCreate,
    TCMDiagnosisListResponse,
    TCMDiagnosisResponse,
)
from app.services.ai_service import tcm_analysis

router = APIRouter(prefix="/api/tcm", tags=["中医辨证"])


@router.post("/diagnosis", response_model=TCMDiagnosisResponse)
async def create_diagnosis(
    data: TCMDiagnosisCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tongue_desc = None
    face_desc = None
    if data.tongue_image_url:
        tongue_desc = "舌象图片已上传，等待AI分析"
    if data.face_image_url:
        face_desc = "面部图片已上传，等待AI分析"

    ai_result = await tcm_analysis(tongue_desc, face_desc, None, db)

    diagnosis = TCMDiagnosis(
        user_id=current_user.id,
        tongue_image_url=data.tongue_image_url,
        face_image_url=data.face_image_url,
        constitution_type=ai_result.get("constitution_type", ""),
        tongue_analysis=ai_result.get("tongue_analysis", ""),
        face_analysis=ai_result.get("face_analysis", ""),
        syndrome_analysis=ai_result.get("syndrome_analysis", ""),
        health_plan=ai_result.get("health_plan", ""),
        family_member_id=data.family_member_id,
        constitution_description=ai_result.get("constitution_type", ""),
        advice_summary=ai_result.get("health_plan", "")[:1000] if ai_result.get("health_plan") else None,
    )
    db.add(diagnosis)
    await db.flush()
    await db.refresh(diagnosis)
    return TCMDiagnosisResponse.model_validate(diagnosis)


@router.get("/diagnosis/{diagnosis_id}", response_model=TCMDiagnosisResponse)
async def get_diagnosis(
    diagnosis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TCMDiagnosis).where(TCMDiagnosis.id == diagnosis_id, TCMDiagnosis.user_id == current_user.id)
    )
    diagnosis = result.scalar_one_or_none()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="诊断记录不存在")
    return TCMDiagnosisResponse.model_validate(diagnosis)


@router.get("/diagnosis")
async def list_diagnoses(
    constitution_type: Optional[str] = None,
    family_member_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = [TCMDiagnosis.user_id == current_user.id]
    if constitution_type:
        base_filter.append(TCMDiagnosis.constitution_type == constitution_type)
    if family_member_id is not None:
        base_filter.append(TCMDiagnosis.family_member_id == family_member_id)

    total_result = await db.execute(select(func.count(TCMDiagnosis.id)).where(*base_filter))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(TCMDiagnosis)
        .where(*base_filter)
        .order_by(TCMDiagnosis.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [TCMDiagnosisListResponse.model_validate(d) for d in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/questions")
async def list_questions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConstitutionQuestion).order_by(ConstitutionQuestion.order_num.asc()))
    items = [ConstitutionQuestionResponse.model_validate(q) for q in result.scalars().all()]
    return {"items": items}


@router.post("/constitution-test", response_model=TCMDiagnosisResponse)
async def constitution_test(
    data: ConstitutionTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answers_text_parts = []
    for ans in data.answers:
        q_result = await db.execute(select(ConstitutionQuestion).where(ConstitutionQuestion.id == ans.question_id))
        question = q_result.scalar_one_or_none()
        q_text = question.question_text if question else f"问题{ans.question_id}"
        answers_text_parts.append(f"{q_text}: {ans.answer_value}")

    constitution_data = "\n".join(answers_text_parts)

    profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    if profile:
        constitution_data += f"\n用户信息: 性别{profile.gender or '未知'}, 身高{profile.height or '未知'}cm, 体重{profile.weight or '未知'}kg"

    ai_result = await tcm_analysis(None, None, constitution_data, db)

    constitution_desc = ai_result.get("syndrome_analysis", "")
    advice = ai_result.get("health_plan", "")

    diagnosis = TCMDiagnosis(
        user_id=current_user.id,
        constitution_type=ai_result.get("constitution_type", ""),
        syndrome_analysis=constitution_desc,
        health_plan=advice,
        family_member_id=data.family_member_id,
        constitution_description=ai_result.get("constitution_type", ""),
        advice_summary=advice[:1000] if advice else None,
    )
    db.add(diagnosis)
    await db.flush()

    for ans in data.answers:
        ca = ConstitutionAnswer(
            diagnosis_id=diagnosis.id,
            question_id=ans.question_id,
            answer_value=ans.answer_value,
        )
        db.add(ca)

    session = ChatSession(
        user_id=current_user.id,
        session_type=SessionType.constitution_test,
        title=f"体质测评 - {ai_result.get('constitution_type', '未知')}",
        family_member_id=data.family_member_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=f"体质测评问卷回答:\n{constitution_data}",
    )
    db.add(user_msg)

    ai_content = f"体质类型: {ai_result.get('constitution_type', '')}\n\n辨证分析: {constitution_desc}\n\n调理建议: {advice}"
    ai_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.assistant,
        content=ai_content,
    )
    db.add(ai_msg)

    await db.flush()
    await db.refresh(diagnosis)
    return TCMDiagnosisResponse.model_validate(diagnosis)
