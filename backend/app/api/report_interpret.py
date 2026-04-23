"""[2026-04-23] 报告解读与报告对比 对话化改造 API。

- POST /api/report/interpret/start     - 创建/复用报告解读会话
- POST /api/report/compare/start       - 创建报告对比会话
- GET  /api/report/interpret/session/:sid/stream  - SSE 流式首条解读消息（auto_start）
- POST /api/report/interpret/session/:sid/chat    - SSE 流式追问（自动带上下文）
- GET  /api/report/interpret/detail/:id           - 极简详情页数据
- PUT  /api/report/interpret/:id/title            - 修改报告标题
- GET  /api/member/:id/reports                    - 某咨询人的所有报告（供对比选择页使用）

绑定规则：
- 一份 checkup_report 对应 1 个 interpret 会话（session_type=report_interpret）
- 报告对比每次新建独立会话（session_type=report_compare）
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ChatMessage,
    ChatSession,
    CheckupReport,
    FamilyMember,
    MessageRole,
    PromptTemplate,
    SessionType,
    User,
)
from app.services.ai_service import call_ai_model_stream
from app.services.prompts import (
    DEFAULT_REPORT_COMPARE_PROMPT,
    DEFAULT_REPORT_INTERPRET_PROMPT,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["体检报告-对话解读"])


# ──────────────── 工具函数 ────────────────


def _calc_age(birthday) -> Optional[int]:
    if not birthday:
        return None
    try:
        today = datetime.utcnow().date()
        return today.year - birthday.year - (
            (today.month, today.day) < (birthday.month, birthday.day)
        )
    except Exception:
        return None


async def _build_member_info_text(db: AsyncSession, user: User, member_id: Optional[int]) -> tuple[str, Optional[FamilyMember]]:
    """把咨询人档案拼装成自然语言文本，用于塞入提示词。"""
    if not member_id:
        return (f"咨询对象：{user.nickname or '用户本人'}（档案不完整）", None)
    fm = await db.get(FamilyMember, member_id)
    if not fm or fm.user_id != user.id:
        return ("咨询对象：档案不可用", None)

    parts: list[str] = []
    name = fm.nickname or "未命名"
    rel = fm.relationship_type or ""
    parts.append(f"姓名：{name}")
    if rel:
        parts.append(f"关系：{rel}")
    age = _calc_age(fm.birthday)
    if age is not None:
        parts.append(f"年龄：{age} 岁")
    if fm.gender:
        parts.append(f"性别：{fm.gender}")
    if fm.height:
        parts.append(f"身高：{fm.height} cm")
    if fm.weight:
        parts.append(f"体重：{fm.weight} kg")
    if fm.medical_histories:
        try:
            mh = fm.medical_histories
            if isinstance(mh, list):
                parts.append(f"慢性病/既往史：{'、'.join(str(m) for m in mh) or '无'}")
            elif isinstance(mh, dict):
                parts.append(f"慢性病/既往史：{json.dumps(mh, ensure_ascii=False)}")
        except Exception:
            pass
    if fm.allergies:
        try:
            ag = fm.allergies
            if isinstance(ag, list):
                parts.append(f"过敏史：{'、'.join(str(a) for a in ag) or '无'}")
            elif isinstance(ag, dict):
                parts.append(f"过敏史：{json.dumps(ag, ensure_ascii=False)}")
        except Exception:
            pass
    return ("\n".join(parts), fm)


async def _load_prompt(db: AsyncSession, prompt_type: str, default_content: str) -> str:
    q = await db.execute(
        select(PromptTemplate)
        .where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.is_active.is_(True),
        )
        .order_by(desc(PromptTemplate.updated_at))
        .limit(1)
    )
    tpl = q.scalar_one_or_none()
    if tpl and tpl.content:
        return tpl.content
    return default_content


def _report_title(report: CheckupReport) -> str:
    if getattr(report, "title", None):
        return report.title  # type: ignore[return-value]
    d = report.report_date or (report.created_at.date() if report.created_at else datetime.utcnow().date())
    return f"{d.strftime('%Y-%m-%d')} 体检报告"


def _report_ocr_text(report: CheckupReport) -> str:
    if report.ocr_result and isinstance(report.ocr_result, dict):
        return report.ocr_result.get("text", "") or ""
    return ""


# ──────────────── Schema ────────────────


class InterpretStartRequest(BaseModel):
    report_id: int
    member_id: Optional[int] = None


class CompareStartRequest(BaseModel):
    member_id: int
    report_ids: List[int]


class InterpretStartResponse(BaseModel):
    session_id: int
    redirect_url: str


class ReportTitleUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)


class MemberReportItem(BaseModel):
    id: int
    title: str
    report_date: Optional[str] = None
    created_at: str
    thumbnail_url: Optional[str] = None
    file_url: Optional[str] = None
    interpret_session_id: Optional[int] = None


class MemberReportsResponse(BaseModel):
    member_id: int
    items: List[MemberReportItem]


class ReportDetailV2(BaseModel):
    id: int
    title: str
    ocr_text: str
    images: List[str]
    member_id: Optional[int] = None
    member_name: Optional[str] = None
    member_relation: Optional[str] = None
    created_at: str
    interpret_session_id: Optional[int] = None


# ──────────────── 接口实现 ────────────────


@router.post("/report/interpret/start", response_model=InterpretStartResponse)
async def interpret_start(
    body: InterpretStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传报告 + 选咨询人 → 点【AI 开始解读】。创建或复用解读会话。"""
    rep = await db.get(CheckupReport, body.report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    member_id = body.member_id or rep.family_member_id
    fm: Optional[FamilyMember] = None
    if member_id:
        fm = await db.get(FamilyMember, member_id)
        if not fm or fm.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    # 幂等：若已绑定则直接返回
    if getattr(rep, "interpret_session_id", None):
        existing = await db.get(ChatSession, rep.interpret_session_id)
        if existing and existing.user_id == current_user.id and not existing.is_deleted:
            return InterpretStartResponse(
                session_id=existing.id,
                redirect_url=f"/checkup/chat/{existing.id}?auto_start=1&type=report_interpret",
            )

    # 写入报告绑定字段
    if member_id and not rep.family_member_id:
        rep.family_member_id = member_id
    if not getattr(rep, "title", None):
        rep.title = _report_title(rep)

    # 创建会话
    title = f"🩺 {rep.title} · 解读"
    session = ChatSession(
        user_id=current_user.id,
        session_type=SessionType.report_interpret,
        title=title[:200],
        family_member_id=member_id,
        model_name=None,
        message_count=0,
    )
    # 动态字段（兼容未升级列的情况）
    try:
        session.report_id = rep.id  # type: ignore[attr-defined]
        session.member_relation = (fm.relationship_type if fm else None)  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(session)
    await db.flush()

    rep.interpret_session_id = session.id

    # 预写首条 user 提示消息（用于后续 SSE 首次流式生成）
    member_info_text, _ = await _build_member_info_text(db, current_user, member_id)
    prompt_tpl = await _load_prompt(db, "checkup_report_interpret", DEFAULT_REPORT_INTERPRET_PROMPT)
    rep_date_str = (rep.report_date or (rep.created_at.date() if rep.created_at else datetime.utcnow().date())).strftime("%Y-%m-%d")
    try:
        first_user_content = prompt_tpl.format(
            member_info=member_info_text,
            report_ocr_text=_report_ocr_text(rep) or "（OCR 文本为空）",
            report_date=rep_date_str,
            report_title=rep.title or _report_title(rep),
        )
    except Exception as fe:
        logger.error("interpret prompt render failed: %s", fe)
        first_user_content = prompt_tpl + "\n\n[OCR]\n" + _report_ocr_text(rep)

    db.add(ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=first_user_content,
    ))
    session.message_count = (session.message_count or 0) + 1

    await db.commit()
    return InterpretStartResponse(
        session_id=session.id,
        redirect_url=f"/checkup/chat/{session.id}?auto_start=1&type=report_interpret",
    )


