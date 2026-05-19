from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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
    PromptTemplate,
    PromptTypeConfig,
    SessionType,
    User,
    VoiceCallRecord,
    VoiceServiceConfig,
)
from app.schemas.function_button import (
    ALLOWED_BUTTON_TYPES,
    ALLOWED_AI_FUNCTION_TYPES,
    ALLOWED_CAPTURE_PURPOSES,
    ButtonSortActionRequest,
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
# [AICHAT-OPTIM-FIX-V1 F-04 2026-05-14] 公开顶层路由 /api/function-buttons
# 作为 H5 ai-home 宫格 + chat 详情页胶囊条统一数据源（同一表 chat_function_buttons）
public_router = APIRouter(prefix="/api", tags=["公开-功能按钮"])

admin_dep = require_role("admin")


# ════════════════════════════════════════
#  用户端 API
# ════════════════════════════════════════


@router.get("/function-buttons", response_model=list[ChatFunctionButtonResponse])
async def get_function_buttons(
    position: Optional[str] = Query(None, description="[PRD-AICHAT-HOME-GRID-V1] 过滤位置：grid / capsule / 不传"),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import or_

    stmt = select(ChatFunctionButton)
    pos = (position or "").lower()
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 按 view_type 选择独立排序字段（grid_sort / capsule_sort）
    if pos == "grid":
        stmt = stmt.where(ChatFunctionButton.is_recommended == True)  # noqa: E712
        # [PRD-AICHAT-FUNCBTN-OPTIM-V1] 用 COALESCE 兼容 MySQL（不支持 NULLS LAST）
        stmt = stmt.order_by(
            func.coalesce(ChatFunctionButton.grid_sort, 999999).asc(),
            ChatFunctionButton.sort_weight.asc(),
            ChatFunctionButton.id.asc(),
        )
    elif pos == "capsule":
        stmt = stmt.where(ChatFunctionButton.is_capsule == True)  # noqa: E712
        stmt = stmt.order_by(
            func.coalesce(ChatFunctionButton.capsule_sort, 999999).asc(),
            ChatFunctionButton.sort_weight.asc(),
            ChatFunctionButton.id.asc(),
        )
    else:
        stmt = stmt.where(
            or_(
                ChatFunctionButton.is_recommended == True,  # noqa: E712
                ChatFunctionButton.is_capsule == True,  # noqa: E712
            )
        )
        stmt = stmt.order_by(ChatFunctionButton.sort_weight.asc(), ChatFunctionButton.id.asc())
    result = await db.execute(stmt)
    return [ChatFunctionButtonResponse.model_validate(b) for b in result.scalars().all()]


# ────────────────────────────────────────
#  [AICHAT-OPTIM-FIX-V1 F-04] 公开顶层 /api/function-buttons
# ----------------------------------------
# - 与 /api/chat/function-buttons 等价但 path 平铺，便于 H5 ai-home 宫格 + chat
#   胶囊条统一调用
# - 支持 ?is_enabled=true 仅返回启用按钮（默认）
# - 严禁暴露未启用按钮（避免运营草稿泄露）
# - 排序：sort_weight ASC, id ASC
# - 返回字段：含 8 个新字段 + icon（Emoji）
# ────────────────────────────────────────


@public_router.get("/function-buttons", response_model=list[ChatFunctionButtonResponse])
async def get_public_function_buttons(
    is_enabled: Optional[bool] = Query(True, description="（兼容字段，已忽略）仅保留以避免老前端报错"),
    position: Optional[str] = Query(None, description="[PRD-AICHAT-HOME-GRID-V1] 过滤位置：grid（仅推荐宫格按钮）/ capsule（仅胶囊条按钮）/ 不传则返回 is_recommended OR is_capsule 为 true 的全部按钮"),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AICHAT-HOME-GRID-V1 2026-05-16] 公开接口

    - position=grid    -> 仅 is_recommended=true（按 grid_sort 升序）
    - position=capsule -> 仅 is_capsule=true（按 capsule_sort 升序）
    - 不传 position    -> is_recommended=true OR is_capsule=true（前端按字段过滤）

    任何位置下都不返回两个开关均关闭的按钮（等同旧的"未启用"）。
    """
    from sqlalchemy import or_  # 局部 import 避免顶部循环

    stmt = select(ChatFunctionButton)
    pos = (position or "").lower()
    if pos == "grid":
        stmt = stmt.where(ChatFunctionButton.is_recommended == True)  # noqa: E712
        stmt = stmt.order_by(
            func.coalesce(ChatFunctionButton.grid_sort, 999999).asc(),
            ChatFunctionButton.sort_weight.asc(),
            ChatFunctionButton.id.asc(),
        )
    elif pos == "capsule":
        stmt = stmt.where(ChatFunctionButton.is_capsule == True)  # noqa: E712
        stmt = stmt.order_by(
            func.coalesce(ChatFunctionButton.capsule_sort, 999999).asc(),
            ChatFunctionButton.sort_weight.asc(),
            ChatFunctionButton.id.asc(),
        )
    else:
        stmt = stmt.where(
            or_(
                ChatFunctionButton.is_recommended == True,  # noqa: E712
                ChatFunctionButton.is_capsule == True,  # noqa: E712
            )
        )
        stmt = stmt.order_by(ChatFunctionButton.sort_weight.asc(), ChatFunctionButton.id.asc())
    result = await db.execute(stmt)
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
    view_type: Optional[str] = Query(
        None,
        description="[PRD-AICHAT-FUNCBTN-OPTIM-V1] 视图类型：grid（仅 is_recommended=true，按 grid_sort 升序）/ capsule（仅 is_capsule=true，按 capsule_sort 升序）/ 不传：返回全部按 sort_weight 升序",
    ),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 后台列表接口扩展

    - view_type=grid    : 仅 is_recommended=true 的按钮，按 grid_sort 升序
    - view_type=capsule : 仅 is_capsule=true 的按钮，按 capsule_sort 升序
    - 不传              : 全量按钮，按 sort_weight 升序（旧行为）
    """
    vt = (view_type or "").lower()
    base_stmt = select(ChatFunctionButton)
    count_stmt = select(func.count(ChatFunctionButton.id))

    if vt == "grid":
        base_stmt = base_stmt.where(ChatFunctionButton.is_recommended == True)  # noqa: E712
        count_stmt = count_stmt.where(ChatFunctionButton.is_recommended == True)  # noqa: E712
        base_stmt = base_stmt.order_by(
            func.coalesce(ChatFunctionButton.grid_sort, 999999).asc(),
            ChatFunctionButton.id.asc(),
        )
    elif vt == "capsule":
        base_stmt = base_stmt.where(ChatFunctionButton.is_capsule == True)  # noqa: E712
        count_stmt = count_stmt.where(ChatFunctionButton.is_capsule == True)  # noqa: E712
        base_stmt = base_stmt.order_by(
            func.coalesce(ChatFunctionButton.capsule_sort, 999999).asc(),
            ChatFunctionButton.id.asc(),
        )
    else:
        base_stmt = base_stmt.order_by(ChatFunctionButton.sort_weight.asc())

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    result = await db.execute(
        base_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    items = [ChatFunctionButtonResponse.model_validate(b) for b in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _validate_button_type(btn_type: Optional[str]) -> None:
    """[AI对话模式优化 PRD v1.0] 校验按钮类型属于允许集合。

    [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 加入 page_navigate / ai_function 两大类。
    """
    if btn_type is not None and btn_type not in ALLOWED_BUTTON_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"按钮类型 button_type 取值不合法：{btn_type}，允许值：{sorted(ALLOWED_BUTTON_TYPES)}",
        )


def _validate_ai_function_type(btn_type: Optional[str], ai_func_type: Optional[str]) -> None:
    """[PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 校验 AI 功能子类型。

    - 当 button_type=ai_function 时，ai_function_type 必须是允许子类型集合之一
    - 其它主类型则忽略 ai_function_type
    """
    if btn_type == "ai_function":
        if not ai_func_type:
            raise HTTPException(
                status_code=400,
                detail="按钮类型为 ai_function 时必须指定 ai_function_type",
            )
        if ai_func_type not in ALLOWED_AI_FUNCTION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"ai_function_type 取值不合法：{ai_func_type}，允许值：{sorted(ALLOWED_AI_FUNCTION_TYPES)}",
            )


def _validate_questionnaire_and_capture(
    btn_type: Optional[str],
    ai_func_type: Optional[str],
    questionnaire_template_id: Optional[int],
    capture_purpose: Optional[str],
) -> None:
    """[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]

    - ai_function_type=questionnaire 必填 questionnaire_template_id
    - ai_function_type=image_capture 必填 capture_purpose 且取值合法
    """
    if btn_type != "ai_function":
        return
    if ai_func_type == "questionnaire" and not questionnaire_template_id:
        raise HTTPException(
            status_code=400,
            detail="ai_function_type=questionnaire 时必须指定 questionnaire_template_id",
        )
    if ai_func_type == "image_capture":
        if not capture_purpose:
            raise HTTPException(
                status_code=400,
                detail="ai_function_type=image_capture 时必须指定 capture_purpose",
            )
        if capture_purpose not in ALLOWED_CAPTURE_PURPOSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"capture_purpose 取值不合法：{capture_purpose}，"
                    f"允许值：{sorted(ALLOWED_CAPTURE_PURPOSES)}"
                ),
            )


