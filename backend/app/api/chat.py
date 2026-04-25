import json
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.security import get_current_user
from app.models.models import (
    AiDisclaimerConfig,
    AiPromptConfig,
    AiSensitiveWord,
    ChatMessage,
    ChatSession,
    FamilyMember,
    HealthProfile,
    MessageRole,
    MessageType,
    SessionType,
    User,
)
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatSessionCreate, ChatSessionResponse
from app.services.ai_service import call_ai_model, call_ai_model_stream, symptom_analysis
from app.services.knowledge_search import search_knowledge
# [2026-04-23 v1.2] 用药对话 drug_query 注入 {member_info} + {drug_list}
from app.api.drug_chat import inject_drug_context_to_prompt

router = APIRouter(prefix="/api/chat", tags=["AI对话"])

DEFAULT_SYSTEM_PROMPTS = {
    "health_qa": "你是「宾尼小康」AI健康咨询助手，一个专业、友好的健康咨询助手。请用通俗易懂的语言回答用户的健康相关问题，提供健康参考信息，并在必要时建议用户及时就医。所有内容仅供健康参考，不构成任何医疗诊断或治疗建议。",
    "symptom_check": "你是一位专业的AI健康自查助手。请根据用户描述的身体状况进行初步健康参考分析，给出可能的相关因素和健康建议。所有内容仅供自我健康参考，不能替代专业医疗检查，如有异常请尽快就医。",
    "tcm": "你是一位中医AI养生助手，精通中医养生理论。请根据用户描述，从中医养生角度提供调理建议。所有中医养生建议仅供参考，个人体质不同，建议在专业中医师指导下调理。",
    "tcm_tongue": "你是一位资深的中医AI舌诊专家。用户上传了舌头照片，请根据舌象（舌色、舌苔、舌形等）进行中医辨识分析，判断可能的体质或证候，并给出针对性的中医调理建议。所有中医分析仅供参考，建议在专业中医师指导下进一步辨证施治。",
    "tcm_face": "你是一位资深的中医AI面诊专家。用户上传了面部照片，请根据面色、神态、面相特征等进行中医面诊分析，判断可能的体质或脏腑功能状态，并给出针对性的中医调理建议。所有中医分析仅供参考，建议在专业中医师指导下进一步辨证施治。",
    "drug_query": "你是一位药学AI用药参考助手，请提供药品的基本信息供用户参考，包括常见用法、注意事项、相互作用等。所有用药信息仅供参考，具体用药请严格遵医嘱，切勿自行用药。",
    "customer_service": "你是「宾尼小康」平台的AI客服助手，请热情友好地解答用户关于平台服务的问题。",
    "drug_identify": "你是一位专业的药品识别AI助手。用户通过拍照识别药品，请根据药品图片识别结果提供药品详细信息，包括名称、分类、用法用量、注意事项等。如用户上传多张图片，请综合分析所有图片信息。所有用药信息仅供参考，具体用药请严格遵医嘱。",
    "constitution_test": "你是一位资深的中医AI体质辨识专家。请根据用户的体质测评问卷结果进行综合辨识分析，判断体质类型，并给出调理建议。所有中医养生建议仅供参考，建议在专业中医师指导下调理。",
}


async def _get_system_prompt(session_type: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(AiPromptConfig).where(AiPromptConfig.chat_type == session_type)
    )
    config = result.scalar_one_or_none()
    if config and config.system_prompt:
        return config.system_prompt
    return DEFAULT_SYSTEM_PROMPTS.get(session_type, DEFAULT_SYSTEM_PROMPTS["health_qa"])


async def _filter_sensitive_words(content: str, db: AsyncSession) -> str:
    result = await db.execute(select(AiSensitiveWord))
    words = result.scalars().all()
    for w in words:
        content = content.replace(w.sensitive_word, w.replacement_word)
    return content


async def _append_disclaimer(content: str, session_type: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(AiDisclaimerConfig).where(AiDisclaimerConfig.chat_type == session_type)
    )
    config = result.scalar_one_or_none()
    if config and config.is_enabled and config.disclaimer_text:
        content += "\n\n---disclaimer---\n" + config.disclaimer_text
    return content


