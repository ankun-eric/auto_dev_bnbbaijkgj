"""
[2026-04-23 v1.2] 用药参考功能优化：对话页首条消息 API

- POST /api/chat/drug/init : 进入用药对话页时下发首条 AI 建议（单药 4 段 / 多药双卡片）
- POST /api/chat/drug/regenerate_opening : 重新生成首条建议（10s 幂等防抖）
- 融合卡片平铺规范 v1.2：drug_list ≤ 2
"""
import json
import time
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    AllergyRecord,
    ChatMessage,
    ChatSession,
    DrugIdentifyDetail,
    FamilyMember,
    HealthProfile,
    MedicalHistory,
    MedicationRecord,
    MessageRole,
    MessageType,
    PromptTemplate,
    User,
)
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/drug", tags=["用药对话v1.2"])

# 多药对比最多 2 个药品
MAX_DRUGS_PER_SESSION = 2
# 重新生成幂等防抖间隔（秒）
REGENERATE_DEBOUNCE_SEC = 10

# 简易内存缓存用于防抖（生产建议改 Redis）
_regenerate_last_ts: Dict[int, float] = {}


# ──────────────── Schemas ────────────────


class DrugChatInitRequest(BaseModel):
    session_id: int
    member_id: Optional[int] = None


class DrugListItem(BaseModel):
    id: Optional[int] = None
    name: str
    image_url: Optional[str] = None


class MemberInfo(BaseModel):
    nickname: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    chronic_diseases: List[str] = []
    allergies: List[str] = []
    medications: List[str] = []
    pregnancy_status: Optional[str] = None
    relationship_type: Optional[str] = None


class OpeningMessage(BaseModel):
    message_id: int
    content_markdown: str
    generated_at: datetime


class DrugChatInitResponse(BaseModel):
    session_id: int
    member_info: MemberInfo
    drug_list: List[DrugListItem]
    opening_message: OpeningMessage


class RegenerateOpeningRequest(BaseModel):
    session_id: int


# ──────────────── 健康档案 6 项核心字段提取 ────────────────


def _calc_age(birthday: Any) -> Optional[int]:
    if not birthday:
        return None
    try:
        if isinstance(birthday, str):
            birthday = datetime.strptime(birthday, "%Y-%m-%d").date()
        if isinstance(birthday, datetime):
            birthday = birthday.date()
        today = date.today()
        return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    except Exception:
        return None


async def _build_member_info(
    db: AsyncSession, user_id: int, family_member_id: Optional[int]
) -> MemberInfo:
    """组装「健康档案注入字段」6 项核心：年龄/性别/慢性病史/过敏史/在用药/怀孕哺乳"""
    info = MemberInfo()

    # 家庭成员优先
    if family_member_id:
        fm_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == family_member_id)
        )
        fm = fm_result.scalar_one_or_none()
        if fm:
            info.nickname = fm.nickname or None
            info.age = _calc_age(fm.birthday)
            info.gender = fm.gender
            info.relationship_type = fm.relationship_type
            if fm.medical_histories:
                try:
                    mh = fm.medical_histories if isinstance(fm.medical_histories, list) else json.loads(fm.medical_histories)
                    info.chronic_diseases = [
                        (x.get("name") if isinstance(x, dict) else str(x)) for x in (mh or [])
                    ]
                except Exception:
                    pass
            if fm.allergies:
                try:
                    alg = fm.allergies if isinstance(fm.allergies, list) else json.loads(fm.allergies)
                    info.allergies = [
                        (x.get("name") if isinstance(x, dict) else str(x)) for x in (alg or [])
                    ]
                except Exception:
                    pass

    # 本人档案
    if not info.nickname:
        hp_result = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == user_id)
        )
        hp = hp_result.scalar_one_or_none()
        if hp:
            info.nickname = info.nickname or "本人"
            info.gender = info.gender or hp.gender
            if info.age is None:
                info.age = _calc_age(hp.birthday)

        alg_result = await db.execute(
            select(AllergyRecord).where(AllergyRecord.user_id == user_id)
        )
        allergies = alg_result.scalars().all()
        if allergies and not info.allergies:
            info.allergies = [f"{a.allergy_name}" for a in allergies]

        mh_result = await db.execute(
            select(MedicalHistory).where(MedicalHistory.user_id == user_id)
        )
        mhs = mh_result.scalars().all()
        if mhs and not info.chronic_diseases:
            info.chronic_diseases = [h.disease_name for h in mhs]

    # 在用药（来自 medication_records）
    med_result = await db.execute(
        select(MedicationRecord).where(
            MedicationRecord.user_id == user_id, MedicationRecord.status == "active"
        )
    )
    meds = med_result.scalars().all()
    info.medications = [m.medicine_name for m in meds]

    return info


