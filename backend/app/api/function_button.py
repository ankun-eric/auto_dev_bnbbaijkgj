from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    ChatFunctionButton,
    ChatMessage,
    ChatSession,
    DigitalHuman,
    MessageRole,
    MessageType,
    SessionType,
    User,
    VoiceCallRecord,
    VoiceServiceConfig,
)
from app.schemas.function_button import (
    ButtonSortRequest,
    ChatFunctionButtonCreate,
    ChatFunctionButtonResponse,
    ChatFunctionButtonUpdate,
    DigitalHumanCreate,
    DigitalHumanResponse,
    DigitalHumanUpdate,
    ImageRecognizeRequest,
    VoiceCallEndRequest,
    VoiceCallMessageRequest,
    VoiceCallMessageResponse,
    VoiceCallRecordResponse,
    VoiceCallStartRequest,
    VoiceServiceConfigResponse,
    VoiceServiceConfigUpdate,
)
from app.services.ai_service import call_ai_model

router = APIRouter(prefix="/api/chat", tags=["功能按钮与数字人"])
admin_router = APIRouter(prefix="/api/admin", tags=["管理后台-功能按钮与数字人"])

admin_dep = require_role("admin")


# ════════════════════════════════════════
#  用户端 API
# ════════════════════════════════════════


@router.get("/function-buttons", response_model=list[ChatFunctionButtonResponse])
async def get_function_buttons(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatFunctionButton)
        .where(ChatFunctionButton.is_enabled == True)  # noqa: E712
        .order_by(ChatFunctionButton.sort_weight.asc())
    )
    return [ChatFunctionButtonResponse.model_validate(b) for b in result.scalars().all()]


@router.get("/digital-human/{digital_human_id}", response_model=DigitalHumanResponse)
async def get_digital_human(
    digital_human_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigitalHuman).where(DigitalHuman.id == digital_human_id)
    )
    dh = result.scalar_one_or_none()
    if not dh:
        raise HTTPException(status_code=404, detail="数字人不存在")
    return DigitalHumanResponse.model_validate(dh)


@router.post("/voice-call/start", response_model=VoiceCallRecordResponse)
async def start_voice_call(
    data: VoiceCallStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = VoiceCallRecord(
        user_id=current_user.id,
        digital_human_id=data.digital_human_id,
        chat_session_id=data.chat_session_id,
        start_time=datetime.utcnow(),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return VoiceCallRecordResponse.model_validate(record)


@router.post("/voice-call/{call_id}/end", response_model=VoiceCallRecordResponse)
async def end_voice_call(
    call_id: int,
    data: VoiceCallEndRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceCallRecord).where(
            VoiceCallRecord.id == call_id,
            VoiceCallRecord.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="通话记录不存在")

    now = datetime.utcnow()
    record.end_time = now
    if record.start_time:
        record.duration_seconds = int((now - record.start_time).total_seconds())
    record.dialog_content = data.dialog_content

    if data.dialog_content and record.chat_session_id:
        session_result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == record.chat_session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        session = session_result.scalar_one_or_none()
        if session:
            for entry in data.dialog_content:
                role_str = entry.get("role", "user")
                content = entry.get("content", "")
                if not content:
                    continue
                role = MessageRole.user if role_str == "user" else MessageRole.assistant
                msg = ChatMessage(
                    session_id=session.id,
                    role=role,
                    content=content,
                    message_type=MessageType.voice,
                )
                db.add(msg)
            session.message_count = (session.message_count or 0) + len(data.dialog_content)

    await db.flush()
    await db.refresh(record)
    return VoiceCallRecordResponse.model_validate(record)


@router.post("/voice-call/{call_id}/message", response_model=VoiceCallMessageResponse)
async def voice_call_message(
    call_id: int,
    data: VoiceCallMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceCallRecord).where(
            VoiceCallRecord.id == call_id,
            VoiceCallRecord.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="通话记录不存在")

    existing_dialog = record.dialog_content or []
    messages = [
        {"role": entry.get("role", "user"), "content": entry.get("content", "")}
        for entry in existing_dialog
        if entry.get("content")
    ]
    messages.append({"role": "user", "content": data.user_text})

    system_prompt = (
        "你是「宾尼小康」AI健康咨询数字人助手，正在与用户进行语音通话。"
        "请用简洁、自然的口语化方式回答用户的健康问题，回复控制在100字以内。"
        "所有内容仅供健康参考，不构成任何医疗诊断或治疗建议。"
    )

    ai_result = await call_ai_model(messages, system_prompt, db, return_usage=True)
    ai_text = ai_result["content"] if isinstance(ai_result, dict) else ai_result

    existing_dialog.append({"role": "user", "content": data.user_text})
    existing_dialog.append({"role": "assistant", "content": ai_text})
    record.dialog_content = existing_dialog

    await db.flush()
    return VoiceCallMessageResponse(ai_text=ai_text)


@router.post("/image/recognize-medicine")
async def recognize_medicine(
    data: ImageRecognizeRequest,
    db: AsyncSession = Depends(get_db),
):
    system_prompt = (
        "你是一位专业的药品识别AI助手。请根据用户提供的药品图片进行识别分析，"
        "返回药品名称、分类、用法用量、注意事项等信息。"
        "所有用药信息仅供参考，具体用药请严格遵医嘱。"
    )
    messages = [
        {"role": "user", "content": f"请识别这张药品图片：{data.image_url}"},
    ]
    ai_result = await call_ai_model(messages, system_prompt, db, return_usage=True)
    ai_text = ai_result["content"] if isinstance(ai_result, dict) else ai_result
    return {"result": ai_text, "image_url": data.image_url}


@router.post("/image/analyze-report")
async def analyze_report(
    data: ImageRecognizeRequest,
    db: AsyncSession = Depends(get_db),
):
    system_prompt = (
        "你是一位专业的体检报告解读AI助手。请根据用户上传的报告图片进行分析解读，"
        "提取关键指标，指出异常项目，并给出健康建议。"
        "所有内容仅供健康参考，不构成任何医疗诊断或治疗建议。"
    )
    messages = [
        {"role": "user", "content": f"请解读这份报告：{data.image_url}"},
    ]
    ai_result = await call_ai_model(messages, system_prompt, db, return_usage=True)
    ai_text = ai_result["content"] if isinstance(ai_result, dict) else ai_result
    return {"result": ai_text, "image_url": data.image_url}


@router.get("/voice-service/vad-config")
async def get_vad_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VoiceServiceConfig).where(VoiceServiceConfig.config_type == "vad_param")
    )
    configs = result.scalars().all()
    return {c.config_key: c.config_value for c in configs}