def _calc_age(birthday: date) -> int:
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _calc_bmi(height: float, weight: float) -> float:
    return weight / ((height / 100) ** 2)


async def _build_health_context(session: ChatSession, db: AsyncSession) -> str:
    """Build a health profile context string to append to system_prompt."""
    context_parts = []

    if session.family_member_id:
        member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == session.family_member_id)
        )
        member = member_result.scalar_one_or_none()

        profile_result = await db.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == session.user_id,
                HealthProfile.family_member_id == session.family_member_id,
            )
        )
        profile = profile_result.scalar_one_or_none()

        if member:
            nickname = member.nickname or "家庭成员"
            rel = member.relationship_type
            gender = (profile.gender if profile and profile.gender else None) or member.gender or "未知"
            birthday = (profile.birthday if profile and profile.birthday else None) or member.birthday
            height = (profile.height if profile and profile.height else None) or member.height
            weight = (profile.weight if profile and profile.weight else None) or member.weight
            medical_histories = (profile.medical_histories if profile and profile.medical_histories else None) or member.medical_histories or []
            allergies = (profile.allergies if profile and profile.allergies else None) or member.allergies or []

            age_str = f"{_calc_age(birthday)}岁" if birthday else "年龄未知"
            bmi_str = f"，BMI：{_calc_bmi(height, weight):.1f}" if height and weight else ""
            height_str = f"{height}cm" if height else "未知"
            weight_str = f"{weight}kg" if weight else "未知"
            histories_str = "、".join(medical_histories) if medical_histories else "无"
            allergies_str = "、".join(allergies) if allergies else "无"

            context_parts.append(f"\n\n## 本次咨询对象健康档案")
            context_parts.append(f"咨询对象：{rel}·{nickname}，{gender}，{age_str}")
            context_parts.append(f"身高：{height_str}，体重：{weight_str}{bmi_str}")
            context_parts.append(f"既往病史：{histories_str}")
            context_parts.append(f"过敏史：{allergies_str}")

    if session.symptom_info:
        si = session.symptom_info
        parts = []
        if si.get("body_part"):
            parts.append(f"部位：{si['body_part']}")
        if si.get("symptoms"):
            symptoms = si["symptoms"]
            if isinstance(symptoms, list):
                parts.append(f"症状：{'、'.join(symptoms)}")
            else:
                parts.append(f"症状：{symptoms}")
        if si.get("duration"):
            parts.append(f"持续时间：{si['duration']}")
        if si.get("description"):
            parts.append(si["description"])
        if parts:
            context_parts.append(f"\n本次自查症状：{'；'.join(parts)}")

    if not context_parts:
        return ""

    if session.family_member_id:
        _member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == session.family_member_id)
        )
        _member = _member_result.scalar_one_or_none()
        rel = _member.relationship_type if _member else "家庭成员"
        context_parts.append(
            f'\n\n请以亲切自然的语气，在回复中自然融入对咨询对象信息的引用，不要集中列出，'
            f'开头可以"您好，我注意到这次是为您的{rel}咨询..."'
        )
    else:
        context_parts.append(
            "\n\n请结合用户的症状信息提供针对性的健康建议。"
        )

    return "\n".join(context_parts)


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(
        user_id=current_user.id,
        session_type=data.session_type,
        title=data.title or "新对话",
        family_member_id=data.family_member_id,
        symptom_info=data.symptom_info,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions")
async def list_sessions(
    session_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).where(ChatSession.user_id == current_user.id)
    count_query = select(func.count(ChatSession.id)).where(ChatSession.user_id == current_user.id)

    if session_type:
        query = query.where(ChatSession.session_type == session_type)
        count_query = count_query.where(ChatSession.session_type == session_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ChatSessionResponse.model_validate(s) for s in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    total_result = await db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: int,
    data: ChatMessageCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_metadata = None
    if data.silent:
        msg_metadata = {"silent": True}

    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
        message_metadata=msg_metadata,
    )
    db.add(user_msg)
    await db.flush()

    if not session.device_info:
        session.device_info = request.headers.get("User-Agent", "")[:500]
    if not session.ip_address:
        session.ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host if request.client else None
        )

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

    session_type_val = session.session_type.value if hasattr(session.session_type, "value") else session.session_type
    system_prompt = await _get_system_prompt(session_type_val, db)

    health_context = await _build_health_context(session, db)
    if health_context:
        system_prompt += health_context

    # [2026-04-23 v1.2] drug_query 场景：注入 {member_info} + {drug_list}
    if session_type_val == "drug_query":
        try:
            system_prompt = await inject_drug_context_to_prompt(
                db, session, system_prompt, current_user.id
            )
        except Exception:
            pass

    knowledge_hits = []
    try:
        kb_result = await search_knowledge(
            data.content, session_type_val, db,
            session_id=session_id, message_id=None,
        )
        knowledge_hits = kb_result.get("hits", [])
        if knowledge_hits:
            kb_context_parts = []
            for hit in knowledge_hits:
                if hit.get("question"):
                    kb_context_parts.append(f"Q: {hit['question']}")
                if hit.get("content_json"):
                    content_val = hit["content_json"]
                    if isinstance(content_val, dict):
                        kb_context_parts.append(f"A: {json.dumps(content_val, ensure_ascii=False)}")
                    elif isinstance(content_val, str):
                        kb_context_parts.append(f"A: {content_val}")
                elif hit.get("title"):
                    kb_context_parts.append(f"A: {hit['title']}")
            if kb_context_parts:
                kb_context = "\n".join(kb_context_parts)
                system_prompt += f"\n\n以下是知识库中匹配到的参考信息，请优先参考这些内容回答用户问题：\n{kb_context}"
    except Exception:
        pass

    start_time = time.time()
    ai_result = await call_ai_model(messages, system_prompt, db, return_usage=True)
    elapsed_ms = int((time.time() - start_time) * 1000)

    ai_content = ai_result["content"]
    usage = ai_result.get("usage")
    model_used = ai_result.get("model")

    ai_content = await _filter_sensitive_words(ai_content, db)
    ai_content = await _append_disclaimer(ai_content, session_type_val, db)

    if not session.model_name and model_used:
        session.model_name = model_used

    ai_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.assistant,
        content=ai_content,
        message_type=MessageType.text,
        response_time_ms=elapsed_ms,
        prompt_tokens=usage.get("prompt_tokens") if usage else None,
        completion_tokens=usage.get("completion_tokens") if usage else None,
    )
    db.add(ai_msg)

    session.message_count = (session.message_count or 0) + 1

    if session.title == "新对话" and len(history_msgs) <= 2:
        session.title = data.content[:50]

    await db.flush()
    await db.refresh(ai_msg)

    resp = ChatMessageResponse.model_validate(ai_msg).model_dump()
    if knowledge_hits:
        resp["knowledge_hits"] = knowledge_hits
    return resp


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: int,
    data: ChatMessageCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    stream_msg_metadata = None
    if data.silent:
        stream_msg_metadata = {"silent": True}

    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
        message_metadata=stream_msg_metadata,
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    if not session.device_info:
        session.device_info = request.headers.get("User-Agent", "")[:500]
    if not session.ip_address:
        session.ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host if request.client else None
        )

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))
    messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

    session_type_val = session.session_type.value if hasattr(session.session_type, "value") else session.session_type
    system_prompt = await _get_system_prompt(session_type_val, db)

    health_context = await _build_health_context(session, db)
    if health_context:
        system_prompt += health_context

    # [2026-04-23 v1.2] drug_query 场景：注入 {member_info} + {drug_list}
    if session_type_val == "drug_query":
        try:
            system_prompt = await inject_drug_context_to_prompt(
                db, session, system_prompt, current_user.id
            )
        except Exception:
            pass

    try:
        kb_result = await search_knowledge(
            data.content, session_type_val, db,
            session_id=session_id, message_id=None,
        )
        knowledge_hits = kb_result.get("hits", [])
        if knowledge_hits:
            kb_context_parts = []
            for hit in knowledge_hits:
                if hit.get("question"):
                    kb_context_parts.append(f"Q: {hit['question']}")
                if hit.get("content_json"):
                    content_val = hit["content_json"]
                    if isinstance(content_val, dict):
                        kb_context_parts.append(f"A: {json.dumps(content_val, ensure_ascii=False)}")
                    elif isinstance(content_val, str):
                        kb_context_parts.append(f"A: {content_val}")
                elif hit.get("title"):
                    kb_context_parts.append(f"A: {hit['title']}")
            if kb_context_parts:
                kb_context = "\n".join(kb_context_parts)
                system_prompt += f"\n\n以下是知识库中匹配到的参考信息，请优先参考这些内容回答用户问题：\n{kb_context}"
    except Exception:
        pass

    captured_db = db
    captured_session = session
    captured_session_id = session_id
    captured_session_type_val = session_type_val
    captured_data = data
    captured_history_msgs = history_msgs

    start_time = time.time()

    async def event_generator():
        full_content = ""
        async for chunk in call_ai_model_stream(messages, system_prompt, captured_db):
            if chunk["type"] == "delta":
                full_content = chunk.get("_full", full_content)
                sse_data = json.dumps({"content": chunk["content"]}, ensure_ascii=False)
                yield f"event: delta\ndata: {sse_data}\n\n"
            elif chunk["type"] == "done":
                full_content = chunk["content"]
                elapsed_ms = int((time.time() - start_time) * 1000)

                ai_content = await _filter_sensitive_words(full_content, captured_db)
                ai_content = await _append_disclaimer(ai_content, captured_session_type_val, captured_db)

                ai_msg = ChatMessage(
                    session_id=captured_session_id,
                    role=MessageRole.assistant,
                    content=ai_content,
                    message_type=MessageType.text,
                    response_time_ms=elapsed_ms,
                )
                captured_db.add(ai_msg)
                captured_session.message_count = (captured_session.message_count or 0) + 1
                if captured_session.title == "新对话" and len(captured_history_msgs) <= 2:
                    captured_session.title = captured_data.content[:50]
                await captured_db.flush()
                await captured_db.refresh(ai_msg)

                done_data = json.dumps({
                    "message_id": ai_msg.id,
                    "full_content": ai_content,
                }, ensure_ascii=False)
                yield f"event: done\ndata: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/switch-member")
