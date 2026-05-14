"""[PRD-PROMPT-CONFIG-V1 2026-05-14] 报告解读按钮专属流程入口。

入口：POST /api/report-interpret/start

入参（按 PRD §8.3）：
    {
        "button_id": 123,
        "image_urls": ["..."],   // 拍照场景
        "file_url": "..."        // 文件场景，二者择一
    }

逻辑：
1. 根据 button_id 查 chat_function_buttons 拿到绑定的 prompt_template_id（必须存在且 button_type=report_interpret）
2. 创建 CheckupReport 草稿（user_id + file_urls + ocr_result.text 占位空）
3. 直接复用 report_interpret.interpret_start 的会话创建 + worker 投递逻辑：
   - 创建 ChatSession(session_type=report_interpret)
   - 预写隐式首条 user prompt（按 button 绑定的 PromptTemplate.content 渲染）
   - _schedule_interpret(session.id)
4. 返回 session_id + redirect_url (用于前端跳转 /chat/{sid})

注意：本接口不做实际 OCR；OCR/AI 由现有 report_interpret worker 处理。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ChatFunctionButton,
    ChatMessage,
    ChatSession,
    CheckupReport,
    FamilyMember,
    MessageRole,
    PromptTemplate,
    SessionType,
    User,
)
from app.services.prompts import DEFAULT_REPORT_INTERPRET_PROMPT
from app.api.report_interpret import (
    _build_member_info_text,
    _load_prompt,
    _schedule_interpret,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report-interpret", tags=["体检报告-按钮入口"])


class ReportInterpretStartButtonRequest(BaseModel):
    button_id: int = Field(..., description="功能按钮 ID（type 必须为 report_interpret）")
    image_urls: Optional[List[str]] = None
    file_url: Optional[str] = None
    member_id: Optional[int] = None
    ocr_text: Optional[str] = Field(None, description="可选：客户端预 OCR 文本；缺省则由前端后续触发 OCR")


class ReportInterpretStartButtonResponse(BaseModel):
    session_id: int
    report_id: int
    redirect_url: str
    stream_url: str
    interpret_status: str


@router.post("/start", response_model=ReportInterpretStartButtonResponse)
async def report_interpret_start_via_button(
    body: ReportInterpretStartButtonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ─── 入参校验 ───
    if not body.image_urls and not body.file_url:
        raise HTTPException(status_code=400, detail="image_urls 或 file_url 必须提供其一")

    btn = await db.get(ChatFunctionButton, body.button_id)
    if not btn or not btn.is_enabled:
        raise HTTPException(status_code=404, detail="功能按钮不存在或已禁用")
    if btn.button_type != "report_interpret":
        raise HTTPException(
            status_code=400,
            detail=f"按钮类型必须为 report_interpret，当前 {btn.button_type}",
        )

    prompt_content: Optional[str] = None
    prompt_type: str = "checkup_report_interpret"
    if btn.prompt_template_id:
        tpl = await db.get(PromptTemplate, btn.prompt_template_id)
        if tpl:
            prompt_content = tpl.content
            prompt_type = tpl.prompt_type or prompt_type

    # ─── 校验 member ───
    member_id = body.member_id
    fm: Optional[FamilyMember] = None
    if member_id:
        fm = await db.get(FamilyMember, member_id)
        if not fm or fm.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    # ─── 创建 CheckupReport（草稿） ───
    file_urls: list[str] = []
    if body.image_urls:
        file_urls.extend([u for u in body.image_urls if u])
    if body.file_url:
        file_urls.append(body.file_url)
    primary_url = file_urls[0] if file_urls else None

    today = datetime.utcnow().date()
    report = CheckupReport(
        user_id=current_user.id,
        family_member_id=member_id,
        title=f"{today.strftime('%Y-%m-%d')} 体检报告",
        file_url=primary_url,
        thumbnail_url=primary_url,
        report_date=today,
        ocr_result={"text": body.ocr_text or ""},
    )
    try:
        report.file_urls = file_urls  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(report)
    await db.flush()

    # ─── 创建 ChatSession + 首条隐式 user prompt ───
    title = f"🩺 {report.title} · 解读"
    session = ChatSession(
        user_id=current_user.id,
        session_type=SessionType.report_interpret,
        title=title[:200],
        family_member_id=member_id,
        message_count=0,
    )
    try:
        session.report_id = report.id  # type: ignore[attr-defined]
        session.member_relation = (fm.relationship_type if fm else None)  # type: ignore[attr-defined]
        session.interpret_status = "pending"  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(session)
    await db.flush()

    report.interpret_session_id = session.id

    # 拼装首条隐式 user 内容（优先用 button 绑定模板）
    if not prompt_content:
        prompt_content = await _load_prompt(db, prompt_type, DEFAULT_REPORT_INTERPRET_PROMPT)
    member_info_text, _ = await _build_member_info_text(db, current_user, member_id)
    rep_date_str = today.strftime("%Y-%m-%d")
    try:
        first_user_content = prompt_content.format(
            member_info=member_info_text,
            report_ocr_text=body.ocr_text or "（OCR 文本为空）",
            report_date=rep_date_str,
            report_title=report.title,
        )
    except Exception as fe:
        logger.error("[report_interpret_button] prompt render failed: %s", fe)
        first_user_content = prompt_content + "\n\n[OCR]\n" + (body.ocr_text or "")

    hidden_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=first_user_content,
    )
    try:
        hidden_msg.is_hidden = True  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(hidden_msg)
    session.message_count = (session.message_count or 0) + 1
    await db.commit()

    # 投递异步 worker（如果有 OCR 文本就立即解读，否则先创建会话由前端后续触发）
    if body.ocr_text:
        _schedule_interpret(session.id)

    return ReportInterpretStartButtonResponse(
        session_id=session.id,
        report_id=report.id,
        redirect_url=f"/chat/{session.id}?auto_start=1&type=report_interpret",
        stream_url=f"/api/report/interpret/session/{session.id}/stream",
        interpret_status="pending",
    )