# ════════════════════════════════════════
#  管理端 API
# ════════════════════════════════════════


@admin_router.get("/function-buttons")
async def admin_list_buttons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(ChatFunctionButton.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ChatFunctionButton)
        .order_by(ChatFunctionButton.sort_weight.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ChatFunctionButtonResponse.model_validate(b) for b in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.post("/function-buttons", response_model=ChatFunctionButtonResponse)
async def admin_create_button(
    data: ChatFunctionButtonCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    btn = ChatFunctionButton(**data.model_dump())
    db.add(btn)
    await db.flush()
    await db.refresh(btn)
    return ChatFunctionButtonResponse.model_validate(btn)


@admin_router.put("/function-buttons/{button_id}", response_model=ChatFunctionButtonResponse)
async def admin_update_button(
    button_id: int,
    data: ChatFunctionButtonUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatFunctionButton).where(ChatFunctionButton.id == button_id)
    )
    btn = result.scalar_one_or_none()
    if not btn:
        raise HTTPException(status_code=404, detail="按钮不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(btn, field, value)
    await db.flush()
    await db.refresh(btn)
    return ChatFunctionButtonResponse.model_validate(btn)


@admin_router.delete("/function-buttons/{button_id}")
async def admin_delete_button(
    button_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatFunctionButton).where(ChatFunctionButton.id == button_id)
    )
    btn = result.scalar_one_or_none()
    if not btn:
        raise HTTPException(status_code=404, detail="按钮不存在")
    await db.delete(btn)
    await db.flush()
    return {"message": "删除成功"}


@admin_router.put("/function-buttons/sort")
async def admin_sort_buttons(
    data: ButtonSortRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item in data.items:
        result = await db.execute(
            select(ChatFunctionButton).where(ChatFunctionButton.id == item.id)
        )
        btn = result.scalar_one_or_none()
        if btn:
            btn.sort_weight = item.sort_weight
    await db.flush()
    return {"message": "排序更新成功"}


@admin_router.get("/digital-humans")
async def admin_list_digital_humans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(DigitalHuman.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(DigitalHuman)
        .order_by(DigitalHuman.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [DigitalHumanResponse.model_validate(dh) for dh in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.post("/digital-humans", response_model=DigitalHumanResponse)
async def admin_create_digital_human(
    data: DigitalHumanCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    dh = DigitalHuman(**data.model_dump())
    db.add(dh)
    await db.flush()
    await db.refresh(dh)
    return DigitalHumanResponse.model_validate(dh)


@admin_router.put("/digital-humans/{digital_human_id}", response_model=DigitalHumanResponse)
async def admin_update_digital_human(
    digital_human_id: int,
    data: DigitalHumanUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigitalHuman).where(DigitalHuman.id == digital_human_id)
    )
    dh = result.scalar_one_or_none()
    if not dh:
        raise HTTPException(status_code=404, detail="数字人不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dh, field, value)
    await db.flush()
    await db.refresh(dh)
    return DigitalHumanResponse.model_validate(dh)


@admin_router.delete("/digital-humans/{digital_human_id}")
async def admin_delete_digital_human(
    digital_human_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigitalHuman).where(DigitalHuman.id == digital_human_id)
    )
    dh = result.scalar_one_or_none()
    if not dh:
        raise HTTPException(status_code=404, detail="数字人不存在")
    await db.delete(dh)
    await db.flush()
    return {"message": "删除成功"}


@admin_router.get("/voice-service/config")
async def admin_get_voice_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceServiceConfig).order_by(VoiceServiceConfig.id.asc())
    )
    items = [VoiceServiceConfigResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


@admin_router.put("/voice-service/config")
async def admin_update_voice_config(
    data: VoiceServiceConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceServiceConfig).where(VoiceServiceConfig.config_key == data.config_key)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置项不存在")

    config.config_value = data.config_value
    config.updated_by = current_user.id
    await db.flush()
    await db.refresh(config)
    return VoiceServiceConfigResponse.model_validate(config)


@admin_router.post("/voice-service/test-connection")
async def admin_test_voice_connection(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    return {"status": "ok", "message": "语音服务连接测试成功（placeholder）"}