# [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态枚举
ALLOWED_QUESTIONNAIRE_DISPLAY_FORMS = {"DRAWER_SCROLL", "DRAWER_STEPPED", "INLINE_CHAT"}


def _validate_questionnaire_display_form(
    ai_func_type: Optional[str],
    display_form: Optional[str],
) -> None:
    """[PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]

    - 当 ai_function_type=questionnaire 且 display_form 非空时校验枚举合法
    - 其他类型按钮该字段忽略
    """
    if ai_func_type != "questionnaire":
        return
    if not display_form:
        return
    if display_form not in ALLOWED_QUESTIONNAIRE_DISPLAY_FORMS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"questionnaire_display_form 取值不合法：{display_form}，"
                f"允许值：{sorted(ALLOWED_QUESTIONNAIRE_DISPLAY_FORMS)}"
            ),
        )


def _validate_navigate_url(btn_type: Optional[str], external_url: Optional[str]) -> None:
    """[PRD-AICHAT-FUNCBTN-OPTIM-V1] 页面跳转地址校验：必须 http(s):// 或 / 开头。

    仅当 button_type=page_navigate 且 external_url 非空时才校验，避免对老类型误伤。
    """
    if btn_type != "page_navigate":
        return
    if not external_url:
        return
    s = (external_url or "").strip()
    if not (s.startswith("http://") or s.startswith("https://") or s.startswith("/") or s.startswith("pages/")):
        raise HTTPException(
            status_code=400,
            detail="页面跳转地址必须以 http(s):// 或 / 或 pages/ 开头",
        )