@router.post("/report/compare/start", response_model=InterpretStartResponse)
async def compare_start(
    body: CompareStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """报告对比 - 创建新的对比会话（每次对比都新建独立会话）。"""
    if not body.report_ids or len(body.report_ids) != 2:
        raise HTTPException(status_code=400, detail="只能对比 2 份报告")
    if body.report_ids[0] == body.report_ids[1]:
        raise HTTPException(status_code=400, detail="不能对比同一份报告")

    fm = await db.get(FamilyMember, body.member_id)
    if not fm or fm.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    reports: list[CheckupReport] = []
    for rid in body.report_ids:
        r = await db.get(CheckupReport, rid)
        if not r or r.user_id != current_user.id:
            raise HTTPException(status_code=404, detail=f"报告 {rid} 不存在")
        if r.family_member_id and r.family_member_id != body.member_id:
            raise HTTPException(status_code=400, detail=f"报告 {rid} 不属于该咨询人")
        reports.append(r)

    # 按日期排序：A=较早, B=较晚
    def _rkey(r: CheckupReport):
        return r.report_date or (r.created_at.date() if r.created_at else datetime.utcnow().date())
    reports.sort(key=_rkey)
    rep_a, rep_b = reports[0], reports[1]

    member_info_text, _ = await _build_member_info_text(db, current_user, body.member_id)
    prompt_tpl = await _load_prompt(db, "checkup_report_compare", DEFAULT_REPORT_COMPARE_PROMPT)
    a_date = _rkey(rep_a).strftime("%Y-%m-%d")
    b_date = _rkey(rep_b).strftime("%Y-%m-%d")
    try:
        first_user_content = prompt_tpl.format(
            member_info=member_info_text,
            report_a_date=a_date,
            report_a_title=rep_a.title or _report_title(rep_a),
            report_a_ocr=_report_ocr_text(rep_a) or "（报告A OCR文本为空）",
            report_b_date=b_date,
            report_b_title=rep_b.title or _report_title(rep_b),
            report_b_ocr=_report_ocr_text(rep_b) or "（报告B OCR文本为空）",
        )
    except Exception as fe:
        logger.error("compare prompt render failed: %s", fe)
        first_user_content = prompt_tpl

    short_title = f"🔄 {fm.nickname or '咨询人'} · {a_date} vs {b_date}"
    session = ChatSession(
        user_id=current_user.id,
        session_type=SessionType.report_compare,
        title=short_title[:200],
        family_member_id=body.member_id,
        message_count=0,
    )
    try:
        session.compare_report_ids = f"{rep_a.id},{rep_b.id}"  # type: ignore[attr-defined]
        session.member_relation = fm.relationship_type  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(session)
    await db.flush()

    db.add(ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=first_user_content,
    ))
    session.message_count = 1

    await db.commit()
    return InterpretStartResponse(
        session_id=session.id,
        redirect_url=f"/checkup/chat/{session.id}?auto_start=1&type=report_compare",
    )


