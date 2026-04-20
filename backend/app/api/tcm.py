from typing import Dict, Optional

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
    FamilyMember,
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
    rows = result.scalars().all()

    # 聚合 family_member 以便构造 member_label（PRD v1.0 § 4.1 规则）
    fm_ids = list({r.family_member_id for r in rows if r.family_member_id})
    fm_map: Dict[int, FamilyMember] = {}
    if fm_ids:
        fm_rows = (await db.execute(
            select(FamilyMember).where(FamilyMember.id.in_(fm_ids))
        )).scalars().all()
        fm_map = {fm.id: fm for fm in fm_rows}

    def _build_label(fm: Optional[FamilyMember], has_id: bool) -> str:
        if fm is None:
            return "未知" if has_id else "本人"
        name = (fm.nickname or "").strip() or "成员"
        if getattr(fm, "is_self", False):
            return f"{name}（本人）"
        relation = (fm.relationship_type or "").strip() or None
        if not relation or relation.lower() == "self":
            return f"{name}（未设置）"
        return f"{name}（{relation}）"

    items = []
    for d in rows:
        base = TCMDiagnosisListResponse.model_validate(d).model_dump()
        fm = fm_map.get(d.family_member_id) if d.family_member_id else None
        member_label = _build_label(fm, bool(d.family_member_id))
        base["member_label"] = member_label
        # 兼容旧字段（老前端/小程序读取）
        base["family_member_name"] = member_label
        items.append(base)

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
    """体质测评提交：
    BUG ①修复要点：
    1. answers 中的 question_id 若在 `constitution_questions` 表中不存在（前端硬编码 1-8 题
       但 DB 实际有不同 ID），将外键约束直接 500。修复：仅对 DB 中真实存在的问题写入
       ConstitutionAnswer，缺失问题以"问题{id}"占位写入提示词，不影响主流程。
    2. AI 接口（call_ai_model / json.loads）异常统一 try/except 兜底，永远不抛 500。
    3. 业务层错误返回 422 + 真实 message；500 仅用于真正未知异常。
    """
    if not data.answers:
        raise HTTPException(status_code=422, detail="答题内容不能为空，请先完成体质问卷")

    if data.family_member_id is not None:
        try:
            fm_result = await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == data.family_member_id,
                    FamilyMember.user_id == current_user.id,
                )
            )
            if not fm_result.scalar_one_or_none():
                raise HTTPException(status_code=422, detail="所选咨询人不存在或不属于当前用户")
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"咨询人校验失败：{e}")

    # ── 1. 查询 DB 中实际存在的问题 ID 集合 ──
    q_ids = list({ans.question_id for ans in data.answers})
    try:
        q_rows = (await db.execute(
            select(ConstitutionQuestion).where(ConstitutionQuestion.id.in_(q_ids))
        )).scalars().all()
    except Exception:
        q_rows = []
    valid_q_map = {q.id: q.question_text for q in q_rows}
    valid_q_ids = set(valid_q_map.keys())

    # ── 2. 拼接给 AI 的体质问卷文本（有题文用题文，无题文以编号占位）──
    answers_text_parts = []
    for ans in data.answers:
        q_text = valid_q_map.get(ans.question_id) or f"问题{ans.question_id}"
        answers_text_parts.append(f"{q_text}: {ans.answer_value}")
    constitution_data = "\n".join(answers_text_parts)

    try:
        profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            constitution_data += (
                f"\n用户信息: 性别{profile.gender or '未知'}, "
                f"身高{profile.height or '未知'}cm, 体重{profile.weight or '未知'}kg"
            )
    except Exception:
        pass

    # ── 3. 调用 AI 模型（含整体兜底，AI 异常不影响入库）──
    try:
        ai_result = await tcm_analysis(None, None, constitution_data, db)
        if not isinstance(ai_result, dict):
            ai_result = {}
    except Exception as e:  # noqa: BLE001
        ai_result = {
            "constitution_type": "平和质",
            "syndrome_analysis": f"AI 暂时不可用，已记录您的回答（错误：{e}）",
            "health_plan": "建议保持规律作息、合理饮食和适量运动。如需深入辨证，请稍后重试。",
        }

    constitution_type = (ai_result.get("constitution_type") or "平和质")[:50]
    constitution_desc = ai_result.get("syndrome_analysis") or ""
    advice = ai_result.get("health_plan") or ""

    # ── 4. 入库（外键过滤后写入 ConstitutionAnswer）──
    # BUG ① 关键修复：把 chat_session 副流程的 try/except 放到 commit 之后，
    # 避免 session 因副流程的 flush 异常进入 inactive 状态导致 diagnosis 被 expunge，
    # 进而 refresh 时报 "Instance is not persistent within this Session"。
    try:
        diagnosis = TCMDiagnosis(
            user_id=current_user.id,
            constitution_type=constitution_type,
            syndrome_analysis=constitution_desc,
            health_plan=advice,
            family_member_id=data.family_member_id,
            constitution_description=constitution_type,
            advice_summary=(advice[:1000] if advice else None),
        )
        db.add(diagnosis)
        await db.flush()

        # 仅对 DB 中真实存在的 question_id 写入答案（避免外键约束 500）
        for ans in data.answers:
            if ans.question_id in valid_q_ids:
                db.add(ConstitutionAnswer(
                    diagnosis_id=diagnosis.id,
                    question_id=ans.question_id,
                    answer_value=str(ans.answer_value)[:200],
                ))

        # 主流程立即 commit，把 diagnosis + 答案落盘
        await db.commit()
        await db.refresh(diagnosis)
        # 立即把响应所需字段拷到本地，避免后续 commit 触发 expire 后再触发懒加载
        diagnosis_snapshot = {
            "id": diagnosis.id,
            "user_id": diagnosis.user_id,
            "tongue_image_url": diagnosis.tongue_image_url,
            "face_image_url": diagnosis.face_image_url,
            "constitution_type": diagnosis.constitution_type,
            "tongue_analysis": diagnosis.tongue_analysis,
            "face_analysis": diagnosis.face_analysis,
            "syndrome_analysis": diagnosis.syndrome_analysis,
            "health_plan": diagnosis.health_plan,
            "family_member_id": diagnosis.family_member_id,
            "constitution_description": diagnosis.constitution_description,
            "advice_summary": diagnosis.advice_summary,
            "created_at": diagnosis.created_at,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=422, detail=f"保存体质测评失败：{e}")

    # ── 5. 创建 chat session（独立 try，失败不影响主流程响应）──
    try:
        session = ChatSession(
            user_id=current_user.id,
            session_type=SessionType.constitution_test,
            title=f"体质测评 - {constitution_type}",
            family_member_id=data.family_member_id,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        db.add(ChatMessage(
            session_id=session.id,
            role=MessageRole.user,
            content=f"体质测评问卷回答:\n{constitution_data}",
        ))
        ai_content = (
            f"体质类型: {constitution_type}\n\n"
            f"辨证分析: {constitution_desc}\n\n"
            f"调理建议: {advice}"
        )
        db.add(ChatMessage(
            session_id=session.id,
            role=MessageRole.assistant,
            content=ai_content,
        ))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass

    return TCMDiagnosisResponse.model_validate(diagnosis_snapshot)
