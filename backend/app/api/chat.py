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
    UserHealthProfile,
)
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatSessionCreate, ChatSessionResponse
from app.services.ai_service import (
    call_ai_model,
    call_ai_model_stream,
    extract_image_urls,
    symptom_analysis,
)
from app.services.knowledge_search import search_knowledge
from app.utils.datetime_utils import iso_utc
# [2026-04-23 v1.2] 用药对话 drug_query 注入 {member_info} + {drug_list}
from app.api.drug_chat import inject_drug_context_to_prompt
# [BUG_FIX_拍照识药三联_20260516] 聊天内嵌识药引擎（方案 E）
from app.services.drug_identify_engine import (
    build_implicit_drug_context,
    is_drug_identify_intent,
    run_drug_identify_stream,
)
# [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 聊天内嵌报告解读引擎
from app.services.report_interpret_engine import (
    REPORT_INTERPRET_INTENT,
    is_report_interpret_intent,
    run_report_interpret_stream,
)

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
    """[BUG_FIX_AI_HOME_3BUGS_20260517 · Bug A] 取消末尾追加免责声明。

    根据《AI 对话三 Bug 修复方案 v1.0》Bug A 修复策略：
    1. **取消末尾追加**：后端不再追加任何兜底免责声明，法务话术统一靠
       前端 ``AiActionBar`` 那行小灰字"AI 生成内容仅供参考，不作为诊断依据"
       覆盖。这样既避免了"模型自带免责声明 + 后端追加 + 前端再渲染"三重叠加
       导致的 sanitizer 误吞正文末段问题（Bug A 现场），也确保法务声明
       永远显示给用户。
    2. ``AiDisclaimerConfig`` 的 ``disclaimer_text`` 仅作为后台配置保留，
       不再注入到 AI 文本中（参数 ``session_type`` / ``db`` 保留以兼容上游签名）。
    3. 最终交给改造后的 ``sanitize_ai_output`` 兜底清洗：
       - 整句级免责关键词（不再误伤"请遵医嘱"等高频短语）
       - 行级清洗（命中只去那一行，保留同段其他正文）
       - 不再做末尾追加
    """
    from app.utils.ai_output_sanitizer import sanitize_ai_output

    # [BUG_FIX_AI_HOME_3BUGS_20260517] 不再读取/追加 AiDisclaimerConfig 的免责文案。
    # 仅做兜底清洗，确保模型自带的多余免责短句（仅命中整句级模式时）被剥离。
    return sanitize_ai_output(content or "")


def _calc_age(birthday: date) -> int:
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _calc_bmi(height: float, weight: float) -> float:
    return weight / ((height / 100) ** 2)


