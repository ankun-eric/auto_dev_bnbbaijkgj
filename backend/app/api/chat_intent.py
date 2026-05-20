"""[PRD-TCM-DRAWER-V12 2026-05-20] 聊天意图识别接口

工作流程：
1. 关键词匹配（命中即返回意图，零延迟）
   - 扫描所有 is_enabled=true 且 trigger_by_keyword=true 的 ai_function 按钮
   - 把每个按钮的 trigger_keywords 列表合并；命中任一关键词 → 返回该按钮
2. AI 兜底（关键词未命中且按钮启用了 trigger_by_intent 时）
   - 当前最小实现：基于"启用 trigger_by_intent 的按钮文案"做相似度兜底
   - 未来可接入大模型 function-calling
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ChatFunctionButton, QuestionnaireTemplate

router = APIRouter(prefix="/api/chat", tags=["聊天意图识别"])


class IntentDetectRequest(BaseModel):
    text: str
    consultant_id: Optional[int] = None


class IntentDetectResponse(BaseModel):
    intent: Optional[str] = None  # "questionnaire_tcm" / "questionnaire_<code>" / None
    button_id: Optional[int] = None
    button_name: Optional[str] = None
    questionnaire_template_id: Optional[int] = None
    questionnaire_template_code: Optional[str] = None
    matched_keyword: Optional[str] = None
    source: str = "none"  # keyword / intent / none


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


@router.post("/intent-detect", response_model=IntentDetectResponse)
async def detect_intent(
    payload: IntentDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """根据用户输入的文本，扫描启用的功能按钮，判断是否命中触发关键词或意图。

    - 命中 questionnaire 类按钮时，返回 intent=questionnaire_<template_code>
    - 命中按钮名称 / auto_user_message 等也算意图命中
    - 未命中返回 intent=None
    """
    text_lower = _normalize(payload.text)
    if not text_lower:
        return IntentDetectResponse(source="none")

    # 1. 加载所有启用的 ai_function 按钮
    rows = (
        await db.execute(
            select(ChatFunctionButton).where(
                ChatFunctionButton.is_enabled == True,  # noqa: E712
                ChatFunctionButton.button_type == "ai_function",
            )
        )
    ).scalars().all()

    # 2. 关键词匹配
    for btn in rows:
        # trigger_by_keyword 默认 true（NULL 视为开启）
        if btn.trigger_by_keyword is False:
            continue
        kws = btn.trigger_keywords or []
        if not isinstance(kws, list):
            continue
        for kw in kws:
            if not kw:
                continue
            if _normalize(str(kw)) in text_lower:
                intent_code = await _build_intent_code(db, btn)
                return IntentDetectResponse(
                    intent=intent_code,
                    button_id=btn.id,
                    button_name=btn.name,
                    questionnaire_template_id=btn.questionnaire_template_id,
                    questionnaire_template_code=await _get_tpl_code(db, btn.questionnaire_template_id),
                    matched_keyword=str(kw),
                    source="keyword",
                )

    # 3. 意图兜底：扫描按钮名称 / auto_user_message / card_title
    for btn in rows:
        if btn.trigger_by_intent is False:
            continue
        name_candidates = []
        if btn.name:
            name_candidates.append(btn.name)
        if btn.auto_user_message:
            name_candidates.append(btn.auto_user_message)
        if btn.card_title:
            name_candidates.append(btn.card_title)
        for c in name_candidates:
            cl = _normalize(c)
            if cl and len(cl) >= 2 and cl in text_lower:
                intent_code = await _build_intent_code(db, btn)
                return IntentDetectResponse(
                    intent=intent_code,
                    button_id=btn.id,
                    button_name=btn.name,
                    questionnaire_template_id=btn.questionnaire_template_id,
                    questionnaire_template_code=await _get_tpl_code(db, btn.questionnaire_template_id),
                    matched_keyword=c,
                    source="intent",
                )

    return IntentDetectResponse(source="none")


async def _get_tpl_code(db: AsyncSession, tpl_id: Optional[int]) -> Optional[str]:
    if not tpl_id:
        return None
    tpl = await db.get(QuestionnaireTemplate, tpl_id)
    return tpl.code if tpl else None


async def _build_intent_code(db: AsyncSession, btn: ChatFunctionButton) -> str:
    if btn.ai_function_type == "questionnaire" and btn.questionnaire_template_id:
        tpl_code = await _get_tpl_code(db, btn.questionnaire_template_id)
        if tpl_code:
            return f"questionnaire_{tpl_code}"
    return f"button_{btn.id}"