async def _session_history_as_messages(db: AsyncSession, session_id: int, limit: int = 40) -> list[dict]:
    q = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .limit(limit)
    )
    rows = list(q.scalars().all())
    msgs = []
    for m in rows:
        role_val = m.role.value if hasattr(m.role, "value") else str(m.role)
        if role_val not in ("user", "assistant", "system"):
            continue
        msgs.append({"role": role_val, "content": m.content or ""})
    return msgs


@router.get("/report/interpret/session/{session_id}/stream")
async def interpret_stream(
    session_id: int = Path(...),
    auto_start: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式输出：触发首次 AI 解读（auto_start=1）。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    if sess.session_type not in (SessionType.report_interpret, SessionType.report_compare):
        raise HTTPException(status_code=400, detail="会话类型不支持")

    # 检查是否已经有 assistant 首条回复
    q = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.role == MessageRole.assistant)
        .limit(1)
    )
    has_assistant = q.scalar_one_or_none() is not None
    history = await _session_history_as_messages(db, session_id)

    async def _sse_gen():
        # 如果已有 assistant 首条且非 auto_start 场景，直接返回已有消息
        if has_assistant and not auto_start:
            yield f"data: {json.dumps({'type':'done','content':'已存在历史消息'}, ensure_ascii=False)}\n\n"
            return

        full_content_acc = ""
        try:
            async for chunk in call_ai_model_stream(messages=history, system_prompt="", db=db):
                ctype = chunk.get("type")
                content = chunk.get("content", "")
                if ctype == "delta":
                    full_content_acc += content
                    yield f"data: {json.dumps({'type':'delta','content':content}, ensure_ascii=False)}\n\n"
                elif ctype == "done":
                    final_text = chunk.get("content") or full_content_acc
                    # 保存 assistant 消息到 DB
                    try:
                        from app.core.database import async_session as _as
                        async with _as() as _db2:
                            _db2.add(ChatMessage(
                                session_id=session_id,
                                role=MessageRole.assistant,
                                content=final_text,
                            ))
                            s2 = await _db2.get(ChatSession, session_id)
                            if s2:
                                s2.message_count = (s2.message_count or 0) + 1
                            await _db2.commit()
                    except Exception as se:
                        logger.error("save assistant msg failed: %s", se)
                    yield f"data: {json.dumps({'type':'done','content':final_text}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("interpret_stream error: %s", e)
            yield f"data: {json.dumps({'type':'error','content':str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class InterpretChatRequest(BaseModel):
    content: str = Field(..., min_length=1)