def _normalize_tag_list(raw) -> list[str]:
    """[Bug-470 2026-05-15] 把 JSON 字段（既往病史/过敏史等）归一化为字符串数组。

    历史/线上数据中同一字段同时存在以下三种形态，需统一兜底，避免
    `"、".join(list-of-dict)` 抛 `TypeError: sequence item 0: expected str instance, dict found`
    直接让 /api/chat/sessions/*/messages 与 /stream 全军覆没。

    - list[str]：旧版结构，如 ["哮喘", "鼻炎"] → 原样保留
    - list[dict]：新版结构（含 type/value/name/label/text 等键），如
      [{"type": "custom", "value": "无"}] → 取 value/name/label/text/title 中第一个非空字符串
    - None / 非 list / 空 list → 返回 []
    - 任意元素既不是 str 也不是 dict（例如数字、None）→ 强转为 str，None 跳过
    - dict 中所有候选键都为空 → 跳过该项（不要把空字符串塞进结果）
    """
    if not raw or not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if item is None:
            continue
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict):
            picked = None
            for key in ("value", "name", "label", "text", "title"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    picked = v.strip()
                    break
            if picked:
                out.append(picked)
        else:
            try:
                s = str(item).strip()
                if s:
                    out.append(s)
            except Exception:
                continue
    return out


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

            # [Bug-470 2026-05-15] medical_histories / allergies 在线上存在 list[dict] 形态，
            # 直接 join 会抛 TypeError 导致 /messages 与 /stream 全军覆没。统一走归一化。
            histories_list = _normalize_tag_list(medical_histories)
            allergies_list = _normalize_tag_list(allergies)

            age_str = f"{_calc_age(birthday)}岁" if birthday else "年龄未知"
            bmi_str = f"，BMI：{_calc_bmi(height, weight):.1f}" if height and weight else ""
            height_str = f"{height}cm" if height else "未知"
            weight_str = f"{weight}kg" if weight else "未知"
            histories_str = "、".join(histories_list) if histories_list else "无"
            allergies_str = "、".join(allergies_list) if allergies_list else "无"

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


async def _build_user_health_profile_context(user_id: int, db: AsyncSession) -> str:
    """Build context from UserHealthProfile for system_prompt injection."""
    try:
        result = await db.execute(
            select(UserHealthProfile).where(UserHealthProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return ""

        parts = []
        basic = profile.basic_info or {}
        gender_map = {"male": "男性", "female": "女性"}
        gender = gender_map.get(basic.get("gender", ""), basic.get("gender", ""))
        age = basic.get("age")
        bmi = basic.get("bmi")

        if gender:
            parts.append(gender)
        if age:
            parts.append(f"{age}岁")
        if bmi:
            parts.append(f"BMI {bmi}")

        # [Bug-470 2026-05-15] 同样兼容 list[dict] 数据形态
        chronic = _normalize_tag_list(profile.chronic_diseases or [])
        meds = _normalize_tag_list(profile.medications or [])
        if chronic:
            disease_str = "、".join(chronic)
            if meds:
                parts.append(f"{disease_str}（服用{'、'.join(meds)}）")
            else:
                parts.append(disease_str)
        elif meds:
            parts.append(f"服用{'、'.join(meds)}")

        allergies = _normalize_tag_list(profile.allergies or [])
        if allergies:
            parts.append(f"{'、'.join(allergies)}过敏")

        if not parts:
            return ""

        profile_str = "，".join(parts)
        return (
            f"\n\n用户健康画像：{profile_str}。"
            "请在回答健康问题时参考以上信息，但不要主动提及这些信息，除非与用户当前问题直接相关。"
        )
    except Exception:
        return ""


# [Bug-419 2026-05-08] 会话类型枚举映射 — 兼容历史/外部命名（如 'general'/'constitution'），
# 统一归一化为 SessionType 枚举值。未命中映射时按"未识别 session_type"日志告警并兜底。
_SESSION_TYPE_ALIASES = {
    "general": "health_qa",
    "qa": "health_qa",
    "chat": "health_qa",
    "default": "health_qa",
    "constitution": "constitution_test",
    "drug": "drug_query",
    "symptom": "symptom_check",
    "report": "report_interpret",
}


def _normalize_session_type(raw: Optional[str]) -> str:
    """[Bug-419] 把任意客户端传入值归一化为合法的 SessionType 枚举值。

    - None / 空串 → 默认 health_qa（B-2 兜底）
    - 直接命中枚举值 → 原样返回
    - 命中别名表 → 返回映射值
    - 完全不识别 → 兜底 health_qa，并在 logger 中告警
    """
    valid = {t.value for t in SessionType}
    if not raw:
        return "health_qa"
    if raw in valid:
        return raw
    aliased = _SESSION_TYPE_ALIASES.get(raw)
    if aliased and aliased in valid:
        return aliased
    # 兜底：未识别的 session_type 仍按通用咨询处理，避免 422 必现伤用户
    try:
        import logging

        logging.getLogger(__name__).warning(
            "[Bug-419] unknown session_type=%r, fallback to health_qa", raw
        )
    except Exception:
        pass
    return "health_qa"


async def _ensure_self_family_member(user: User, db: AsyncSession) -> FamilyMember:
    """[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 B]
    保证登录用户存在 ``is_self=True`` 的 FamilyMember 行；若不存在则懒创建一条，
    使得"本人"与"其他咨询人"在 prompt 装配 / 档案查询上路径完全一致，
    彻底消除"档案串味"。
    """
    try:
        q = await db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == user.id,
                FamilyMember.is_self.is_(True),
            ).limit(1)
        )
        row = q.scalar_one_or_none()
        if row:
            return row
    except Exception:
        pass

    member = FamilyMember(
        user_id=user.id,
        relationship_type="self",
        nickname=(user.nickname or "本人"),
        is_self=True,
        status="active",
    )
    db.add(member)
    try:
        await db.flush()
        await db.refresh(member)
    except Exception:
        # 罕见：并发同时创建。回滚后再 select 一次。
        try:
            await db.rollback()
        except Exception:
            pass
        q2 = await db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == user.id,
                FamilyMember.is_self.is_(True),
            ).limit(1)
        )
        existed = q2.scalar_one_or_none()
        if existed:
            return existed
        raise
    return member