async def _get_session_drugs(
    db: AsyncSession, session_id: int, user_id: int
) -> List[DrugListItem]:
    """取该 session 关联的药品列表（最多 2 个）"""
    result = await db.execute(
        select(DrugIdentifyDetail)
        .where(
            DrugIdentifyDetail.session_id == session_id,
            DrugIdentifyDetail.user_id == user_id,
        )
        .order_by(DrugIdentifyDetail.id.asc())
        .limit(MAX_DRUGS_PER_SESSION)
    )
    drugs = []
    for r in result.scalars().all():
        drugs.append(
            DrugListItem(
                id=r.id,
                name=r.drug_name or "未知药品",
                image_url=r.original_image_url,
            )
        )
    return drugs


# ──────────────── Prompt 组装 ────────────────


def _format_member_info_text(info: MemberInfo) -> str:
    parts = []
    if info.nickname:
        parts.append(f"- 昵称: {info.nickname}")
    if info.age is not None:
        parts.append(f"- 年龄: {info.age}岁")
    if info.gender:
        parts.append(f"- 性别: {info.gender}")
    parts.append(f"- 慢性病史: {', '.join(info.chronic_diseases) if info.chronic_diseases else '无'}")
    parts.append(f"- 过敏史: {', '.join(info.allergies) if info.allergies else '无'}")
    parts.append(f"- 正在服用药物: {', '.join(info.medications) if info.medications else '无'}")
    if info.pregnancy_status:
        parts.append(f"- 怀孕/哺乳状态: {info.pregnancy_status}")
    return "\n".join(parts)


def _format_drug_list_text(drugs: List[DrugListItem]) -> str:
    if not drugs:
        return "（无）"
    return "\n".join(f"{i + 1}. {d.name}" for i, d in enumerate(drugs))


DEFAULT_SINGLE_PROMPT = """你是一位资深药师AI，面向中老年用户。请基于用户的健康档案和所识别的药品信息，按以下 4 段式结构生成 Markdown 格式的用药首条建议：

【这个药是什么】一句话说清药名和主要作用
【您能吃吗】✅ / ⚠️ / ❌ + 结合健康档案的判断
【怎么吃】用法用量，通俗易懂
【⚠️ 特别提醒】结合慢性病/过敏/在用药提示注意点

要求：
- 每段 30 字以内，一目了然
- 面向中老年，不使用专业术语，必须通俗易懂
- 涉及处方药、孕妇/哺乳、危急情况请明确提示「请咨询医生」
- 结尾附：\\n\\n---\\n🔄 重新生成这条建议
"""


DEFAULT_MULTI_PROMPT = """你是一位资深药师AI，面向中老年用户。本次用户上传了 2 个药品进行对比，请基于用户的健康档案，按以下 Markdown 结构生成首条建议：

## 💊 药品 1：{药品1名}
【这个药是什么】…
【您能吃吗】…
【怎么吃】…
【⚠️ 特别提醒】…

## 💊 药品 2：{药品2名}
【这个药是什么】…
【您能吃吗】…
【怎么吃】…
【⚠️ 特别提醒】…

## 🔄 一起吃要注意
- 相互作用 / 服药间隔 / 禁忌搭配

## 📝 给您的综合建议
- 2-3 句总结

结尾附：\\n\\n---\\n🔄 重新生成这条建议
"""


async def _get_prompt_template(db: AsyncSession, prompt_type: str, default: str) -> str:
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    tpl = result.scalar_one_or_none()
    return tpl.content if tpl else default


async def _generate_opening_markdown(
    db: AsyncSession, drugs: List[DrugListItem], member_info: MemberInfo
) -> str:
    """调用 AI 生成首条建议 Markdown（单药 / 多药）"""
    is_multi = len(drugs) >= 2

    if is_multi:
        system_prompt = await _get_prompt_template(db, "drug_chat_opening_multi", DEFAULT_MULTI_PROMPT)
    else:
        system_prompt = await _get_prompt_template(db, "drug_chat_opening_single", DEFAULT_SINGLE_PROMPT)

    # 占位符替换
    system_prompt = system_prompt.replace("{member_info}", _format_member_info_text(member_info))
    system_prompt = system_prompt.replace("{drug_list}", _format_drug_list_text(drugs))

    user_content = (
        f"咨询对象健康档案：\n{_format_member_info_text(member_info)}\n\n"
        f"本次识别药品：\n{_format_drug_list_text(drugs)}\n\n"
        f"请按系统提示词的结构输出用药建议。"
    )

    try:
        raw = await call_ai_model(
            [{"role": "user", "content": user_content}], system_prompt, db
        )
        text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        # 兜底：若返回内容未包含重新生成链接，自动追加
        if "🔄 重新生成这条建议" not in text:
            text = text.rstrip() + "\n\n---\n🔄 重新生成这条建议"
        return text
    except Exception as e:
        logger.exception("生成用药首条建议失败")
        return (
            "AI 正在思考…遇到问题请点🔄 重试\n\n"
            f"（错误详情：{str(e)[:80]}）\n\n---\n🔄 重新生成这条建议"
        )


# ──────────────── 接口 ────────────────


