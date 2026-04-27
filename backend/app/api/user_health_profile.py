import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, get_db
from app.core.security import get_current_user
from app.models.models import ChatMessage, ChatSession, User, UserHealthProfile
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["用户健康画像"])


class HealthProfileUpdate(BaseModel):
    basic_info: Optional[dict] = None
    chronic_diseases: Optional[list] = None
    allergies: Optional[list] = None
    medications: Optional[list] = None
    family_history: Optional[list] = None
    focus_areas: Optional[list] = None


class ExtractRequest(BaseModel):
    session_id: str


@router.get("/health-profile")
async def get_health_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserHealthProfile).where(UserHealthProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {
            "code": 200,
            "data": {
                "basic_info": {},
                "chronic_diseases": [],
                "allergies": [],
                "medications": [],
                "family_history": [],
                "focus_areas": [],
                "last_updated": None,
            },
        }
    return {
        "code": 200,
        "data": {
            "basic_info": profile.basic_info or {},
            "chronic_diseases": profile.chronic_diseases or [],
            "allergies": profile.allergies or [],
            "medications": profile.medications or [],
            "family_history": profile.family_history or [],
            "focus_areas": profile.focus_areas or [],
            "last_updated": profile.updated_at.isoformat() + "Z" if profile.updated_at else None,
        },
    }


@router.put("/health-profile")
async def update_health_profile(
    data: HealthProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserHealthProfile).where(UserHealthProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserHealthProfile(user_id=current_user.id)
        db.add(profile)

    if data.basic_info is not None:
        profile.basic_info = data.basic_info
    if data.chronic_diseases is not None:
        profile.chronic_diseases = data.chronic_diseases
    if data.allergies is not None:
        profile.allergies = data.allergies
    if data.medications is not None:
        profile.medications = data.medications
    if data.family_history is not None:
        profile.family_history = data.family_history
    if data.focus_areas is not None:
        profile.focus_areas = data.focus_areas

    await db.flush()
    await db.refresh(profile)
    return {
        "code": 200,
        "data": {
            "basic_info": profile.basic_info or {},
            "chronic_diseases": profile.chronic_diseases or [],
            "allergies": profile.allergies or [],
            "medications": profile.medications or [],
            "family_history": profile.family_history or [],
            "focus_areas": profile.focus_areas or [],
            "last_updated": profile.updated_at.isoformat() + "Z" if profile.updated_at else None,
        },
    }


@router.post("/health-profile/extract")
async def extract_health_profile(
    data: ExtractRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_id = int(data.session_id) if data.session_id.isdigit() else None
    if session_id is None:
        raise HTTPException(status_code=400, detail="无效的 session_id")

    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    background_tasks.add_task(_extract_health_info_task, current_user.id, session_id)
    return {"code": 200, "message": "健康信息提取任务已启动"}


async def _extract_health_info_task(user_id: int, session_id: int):
    """Background task: extract health info from conversation via AI."""
    try:
        async with async_session() as db:
            msg_result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(50)
            )
            messages = msg_result.scalars().all()
            if not messages:
                return

            conversation = "\n".join(
                f"{'用户' if m.role.value == 'user' else 'AI'}: {m.content}"
                for m in messages
                if m.content
            )

            extract_prompt = (
                "请从以下对话中提取用户的健康相关信息，以 JSON 格式返回。"
                "只提取对话中明确提到的信息，不要推测。如果某个字段没有信息则返回空数组或空对象。\n"
                "返回格式：\n"
                '{"basic_info": {"age": null, "gender": null, "bmi": null}, '
                '"chronic_diseases": [], "allergies": [], "medications": [], '
                '"family_history": [], "focus_areas": []}\n\n'
                f"对话内容：\n{conversation}"
            )

            ai_messages = [{"role": "user", "content": extract_prompt}]
            ai_response = await call_ai_model(ai_messages, "你是一个健康信息提取助手，请严格按JSON格式返回结果。", db)

            extracted = _parse_ai_json(ai_response)
            if not extracted:
                return

            profile_result = await db.execute(
                select(UserHealthProfile).where(UserHealthProfile.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()
            if not profile:
                profile = UserHealthProfile(user_id=user_id)
                db.add(profile)

            _merge_profile(profile, extracted)
            await db.commit()
            logger.info("健康画像提取完成: user_id=%s, session_id=%s", user_id, session_id)
    except Exception as e:
        logger.error("健康画像提取失败: user_id=%s, session_id=%s, error=%s", user_id, session_id, e)


def _parse_ai_json(text: str) -> Optional[dict]:
    """Try to parse JSON from AI response, handling markdown code blocks."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                pass
    return None


def _merge_profile(profile: UserHealthProfile, extracted: dict):
    """Incrementally merge extracted data into existing profile."""
    if extracted.get("basic_info"):
        existing = profile.basic_info or {}
        for k, v in extracted["basic_info"].items():
            if v is not None:
                existing[k] = v
        profile.basic_info = existing

    for field in ["chronic_diseases", "allergies", "medications", "family_history", "focus_areas"]:
        new_items = extracted.get(field)
        if new_items and isinstance(new_items, list):
            existing = getattr(profile, field) or []
            merged = list(set(existing + new_items))
            setattr(profile, field, merged)
