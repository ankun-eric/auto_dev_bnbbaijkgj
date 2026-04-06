from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import AiDisclaimerConfig, AiPromptConfig, AiSensitiveWord
from app.schemas.ai_center import (
    DisclaimerConfigResponse,
    DisclaimerConfigUpdate,
    PromptConfigResponse,
    PromptConfigUpdate,
    SensitiveWordCreate,
    SensitiveWordResponse,
    SensitiveWordUpdate,
)

router = APIRouter(prefix="/api/admin/ai-center", tags=["AI中心管理"])

admin_dep = require_role("admin")


# ── 敏感词管理 ──

@router.get("/sensitive-words")
async def list_sensitive_words(
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(AiSensitiveWord)
    count_query = select(func.count(AiSensitiveWord.id))

    if keyword:
        query = query.where(
            AiSensitiveWord.sensitive_word.contains(keyword)
            | AiSensitiveWord.replacement_word.contains(keyword)
        )
        count_query = count_query.where(
            AiSensitiveWord.sensitive_word.contains(keyword)
            | AiSensitiveWord.replacement_word.contains(keyword)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(AiSensitiveWord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [SensitiveWordResponse.model_validate(w) for w in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/sensitive-words", response_model=SensitiveWordResponse)
async def create_sensitive_word(
    data: SensitiveWordCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    word = AiSensitiveWord(
        sensitive_word=data.sensitive_word,
        replacement_word=data.replacement_word,
    )
    db.add(word)
    await db.flush()
    await db.refresh(word)
    return SensitiveWordResponse.model_validate(word)


@router.put("/sensitive-words/{word_id}", response_model=SensitiveWordResponse)
async def update_sensitive_word(
    word_id: int,
    data: SensitiveWordUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AiSensitiveWord).where(AiSensitiveWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="敏感词不存在")

    if data.sensitive_word is not None:
        word.sensitive_word = data.sensitive_word
    if data.replacement_word is not None:
        word.replacement_word = data.replacement_word
    word.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(word)
    return SensitiveWordResponse.model_validate(word)


@router.delete("/sensitive-words/{word_id}")
async def delete_sensitive_word(
    word_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AiSensitiveWord).where(AiSensitiveWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="敏感词不存在")
    await db.delete(word)
    return {"message": "删除成功"}


# ── 提示词配置 ──

@router.get("/prompts")
async def list_prompt_configs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AiPromptConfig).order_by(AiPromptConfig.id.asc()))
    items = [PromptConfigResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items}


@router.get("/prompts/{chat_type}", response_model=PromptConfigResponse)
async def get_prompt_config(
    chat_type: str,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AiPromptConfig).where(AiPromptConfig.chat_type == chat_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="提示词配置不存在")
    return PromptConfigResponse.model_validate(config)


@router.put("/prompts/{chat_type}", response_model=PromptConfigResponse)
async def update_prompt_config(
    chat_type: str,
    data: PromptConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AiPromptConfig).where(AiPromptConfig.chat_type == chat_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="提示词配置不存在")

    config.system_prompt = data.system_prompt
    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)
    return PromptConfigResponse.model_validate(config)


# ── 免责提示配置 ──

@router.get("/disclaimers")
async def list_disclaimer_configs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AiDisclaimerConfig).order_by(AiDisclaimerConfig.id.asc()))
    items = [DisclaimerConfigResponse.model_validate(d) for d in result.scalars().all()]
    return {"items": items}


@router.get("/disclaimers/{chat_type}", response_model=DisclaimerConfigResponse)
async def get_disclaimer_config(
    chat_type: str,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AiDisclaimerConfig).where(AiDisclaimerConfig.chat_type == chat_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="免责提示配置不存在")
    return DisclaimerConfigResponse.model_validate(config)


@router.put("/disclaimers/{chat_type}", response_model=DisclaimerConfigResponse)
async def update_disclaimer_config(
    chat_type: str,
    data: DisclaimerConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AiDisclaimerConfig).where(AiDisclaimerConfig.chat_type == chat_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="免责提示配置不存在")

    if data.disclaimer_text is not None:
        config.disclaimer_text = data.disclaimer_text
    if data.is_enabled is not None:
        config.is_enabled = data.is_enabled
    config.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(config)
    return DisclaimerConfigResponse.model_validate(config)