@router.post("/report/interpret/session/{session_id}/chat")
async def interpret_chat_followup(
    session_id: int = Path(...),
    body: InterpretChatRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """追问接口 - SSE 流式。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户追问消息
    db.add(ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=body.content,
    ))
    sess.message_count = (sess.message_count or 0) + 1
    await db.commit()

    history = await _session_history_as_messages(db, session_id)

    async def _sse_gen():
        full_content_acc = ""
        try:
            async for chunk in call_ai_model_stream(messages=history, system_prompt="", db=db):
                ctype = chunk.get("type")
                content = chunk.get("content", "")
                if ctype == "delta":
                    full_content_acc += content
                    yield f"data: {json.dumps({'type':'delta','content':content}, ensure_ascii=False)}\n\n"
                elif ctype == "done":
                    final_text = chunk.get("content") or full_content_acc
                    try:
                        from app.core.database import async_session as _as
                        async with _as() as _db2:
                            _db2.add(ChatMessage(
                                session_id=session_id,
                                role=MessageRole.assistant,
                                content=final_text,
                            ))
                            s2 = await _db2.get(ChatSession, session_id)
                            if s2:
                                s2.message_count = (s2.message_count or 0) + 1
                            await _db2.commit()
                    except Exception as se:
                        logger.error("save assistant msg failed: %s", se)
                    yield f"data: {json.dumps({'type':'done','content':final_text}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("interpret_chat_followup error: %s", e)
            yield f"data: {json.dumps({'type':'error','content':str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class InterpretSessionInfo(BaseModel):
    id: int
    title: Optional[str] = None
    session_type: str
    family_member_id: Optional[int] = None
    report_id: Optional[int] = None
    compare_report_ids: Optional[str] = None
    member_relation: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/report/interpret/session/{session_id}", response_model=InterpretSessionInfo)
async def interpret_session_info(
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    stype = sess.session_type.value if hasattr(sess.session_type, "value") else str(sess.session_type)
    return InterpretSessionInfo(
        id=sess.id,
        title=sess.title,
        session_type=stype,
        family_member_id=sess.family_member_id,
        report_id=getattr(sess, "report_id", None),
        compare_report_ids=getattr(sess, "compare_report_ids", None),
        member_relation=getattr(sess, "member_relation", None),
        created_at=sess.created_at.isoformat() if sess.created_at else None,
    )


@router.get("/report/interpret/session/{session_id}/messages")
async def interpret_session_messages(
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    q = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    items = []
    for m in q.scalars().all():
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        items.append({
            "id": m.id,
            "role": role,
            "content": m.content or "",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"items": items}


@router.get("/report/interpret/detail/{report_id}", response_model=ReportDetailV2)
async def interpret_detail(
    report_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rep = await db.get(CheckupReport, report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    # [2026-04-23] 多图修复：优先使用完整 URL 列表，fallback 为 [file_url]
    images: list[str] = []
    file_urls_val = getattr(rep, "file_urls", None)
    if isinstance(file_urls_val, list) and file_urls_val:
        images = [u for u in file_urls_val if u]
    elif isinstance(file_urls_val, str) and file_urls_val:
        # 兼容 JSON 字段返回字符串的场景
        try:
            import json as _json
            parsed = _json.loads(file_urls_val)
            if isinstance(parsed, list):
                images = [u for u in parsed if u]
        except Exception:
            images = []
    if not images:
        if rep.file_url:
            images.append(rep.file_url)
        if rep.thumbnail_url and rep.thumbnail_url != rep.file_url:
            images.append(rep.thumbnail_url)

    mem_name = None
    mem_relation = None
    if rep.family_member_id:
        fm = await db.get(FamilyMember, rep.family_member_id)
        if fm:
            mem_name = fm.nickname
            mem_relation = fm.relationship_type

    return ReportDetailV2(
        id=rep.id,
        title=rep.title or _report_title(rep),
        ocr_text=_report_ocr_text(rep),
        images=images,
        member_id=rep.family_member_id,
        member_name=mem_name,
        member_relation=mem_relation,
        created_at=rep.created_at.isoformat() if rep.created_at else "",
        interpret_session_id=getattr(rep, "interpret_session_id", None),
    )


@router.put("/report/interpret/{report_id}/title")
async def interpret_update_title(
    report_id: int = Path(...),
    body: ReportTitleUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rep = await db.get(CheckupReport, report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    new_title = body.title.strip()[:50]
    rep.title = new_title
    await db.commit()
    return {"success": True, "title": new_title}


@router.get("/member/{member_id}/reports", response_model=MemberReportsResponse)
async def member_reports(
    member_id: int = Path(...),
    for_compare: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回某咨询人所有报告（按上传时间倒序）。"""
    fm = await db.get(FamilyMember, member_id)
    if not fm or fm.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    q = await db.execute(
        select(CheckupReport)
        .where(
            CheckupReport.user_id == current_user.id,
            CheckupReport.family_member_id == member_id,
        )
        .order_by(desc(CheckupReport.created_at))
    )
    rows = list(q.scalars().all())
    items: list[MemberReportItem] = []
    for r in rows:
        items.append(MemberReportItem(
            id=r.id,
            title=r.title or _report_title(r),
            report_date=r.report_date.strftime("%Y-%m-%d") if r.report_date else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
            thumbnail_url=r.thumbnail_url,
            file_url=r.file_url,
            interpret_session_id=getattr(r, "interpret_session_id", None),
        ))
    return MemberReportsResponse(member_id=member_id, items=items)