async def _validate_button_prompt_binding(
    db: AsyncSession,
    button_type: Optional[str],
    prompt_template_id: Optional[int],
) -> None:
    """[PRD-PROMPT-CONFIG-V1 2026-05-14] 校验 button_type 与 prompt_template_id 的绑定关系。

    规则：
    - 如果未提供 prompt_template_id：跳过校验
    - 否则：查 PromptTemplate -> 查 PromptTypeConfig -> 校验 button_type 在 allowed_button_types 中
    - 配置缺失（兜底）：放行，避免误伤历史数据
    """
    if not prompt_template_id or not button_type:
        return
    tpl = await db.get(PromptTemplate, prompt_template_id)
    if not tpl:
        raise HTTPException(status_code=400, detail=f"prompt_template_id={prompt_template_id} 不存在")
    cfg_res = await db.execute(
        select(PromptTypeConfig).where(PromptTypeConfig.type_key == tpl.prompt_type)
    )
    cfg = cfg_res.scalar_one_or_none()
    if not cfg:
        # 配置缺失视为兜底放行（不阻断写入）
        return
    allowed = list(cfg.allowed_button_types or [])
    if allowed and button_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"按钮类型 {button_type} 不允许绑定 Prompt 类型 {tpl.prompt_type}"
                f"（允许的按钮类型：{allowed}）"
            ),
        )