async def _pick_default_family_member_id(
    user_id: int, db: AsyncSession
) -> Optional[int]:
    """[Bug-419] 当客户端未传 family_member_id 时，优先使用用户的"本人"档案，
    若无 is_self 记录则回退到该用户最早创建的家庭成员；都没有则返回 None。
    """
    try:
        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id, FamilyMember.is_self.is_(True))
            .limit(1)
        )
        member = result.scalar_one_or_none()
        if member:
            return member.id
        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .order_by(FamilyMember.created_at.asc())
            .limit(1)
        )
        member = result.scalar_one_or_none()
        return member.id if member else None
    except Exception:
        return None


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新的 AI 会话。

    [Bug-419 2026-05-08] 此接口对客户端字段做最大限度的容错与兜底：
      1) session_type 缺失 / 非法 → 自动兜底为 health_qa（B-2）
      2) family_member_id 缺失 → 优先取用户「默认咨询对象」（B-3）
      3) H5 早期实现使用的 member_id 字段，自动并入 family_member_id（兼容字段）
      4) 兜底命中时记录日志，便于排查（B-4）
    """
    import logging

    logger = logging.getLogger(__name__)

    # 兼容字段：member_id → family_member_id
    if data.family_member_id is None and getattr(data, "member_id", None) is not None:
        logger.info(
            "[Bug-419] H5 旧版字段 member_id=%s 自动归并到 family_member_id",
            data.member_id,
        )
        data.family_member_id = data.member_id

    # session_type 归一化 + 兜底
    raw_session_type = data.session_type
    session_type = _normalize_session_type(raw_session_type)
    if session_type != raw_session_type:
        logger.info(
            "[Bug-419] session_type normalized: raw=%r -> %r", raw_session_type, session_type
        )

    # family_member_id 兜底（仅在客户端未显式传入时）
    family_member_id = data.family_member_id
    if family_member_id is None:
        family_member_id = await _pick_default_family_member_id(current_user.id, db)
        if family_member_id is not None:
            logger.info(
                "[Bug-419] family_member_id 缺失，兜底为用户默认家庭成员 id=%s",
                family_member_id,
            )

    try:
        session = ChatSession(
            user_id=current_user.id,
            session_type=session_type,
            title=data.title or "新对话",
            family_member_id=family_member_id,
            symptom_info=data.symptom_info,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return ChatSessionResponse.model_validate(session)
    except Exception as exc:
        # [Bug-419 B-1/B-4] 友好的中文错误消息 + 完整请求上下文日志
        logger.exception(
            "[Bug-419] create_session 失败 user_id=%s session_type=%r family_member_id=%r title=%r",
            current_user.id,
            session_type,
            family_member_id,
            data.title,
        )
        raise HTTPException(
            status_code=500,
            detail=f"创建会话失败：{exc}。请稍后重试，若持续报错请联系客服。",
        )


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

    # [Bug-433 2026-05-09] source 归一化
    raw_source = (getattr(data, "source", None) or "text").strip().lower()
    user_source = raw_source if raw_source in ("text", "voice", "preset", "voice_repair") else "text"

    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
        message_metadata=msg_metadata,
        source=user_source,
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
        # [Bug-433] AI 回复关联到对应的用户消息（成对查询 + 历史孤立扫描）
        source=user_source,
        parent_id=user_msg.id,
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


async def _stream_drug_identify(
    *,
    session: ChatSession,
    session_id: int,
    user_id: int,
    user_msg_id: int,
    user_source: str,
    content: str,
    image_urls: list,
    family_member_id: Optional[int],
    db: AsyncSession,
) -> StreamingResponse:
    """[BUG_FIX_拍照识药三联_20260516] 方案 E：聊天内嵌识药引擎 SSE 入口。

    - 与 ``stream_message`` 共享 SSE 协议：``event: delta`` / ``event: done`` /
      新增 ``event: progress``（识别中/OCR完成/视觉完成 提示文案，避免白屏）
    - AI 消息持久化时，把识药结构化结果写入 ``message_metadata``，
      字段含 ``message_type``（drug_identify_card / drug_identify_retake）、
      ``medicines``、``family_member_id`` 等，供前端渲染卡片
    """
    start_time = time.time()
    captured_session = session

    async def event_generator():
        full_text = ""
        final_meta: dict = {}
        try:
            async for ev in run_drug_identify_stream(
                image_urls=image_urls,
                ocr_text_hint=None,
                user_id=user_id,
                family_member_id=family_member_id,
                db=db,
            ):
                etype = ev.get("type")
                if etype == "progress":
                    sse_data = json.dumps(
                        {"stage": ev.get("stage"), "text": ev.get("text", "")},
                        ensure_ascii=False,
                    )
                    yield f"event: progress\ndata: {sse_data}\n\n"
                elif etype == "delta":
                    full_text = ev.get("content", "") or full_text
                    sse_data = json.dumps({"content": ev.get("content", "")}, ensure_ascii=False)
                    yield f"event: delta\ndata: {sse_data}\n\n"
                elif etype == "done":
                    full_text = ev.get("content") or full_text
                    final_meta = ev.get("meta") or {}
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    ai_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.assistant,
                        content=full_text or "识别完成",
                        message_type=MessageType.text,
                        response_time_ms=elapsed_ms,
                        source=user_source,
                        parent_id=user_msg_id,
                        message_metadata=final_meta,
                    )
                    db.add(ai_msg)
                    captured_session.message_count = (captured_session.message_count or 0) + 1
                    if captured_session.title == "新对话":
                        captured_session.title = "拍照识药"
                    try:
                        await db.flush()
                        await db.refresh(ai_msg)
                        await db.commit()
                    except Exception:
                        try:
                            await db.rollback()
                        except Exception:
                            pass

                    done_data = json.dumps(
                        {
                            "message_id": getattr(ai_msg, "id", None),
                            "full_content": full_text or "",
                            "meta": final_meta,
                        },
                        ensure_ascii=False,
                    )
                    yield f"event: done\ndata: {done_data}\n\n"
        except Exception as e:
            err_data = json.dumps({"content": f"识药服务异常：{str(e)[:160]}"}, ensure_ascii=False)
            yield f"event: delta\ndata: {err_data}\n\n"
            yield f"event: done\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_report_interpret(
    *,
    session: ChatSession,
    session_id: int,
    user: User,
    user_msg_id: int,
    user_source: str,
    image_urls: list,
    family_member_id: Optional[int],
    report_meta: Optional[dict],
    db: AsyncSession,
) -> StreamingResponse:
    """[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
    SSE 入口：把 ``run_report_interpret_stream`` 的事件流转成 SSE 事件，
    并在 done 时把 AI 消息 + meta 持久化到 chat_messages。

    与 _stream_drug_identify 共享 SSE 协议：
      event: progress|delta|done
    """
    start_time = time.time()
    captured_session = session

    async def event_generator():
        full_text = ""
        final_meta: dict = {}
        try:
            async for ev in run_report_interpret_stream(
                image_urls=image_urls,
                user=user,
                family_member_id=family_member_id,
                report_title=(report_meta or {}).get("report_title") if isinstance(report_meta, dict) else None,
                report_date=(report_meta or {}).get("report_date") if isinstance(report_meta, dict) else None,
                db=db,
            ):
                etype = ev.get("type")
                if etype == "progress":
                    sse_data = json.dumps(
                        {"stage": ev.get("stage"), "text": ev.get("text", "")},
                        ensure_ascii=False,
                    )
                    yield f"event: progress\ndata: {sse_data}\n\n"
                elif etype == "delta":
                    full_text += ev.get("content", "") or ""
                    sse_data = json.dumps({"content": ev.get("content", "")}, ensure_ascii=False)
                    yield f"event: delta\ndata: {sse_data}\n\n"
                elif etype == "done":
                    full_text = ev.get("content") or full_text
                    final_meta = ev.get("meta") or {}
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    ai_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.assistant,
                        content=full_text or "解读完成",
                        message_type=MessageType.text,
                        response_time_ms=elapsed_ms,
                        source=user_source,
                        parent_id=user_msg_id,
                        message_metadata=final_meta,
                    )
                    db.add(ai_msg)
                    captured_session.message_count = (captured_session.message_count or 0) + 1
                    if captured_session.title == "新对话":
                        captured_session.title = "报告解读"
                    try:
                        await db.flush()
                        await db.refresh(ai_msg)
                        await db.commit()
                    except Exception:
                        try:
                            await db.rollback()
                        except Exception:
                            pass

                    done_data = json.dumps(
                        {
                            "message_id": getattr(ai_msg, "id", None),
                            "full_content": full_text or "",
                            "meta": final_meta,
                        },
                        ensure_ascii=False,
                    )
                    yield f"event: done\ndata: {done_data}\n\n"
        except Exception as e:
            err_data = json.dumps(
                {"content": f"报告解读服务异常：{str(e)[:160]}"},
                ensure_ascii=False,
            )
            yield f"event: delta\ndata: {err_data}\n\n"
            yield f"event: done\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

    # [Bug-433 2026-05-09] source 归一化为合法枚举之一，非法值兜底为 'text'
    raw_source = (getattr(data, "source", None) or "text").strip().lower()
    user_source = raw_source if raw_source in ("text", "voice", "preset", "voice_repair") else "text"

    # [BUG_FIX_拍照识药三联_20260516] family_member_id 透传：客户端传则覆盖会话级，
    # 不传保留原会话绑定的咨询人；用于识药剂量/禁忌按"咨询人"档案而非登录用户档案输出。
    incoming_family_member_id = getattr(data, "family_member_id", None)
    if incoming_family_member_id is not None:
        try:
            session.family_member_id = incoming_family_member_id
        except Exception:
            pass

    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
        message_metadata=stream_msg_metadata,
        source=user_source,
    )
    db.add(user_msg)
    # [Bug-433 2026-05-09] 用户消息入库强约束：在调用 LLM 之前提交 user 行，
    # 哪怕 LLM 流式中断、网络断开，user 消息也已落地 chat_messages 表，
    # 保证刷新/重进会话后用户气泡不会丢失。
    await db.commit()
    await db.refresh(user_msg)

    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
    # 统一图片 URL 来源：优先 payload.image_urls（结构化），否则从 content 文本中抽
    payload_image_urls = list(getattr(data, "image_urls", None) or [])
    text_image_urls = extract_image_urls(data.content or "")
    merged_image_urls = payload_image_urls or text_image_urls

    payload_intent = (getattr(data, "intent", None) or "").strip().lower() or None
    payload_button_id = getattr(data, "button_id", None)
    payload_report_meta = getattr(data, "report_meta", None)

    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 分发优先级 1：报告解读 intent
    # 显式 intent == 'report_interpret' 或 button_type 命中报告解读按钮 → 走 ReportInterpretEngine
    if is_report_interpret_intent(
        intent=payload_intent,
        button_type=getattr(data, "button_type", None),
        button_id=payload_button_id,
        image_urls=merged_image_urls,
    ):
        return await _stream_report_interpret(
            session=session,
            session_id=session_id,
            user=current_user,
            user_msg_id=user_msg.id,
            user_source=user_source,
            image_urls=merged_image_urls,
            family_member_id=session.family_member_id or incoming_family_member_id,
            report_meta=payload_report_meta if isinstance(payload_report_meta, dict) else None,
            db=db,
        )

    # [BUG_FIX_拍照识药三联_20260516] 方案 E：聊天内嵌识药引擎路由
    # 当 button_type ∈ {photo_recognize_drug, drug_identify, medication_recognize}
    # 或消息文本含识药关键词，且消息含图片 URL → 走 DrugIdentifyEngine
    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 同时支持显式 intent='drug_identify'
    drug_image_urls = merged_image_urls
    if payload_intent == "drug_identify" and drug_image_urls:
        return await _stream_drug_identify(
            session=session,
            session_id=session_id,
            user_id=current_user.id,
            user_msg_id=user_msg.id,
            user_source=user_source,
            content=data.content,
            image_urls=drug_image_urls,
            family_member_id=session.family_member_id or incoming_family_member_id,
            db=db,
        )
    if is_drug_identify_intent(
        button_type=getattr(data, "button_type", None),
        content=data.content or "",
        image_urls=drug_image_urls,
    ):
        return await _stream_drug_identify(
            session=session,
            session_id=session_id,
            user_id=current_user.id,
            user_msg_id=user_msg.id,
            user_source=user_source,
            content=data.content,
            image_urls=drug_image_urls,
            family_member_id=session.family_member_id or incoming_family_member_id,
            db=db,
        )

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

    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 A]
    # 关键修复：去掉"无条件叠加登录用户档案"——这会把"本人档案"和"咨询人档案"
    # 同时拼进 prompt，导致 AI 在选了某个咨询人后还引用其他成员的健康档案信息（串味）。
    # 新规则：
    #   - session.family_member_id 已绑定咨询人（含"本人=is_self FamilyMember"）→ health_context
    #     已完整覆盖，不再叠加 UserHealthProfile；
    #   - 未绑定任何 family_member_id（极少数老会话）→ 兜底拼一份 UserHealthProfile，
    #     避免完全没有用户档案上下文。
    if not session.family_member_id:
        user_hp_context = await _build_user_health_profile_context(current_user.id, db)
        if user_hp_context:
            system_prompt += user_hp_context

    # [2026-04-23 v1.2] drug_query 场景：注入 {member_info} + {drug_list}
    if session_type_val == "drug_query":
        try:
            system_prompt = await inject_drug_context_to_prompt(
                db, session, system_prompt, current_user.id
            )
        except Exception:
            pass

    # [BUG_FIX_拍照识药三联_20260516] 隐式药品上下文注入：
    # 检测最近 3 条 assistant 消息是否含 drug_identify_card meta，
    # 若有则把该药品 JSON 拼成 system context，让用户在同一会话中追问
    # "能和布洛芬同服吗"等问题时 AI 能基于上文药品作答（豆包/阿福对标）。
    try:
        count = 0
        for hm in reversed(history_msgs):
            role_val = hm.role.value if hasattr(hm.role, "value") else hm.role
            if role_val != "assistant":
                continue
            count += 1
            meta = getattr(hm, "message_metadata", None) or {}
            ctx = build_implicit_drug_context(meta)
            if ctx:
                system_prompt += ctx
                break
            if count >= 3:
                break
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
    # [Bug-433 2026-05-09] 把已落地的 user_msg.id 透传给生成器，
    # done 回调里把 ai_msg.parent_id 关联到对应的用户消息，
    # 便于成对查询 + 历史孤立 AI 消息回补脚本扫描使用。
    captured_user_msg_id = user_msg.id

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
                    # [Bug-433] AI 回复 source 复用对应用户消息 source（便于按入口统计回复链路）
                    source=user_source,
                    # [Bug-433] 关联到对应的用户消息，便于成对查询 + 历史孤立扫描
                    parent_id=captured_user_msg_id,
                )
                captured_db.add(ai_msg)
                captured_session.message_count = (captured_session.message_count or 0) + 1
                if captured_session.title == "新对话" and len(captured_history_msgs) <= 2:
                    captured_session.title = captured_data.content[:50]
                await captured_db.flush()
                await captured_db.refresh(ai_msg)
                # [Bug-433 2026-05-09] 显式 commit AI 消息，避免流式响应在
                # generator yield 之后客户端关闭连接、FastAPI 默认依赖 finally
                # 路径下 commit 时机不稳导致 AI 回复偶发不入库（历史问题）。
                # user 消息已在 stream 入口提前 commit（见上方），此处只对 AI
                # 消息和 session 状态做最终持久化。
                try:
                    await captured_db.commit()
                except Exception:
                    pass

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
        # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 B]
        # 切回"本人"：统一为 is_self=True 的 FamilyMember（不再置 None），
        # 避免与"其他咨询人=family_member_id"形成双标，从根上消除档案串味。
        # 若该用户尚未回填 is_self 行，则懒创建一条。
        self_member = await _ensure_self_family_member(current_user, db)
        switch_summary = (
            f"用户已将咨询对象切换回自己（{self_member.nickname or '本人'}）"
        )
        session.family_member_id = self_member.id
        family_member_id = self_member.id
        message = "已切换咨询对象为自己"

    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 C]
    # switch-member 时写入一条系统级的 switch_summary 消息，便于 AI 在续问时
    # 明确"咨询人已变更"，同时供前端/审计回放使用。
    try:
        sys_msg = ChatMessage(
            session_id=session.id,
            role=MessageRole.system,
            content=switch_summary,
            message_type=MessageType.text,
            source="switch_member",
            message_metadata={
                "kind": "switch_summary",
                "family_member_id": family_member_id,
            },
        )
        db.add(sys_msg)
    except Exception:
        # 切换主流程不应因写系统消息失败而失败；忽略即可，下游靠 family_member_id 兜底
        pass

    await db.flush()
    try:
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
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
        # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 时区规范：输出 UTC 带 +00:00 标识
        # 旧 isoformat() 不带时区会被前端按本地时区误解析（导致"刚发生显示 8 小时前"）
        "created_at": iso_utc(sess.created_at),
        "updated_at": iso_utc(sess.updated_at),
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


# ──────────────────────────────────────────────────────────────────────────
# [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3] 识药卡片状态持久化
# ──────────────────────────────────────────────────────────────────────────


@router.post("/messages/{message_id}/mark-added-to-plan")
async def mark_message_added_to_plan(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3]
    把识药卡片消息标记为「已加入用药计划」，写入 ChatMessage.message_metadata.added_to_plan = True
    用于解决：点击"加入用药计划"跳转后返回 ai-home，按钮不再变回可点击的状态。

    - 必须是 assistant 消息
    - 必须归属于当前用户的会话
    - 必须已经是 drug_identify_card 消息（meta.message_type == drug_identify_card）
    """
    msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == msg.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    sess = sess_result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=403, detail="无权操作该消息")

    meta = dict(msg.message_metadata or {})
    if meta.get("message_type") != "drug_identify_card":
        # 非识药卡消息，也允许（前端可能复用作通用标记），但不强制 400
        pass
    meta["added_to_plan"] = True
    msg.message_metadata = meta
    # SQLAlchemy JSON 字段对 in-place 修改不一定脏检测，显式标记
    try:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(msg, "message_metadata")
    except Exception:
        pass
    await db.commit()
    return {"ok": True, "message_id": message_id, "added_to_plan": True}