async def switch_session_member(
    session_id: int,
    family_member_id: Optional[int] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # [2026-04-25 Bug-04] 报告解读/对比类会话强绑定上传时选择的咨询人，后端禁止切换
    _stype_val = session.session_type.value if hasattr(session.session_type, "value") else str(session.session_type)
    if _stype_val in ("report_interpret", "report_compare"):
        raise HTTPException(status_code=400, detail="报告解读/对比会话不允许切换咨询人")

    if family_member_id is not None:
        member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == family_member_id, FamilyMember.user_id == current_user.id)
        )
        member = member_result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="家庭成员不存在")

        profile_result = await db.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == current_user.id,
                HealthProfile.family_member_id == family_member_id,
            )
        )
        profile = profile_result.scalar_one_or_none()

        nickname = member.nickname or "家庭成员"
        rel = member.relationship_type
        gender = (profile.gender if profile and profile.gender else None) or member.gender or "未知"
        birthday = (profile.birthday if profile and profile.birthday else None) or member.birthday
        height = (profile.height if profile and profile.height else None) or member.height
        weight = (profile.weight if profile and profile.weight else None) or member.weight
        medical_histories = (profile.medical_histories if profile and profile.medical_histories else None) or member.medical_histories or []
        allergies = (profile.allergies if profile and profile.allergies else None) or member.allergies or []

        age_str = f"{_calc_age(birthday)}岁" if birthday else "年龄未知"
        bmi_str = f"，BMI：{_calc_bmi(height, weight):.1f}" if height and weight else ""
        histories_str = "、".join(medical_histories) if medical_histories else "无"
        allergies_str = "、".join(allergies) if allergies else "无"

        switch_summary = (
            f"用户已将咨询对象切换为{rel}·{nickname}（{gender}，{age_str}"
            f"，身高：{height or '未知'}cm，体重：{weight or '未知'}kg{bmi_str}"
            f"，既往病史：{histories_str}，过敏史：{allergies_str}）"
        )
        session.family_member_id = family_member_id
        message = f"已切换咨询对象为{rel}·{nickname}"
    else:
        switch_summary = "用户已将咨询对象切换回自己"
        session.family_member_id = None
        message = "已切换咨询对象为自己"

    await db.flush()
    return {"message": message, "family_member_id": family_member_id, "switch_summary": switch_summary}


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: int):
    await websocket.accept()

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少认证token")
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except JWTError:
        await websocket.close(code=4001, reason="无效的认证token")
        return

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            content = data.get("content", "")
            msg_type = data.get("message_type", "text")

            async with async_session() as db:
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
                )
                session = result.scalar_one_or_none()
                if not session:
                    await websocket.send_json({"error": "会话不存在"})
                    continue

                user_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.user,
                    content=content,
                    message_type=msg_type,
                )
                db.add(user_msg)
                await db.flush()

                history_result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(20)
                )
                history_msgs = list(reversed(history_result.scalars().all()))
                messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

                stype = session.session_type.value if hasattr(session.session_type, "value") else session.session_type
                system_prompt = await _get_system_prompt(stype, db)

                ai_reply = await call_ai_model(messages, system_prompt, db)

                ai_reply = await _filter_sensitive_words(ai_reply, db)
                ai_reply = await _append_disclaimer(ai_reply, stype, db)

                ai_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.assistant,
                    content=ai_reply,
                    message_type=MessageType.text,
                )
                db.add(ai_msg)
                await db.commit()

                await websocket.send_json({
                    "role": "assistant",
                    "content": ai_reply,
                    "message_type": "text",
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()


# ──────────────── [2026-04-23] 对话化 v2：通用会话详情 + SSE 流式接口 ────────────────


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """会话详情。返回扩展字段：
    - report_id：对话解读场景绑定的报告 id（report_interpret）
    - report_ids：对比场景的报告 id 列表（report_compare）
    - family_member：咨询人简要档案（id / nickname / relationship / gender / age / avatar）
    - reports_brief：对话涉及的报告概要数组（title / report_date / thumbnail_url / file_url）
    """
    from app.models.models import CheckupReport as _CR

    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    stype = sess.session_type.value if hasattr(sess.session_type, "value") else str(sess.session_type)

    # 报告 id / ids 解析
    report_id_val: Optional[int] = getattr(sess, "report_id", None)
    compare_ids_raw = getattr(sess, "compare_report_ids", None)
    report_ids_val: list[int] = []
    if compare_ids_raw:
        try:
            report_ids_val = [int(x.strip()) for x in str(compare_ids_raw).split(",") if x.strip()]
        except Exception:
            report_ids_val = []

    # family_member 简要
    family_member_brief = None
    if sess.family_member_id:
        fm_r = await db.execute(
            select(FamilyMember).where(FamilyMember.id == sess.family_member_id)
        )
        fm = fm_r.scalar_one_or_none()
        if fm:
            age = None
            if fm.birthday:
                try:
                    age = _calc_age(fm.birthday)
                except Exception:
                    age = None
            family_member_brief = {
                "id": fm.id,
                "nickname": fm.nickname,
                "relationship": fm.relationship_type,
                "gender": fm.gender,
                "age": age,
                "avatar": getattr(fm, "avatar_url", None),
            }

    # reports_brief
    reports_brief: list[dict] = []
    rids_to_load: list[int] = []
    if report_id_val:
        rids_to_load.append(report_id_val)
    if report_ids_val:
        for rid in report_ids_val:
            if rid not in rids_to_load:
                rids_to_load.append(rid)
    for rid in rids_to_load:
        rep = await db.get(_CR, rid)
        if rep and rep.user_id == current_user.id:
            default_title = (
                (rep.report_date or (rep.created_at.date() if rep.created_at else None))
            )
            title = getattr(rep, "title", None) or (
                f"{default_title.strftime('%Y-%m-%d')} 体检报告" if default_title else "体检报告"
            )
            # [2026-04-23] 多图修复：返回完整 URL 列表，fallback 为 [file_url]
            def _to_url_list(val, fallback):
                if isinstance(val, list) and val:
                    return [u for u in val if u]
                if isinstance(val, str) and val:
                    try:
                        import json as _json
                        parsed = _json.loads(val)
                        if isinstance(parsed, list):
                            return [u for u in parsed if u]
                    except Exception:
                        pass
                return [fallback] if fallback else []

            file_urls_list = _to_url_list(getattr(rep, "file_urls", None), rep.file_url)
            thumb_urls_list = _to_url_list(getattr(rep, "thumbnail_urls", None), rep.thumbnail_url or rep.file_url)

            reports_brief.append({
                "id": rep.id,
                "title": title,
                "report_date": rep.report_date.strftime("%Y-%m-%d") if rep.report_date else None,
                "thumbnail_url": rep.thumbnail_url,
                "file_url": rep.file_url,
                "file_urls": file_urls_list,
                "thumbnail_urls": thumb_urls_list,
            })

    # [2026-04-23] 多图修复：前端命名兼容字段
    # - type: 与 session_type 同值，供前端沿用旧命名读取
    # - interpret_session_id: 解读/对比会话取自身 id，其余为 None
    # - compare_report_ids: 与 report_ids 同值列表，兼容前端命名习惯
    # - auto_start_supported: 是否支持自动首条 AI 输出的会话类型
    auto_start_types = {
        "report_interpret",
        "report_compare",
        "symptom_check",
        "drug_identify",
        "constitution_test",
    }
    interpret_self_types = {"report_interpret", "report_compare"}

    return {
        "id": sess.id,
        "user_id": sess.user_id,
        "title": sess.title,
        "session_type": stype,
        "type": stype,
        "family_member_id": sess.family_member_id,
        "message_count": sess.message_count or 0,
        "created_at": sess.created_at.isoformat() if sess.created_at else None,
        "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
        "report_id": report_id_val,
        "report_ids": report_ids_val,
        "compare_report_ids": report_ids_val,
        "interpret_session_id": sess.id if stype in interpret_self_types else None,
        "auto_start_supported": stype in auto_start_types,
        "family_member": family_member_brief,
        "reports_brief": reports_brief,
    }


@router.get("/sessions/{session_id}/first-message-stream")
async def sessions_first_message_stream_get(
    request: Request,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """会话首条消息 SSE 流式输出（GET 方法）。

    行为：订阅后端异步 worker 推送的流式消息；若会话已完成则直接回放。
    [2026-04-25] 已改为纯订阅模式，不再在此接口里同步触发 AI。
    """
    from app.api.report_interpret import interpret_stream as _interpret_stream

    return await _interpret_stream(
        request=request,
        session_id=session_id,
        auto_start=1,
        current_user=current_user,
        db=db,
    )


@router.post("/sessions/{session_id}/first-message-stream")
async def sessions_first_message_stream_post(
    request: Request,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """同 GET，供历史前端兼容（H5 v1.0 用 POST 调用此接口）。"""
    from app.api.report_interpret import interpret_stream as _interpret_stream

    return await _interpret_stream(
        request=request,
        session_id=session_id,
        auto_start=1,
        current_user=current_user,
        db=db,
    )


from pydantic import BaseModel as _ChatBaseModel  # 延迟导入，避免顶部改动


class _MessagesStreamBody(_ChatBaseModel):
    content: str


@router.post("/sessions/{session_id}/messages-stream")
async def sessions_messages_stream(
    session_id: int,
    body: _MessagesStreamBody = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户追问消息 SSE 流式输出。

    行为：保存 user 消息 → 流式调用 AI 生成 assistant 回复 → 落库。
    内部复用 `report_interpret.interpret_chat_followup`。
    """
    from app.api.report_interpret import (
        InterpretChatRequest as _IReq,
        interpret_chat_followup as _interpret_chat,
    )

    return await _interpret_chat(
        session_id=session_id,
        body=_IReq(content=body.content),
        current_user=current_user,
        db=db,
    )