@admin_router.post("/function-buttons", response_model=ChatFunctionButtonResponse)
async def admin_create_button(
    data: ChatFunctionButtonCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    _validate_button_type(data.button_type)
    _validate_ai_function_type(data.button_type, data.ai_function_type)
    _validate_navigate_url(data.button_type, data.external_url)
    _validate_questionnaire_and_capture(
        data.button_type,
        data.ai_function_type,
        data.questionnaire_template_id,
        data.capture_purpose,
    )
    _validate_questionnaire_display_form(
        data.ai_function_type, data.questionnaire_display_form,
    )
    await _validate_button_prompt_binding(db, data.button_type, data.prompt_template_id)
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

    _validate_button_type(data.button_type)
    # 计算更新后的有效 button_type / prompt_template_id（取请求里有值的覆盖现有）
    updates = data.model_dump(exclude_unset=True)
    effective_btn_type = updates.get("button_type", btn.button_type)
    effective_pt_id = updates.get("prompt_template_id", btn.prompt_template_id)
    effective_ai_fn_type = updates.get("ai_function_type", btn.ai_function_type)
    effective_external_url = updates.get("external_url", btn.external_url)
    _validate_ai_function_type(effective_btn_type, effective_ai_fn_type)
    _validate_navigate_url(effective_btn_type, effective_external_url)
    effective_qt_id = updates.get(
        "questionnaire_template_id", btn.questionnaire_template_id
    )
    effective_cp = updates.get("capture_purpose", btn.capture_purpose)
    _validate_questionnaire_and_capture(
        effective_btn_type, effective_ai_fn_type, effective_qt_id, effective_cp
    )
    effective_display_form = updates.get(
        "questionnaire_display_form", btn.questionnaire_display_form
    )
    _validate_questionnaire_display_form(effective_ai_fn_type, effective_display_form)
    await _validate_button_prompt_binding(db, effective_btn_type, effective_pt_id)
    for field, value in updates.items():
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


# ────────────────────────────────────────
#  [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 快速切换接口
#  快速切换"是否推荐"/"是否胶囊"，点一下立即生效，无二次确认
# ────────────────────────────────────────


class _ToggleValue(BaseModel):
    value: bool


@admin_router.patch("/function-buttons/{button_id}/toggle-recommended")
async def admin_toggle_recommended(
    button_id: int,
    payload: _ToggleValue,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChatFunctionButton).where(ChatFunctionButton.id == button_id))
    btn = result.scalar_one_or_none()
    if not btn:
        raise HTTPException(status_code=404, detail="按钮不存在")
    btn.is_recommended = bool(payload.value)
    await db.flush()
    return {"id": btn.id, "is_recommended": bool(btn.is_recommended)}


@admin_router.patch("/function-buttons/{button_id}/toggle-capsule")
async def admin_toggle_capsule(
    button_id: int,
    payload: _ToggleValue,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChatFunctionButton).where(ChatFunctionButton.id == button_id))
    btn = result.scalar_one_or_none()
    if not btn:
        raise HTTPException(status_code=404, detail="按钮不存在")
    btn.is_capsule = bool(payload.value)
    await db.flush()
    return {"id": btn.id, "is_capsule": bool(btn.is_capsule)}


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


# [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 单按钮原子排序操作（置顶/上移/下移）
@admin_router.post("/function-buttons/sort-action")
async def admin_sort_button_action(
    data: ButtonSortActionRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """对单个按钮在指定视图（grid/capsule）执行 top/up/down 排序操作。

    实现策略：
      - 先按 view_type 过滤出所属视图的全部按钮列表（按对应 *_sort 升序）
      - 在内存里调整目标按钮的位置（置顶 / 上移 / 下移）
      - 然后把整个视图重排为 1,2,3,... 写回数据库（避免 NULL / 同值问题）
    """
    vt = (data.view_type or "").lower()
    if vt not in ("grid", "capsule"):
        raise HTTPException(status_code=400, detail="view_type 只能是 grid 或 capsule")
    if data.action not in ("top", "up", "down"):
        raise HTTPException(status_code=400, detail="action 只能是 top / up / down")

    if vt == "grid":
        flag_col = ChatFunctionButton.is_recommended
        sort_col = ChatFunctionButton.grid_sort
    else:
        flag_col = ChatFunctionButton.is_capsule
        sort_col = ChatFunctionButton.capsule_sort

    res = await db.execute(
        select(ChatFunctionButton)
        .where(flag_col == True)  # noqa: E712
        .order_by(func.coalesce(sort_col, 999999).asc(), ChatFunctionButton.id.asc())
    )
    rows = list(res.scalars().all())
    ids = [r.id for r in rows]
    try:
        idx = ids.index(data.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="该按钮不在当前视图（请先在编辑里开启对应开关）")

    if data.action == "top":
        if idx > 0:
            target = rows.pop(idx)
            rows.insert(0, target)
    elif data.action == "up":
        if idx > 0:
            rows[idx - 1], rows[idx] = rows[idx], rows[idx - 1]
        else:
            raise HTTPException(status_code=400, detail="已经是第一行，无法上移")
    elif data.action == "down":
        if idx < len(rows) - 1:
            rows[idx], rows[idx + 1] = rows[idx + 1], rows[idx]
        else:
            raise HTTPException(status_code=400, detail="已经是最后一行，无法下移")

    # 重排序号 1..N 写回
    for i, btn in enumerate(rows, start=1):
        if vt == "grid":
            btn.grid_sort = i
        else:
            btn.capsule_sort = i
    await db.flush()
    return {
        "message": "排序更新成功",
        "view_type": vt,
        "ordered_ids": [b.id for b in rows],
    }


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