@router.post("/init", response_model=DrugChatInitResponse)
async def drug_chat_init(
    body: DrugChatInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 校验 session
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == body.session_id, ChatSession.user_id == current_user.id
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 取药品列表（≤2）
    drugs = await _get_session_drugs(db, body.session_id, current_user.id)
    if len(drugs) > MAX_DRUGS_PER_SESSION:
        raise HTTPException(
            status_code=400,
            detail=f"多药对比最多 {MAX_DRUGS_PER_SESSION} 个药品",
        )

    # 3. 组装 member_info
    member_id = body.member_id or session.family_member_id
    member_info = await _build_member_info(db, current_user.id, member_id)

    # 4. 检查是否已有首条 assistant 消息，有则复用
    existing_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == body.session_id,
            ChatMessage.role == MessageRole.assistant,
        )
        .order_by(ChatMessage.created_at.asc())
        .limit(1)
    )
    existing_msg = existing_result.scalar_one_or_none()

    if existing_msg:
        opening = OpeningMessage(
            message_id=existing_msg.id,
            content_markdown=existing_msg.content,
            generated_at=existing_msg.created_at,
        )
    else:
        # 5. 生成首条消息
        content = await _generate_opening_markdown(db, drugs, member_info)
        new_msg = ChatMessage(
            session_id=body.session_id,
            role=MessageRole.assistant,
            content=content,
            message_type=MessageType.text,
            message_metadata={"source": "drug_chat_opening", "drug_count": len(drugs)},
        )
        db.add(new_msg)
        session.message_count = (session.message_count or 0) + 1
        await db.flush()
        await db.refresh(new_msg)
        opening = OpeningMessage(
            message_id=new_msg.id,
            content_markdown=new_msg.content,
            generated_at=new_msg.created_at,
        )

    return DrugChatInitResponse(
        session_id=body.session_id,
        member_info=member_info,
        drug_list=drugs,
        opening_message=opening,
    )


@router.post("/regenerate_opening", response_model=OpeningMessage)
async def regenerate_opening(
    body: RegenerateOpeningRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 幂等防抖检查（10s）
    now = time.time()
    last = _regenerate_last_ts.get(body.session_id, 0)
    if now - last < REGENERATE_DEBOUNCE_SEC:
        raise HTTPException(status_code=429, detail=f"请求过快，请等待 {REGENERATE_DEBOUNCE_SEC} 秒后重试")
    _regenerate_last_ts[body.session_id] = now

    # 2. 校验 session
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == body.session_id, ChatSession.user_id == current_user.id
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 3. 取药品 + member_info
    drugs = await _get_session_drugs(db, body.session_id, current_user.id)
    member_info = await _build_member_info(db, current_user.id, session.family_member_id)

    # 4. 重新生成
    content = await _generate_opening_markdown(db, drugs, member_info)

    # 5. 更新首条 assistant 消息（若存在）或新增
    existing_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == body.session_id,
            ChatMessage.role == MessageRole.assistant,
        )
        .order_by(ChatMessage.created_at.asc())
        .limit(1)
    )
    existing_msg = existing_result.scalar_one_or_none()

    if existing_msg:
        existing_msg.content = content
        existing_msg.created_at = datetime.utcnow()
        existing_msg.message_metadata = {
            "source": "drug_chat_opening",
            "drug_count": len(drugs),
            "regenerated": True,
        }
        await db.flush()
        return OpeningMessage(
            message_id=existing_msg.id,
            content_markdown=content,
            generated_at=existing_msg.created_at,
        )
    else:
        new_msg = ChatMessage(
            session_id=body.session_id,
            role=MessageRole.assistant,
            content=content,
            message_type=MessageType.text,
            message_metadata={"source": "drug_chat_opening", "drug_count": len(drugs), "regenerated": True},
        )
        db.add(new_msg)
        session.message_count = (session.message_count or 0) + 1
        await db.flush()
        await db.refresh(new_msg)
        return OpeningMessage(
            message_id=new_msg.id,
            content_markdown=content,
            generated_at=new_msg.created_at,
        )


# ──────────────── drug_query 上下文注入辅助函数（供 chat.py 使用） ────────────────


async def inject_drug_context_to_prompt(
    db: AsyncSession, session: ChatSession, base_prompt: str, user_id: int
) -> str:
    """为 drug_query 类型会话注入 {member_info} + {drug_list} 到 prompt 模板中。
    供 chat.py 在组装后端消息上下文时调用。"""
    try:
        drugs = await _get_session_drugs(db, session.id, user_id)
        member_info = await _build_member_info(db, user_id, session.family_member_id)
        out = base_prompt
        if "{member_info}" in out:
            out = out.replace("{member_info}", _format_member_info_text(member_info))
        else:
            out = out + "\n\n【咨询对象健康档案】\n" + _format_member_info_text(member_info)
        if "{drug_list}" in out:
            out = out.replace("{drug_list}", _format_drug_list_text(drugs))
        else:
            out = out + "\n\n【本次药品列表】\n" + _format_drug_list_text(drugs)
        return out
    except Exception:
        logger.exception("inject_drug_context_to_prompt 失败，返回原 prompt")
        return base_prompt
