"""[2026-04-23] 报告解读与报告对比 对话化改造 API。
[2026-04-25] 异步化改造：/start 秒回（≤ 3s）；OCR/AI 在后台 worker 中执行；
                       结果通过 SSE 事件总线流式推送到 /stream 订阅者。

核心接口：
- POST /api/report/interpret/start     - 创建/复用报告解读会话（秒回 + 投递 worker）
- POST /api/report/compare/start       - 创建报告对比会话（秒回 + 投递 worker）
- GET  /api/report/interpret/session/:sid/stream  - SSE 订阅 worker 推送（含心跳 15s）
- POST /api/report/interpret/session/:sid/chat    - SSE 流式追问（自动带上下文，幂等不会重复触发 AI）
- POST /api/report/interpret/session/:sid/retry   - 重新解读（仅 failed 时可用）
- GET  /api/report/interpret/session/:sid/messages - 消息列表（默认过滤 is_hidden）
- GET  /api/report/interpret/detail/:id           - 极简详情页数据
- PUT  /api/report/interpret/:id/title            - 修改报告标题
- GET  /api/member/:id/reports                    - 某咨询人的所有报告
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session as _async_session
from app.core.security import get_current_user
from app.core import task_queue
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
    type: str
    interpret_status: str
    redirect_url: str
    stream_url: str


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


# ──────────────── 异步 worker ────────────────


# 最大重试次数（不含首次）
_MAX_RETRY = 2
# 重试退避秒数（首次失败后等 3s，再失败等 9s）
_RETRY_BACKOFFS = [3, 9]


async def _get_session_history_hidden_aware(session_id: int) -> list[dict]:
    """加载 session 历史（含 is_hidden 消息，用作完整 LLM 上下文）。"""
    async with _async_session() as db:
        q = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        rows = list(q.scalars().all())
    msgs = []
    for m in rows:
        role_val = m.role.value if hasattr(m.role, "value") else str(m.role)
        if role_val not in ("user", "assistant", "system"):
            continue
        msgs.append({"role": role_val, "content": m.content or ""})
    return msgs


async def _set_session_status(
    session_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    async with _async_session() as db:
        s = await db.get(ChatSession, session_id)
        if not s:
            return
        try:
            s.interpret_status = status  # type: ignore[attr-defined]
            if error is not None:
                s.interpret_error = error[:4000]  # type: ignore[attr-defined]
            if started:
                s.interpret_started_at = datetime.utcnow()  # type: ignore[attr-defined]
            if finished:
                s.interpret_finished_at = datetime.utcnow()  # type: ignore[attr-defined]
        except Exception:
            pass
        await db.commit()


async def _save_assistant_message(session_id: int, content: str) -> int:
    """落库 assistant 首条消息，返回消息 id。"""
    async with _async_session() as db:
        msg = ChatMessage(
            session_id=session_id,
            role=MessageRole.assistant,
            content=content,
        )
        db.add(msg)
        s = await db.get(ChatSession, session_id)
        if s:
            s.message_count = (s.message_count or 0) + 1
        await db.commit()
        await db.refresh(msg)
        return int(msg.id)


# [2026-04-25 Bug-01] AI 调用失败时对外统一友好文案，避免把后端配置错误透给用户
_AI_UNAVAILABLE_USER_MSG = "AI 解读服务暂时不可用，请稍后重试。"


async def _run_interpret_worker(session_id: int) -> None:
    """后台异步 worker：真正调用 AI，流式推送到 SSE 总线。
    失败自动重试（最多 2 次）。"""
    task_queue.broadcast(session_id, "progress", {"stage": "starting", "percent": 5})
    await _set_session_status(session_id, "running", started=True)
    task_queue.broadcast(session_id, "status", {"interpret_status": "running"})

    attempts = 0
    last_error: Optional[str] = None
    while attempts <= _MAX_RETRY:
        try:
            history = await _get_session_history_hidden_aware(session_id)
            if not history:
                raise RuntimeError("会话历史为空，无法解读")

            task_queue.broadcast(session_id, "progress", {"stage": "ai", "percent": 30})

            full_text = ""
            stream_msg_id: Optional[int] = None
            # [2026-04-25 Bug-01] 自建 AsyncSession 传给 call_ai_model_stream，
            # 避免 db=None 走 settings fallback 命中"AI服务未配置"
            async with _async_session() as ai_db:
                async for chunk in call_ai_model_stream(messages=history, system_prompt="", db=ai_db):
                    ctype = chunk.get("type")
                    content = chunk.get("content", "") or ""
                    if ctype == "delta" and content:
                        full_text += content
                        task_queue.broadcast(
                            session_id, "message.delta",
                            {"delta": content}
                        )
                    elif ctype == "done":
                        final_text = chunk.get("content") or full_text
                        if not final_text.strip():
                            raise RuntimeError("AI 返回内容为空")
                        stream_msg_id = await _save_assistant_message(session_id, final_text)
                        task_queue.broadcast(
                            session_id, "message.done",
                            {"message_id": stream_msg_id, "content": final_text}
                        )

            # 正常完成
            await _set_session_status(session_id, "done", finished=True)
            task_queue.broadcast(session_id, "status", {"interpret_status": "done"})
            task_queue.broadcast(session_id, "done", {"message_id": stream_msg_id or 0, "content": full_text})
            return
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            logger.warning("interpret worker attempt %d failed for session %s: %s", attempts + 1, session_id, e)
            attempts += 1
            if attempts > _MAX_RETRY:
                break
            backoff = _RETRY_BACKOFFS[min(attempts - 1, len(_RETRY_BACKOFFS) - 1)]
            task_queue.broadcast(
                session_id, "progress",
                {"stage": "retry", "attempt": attempts, "wait": backoff}
            )
            await asyncio.sleep(backoff)

    # [2026-04-25 Bug-01] 所有重试耗尽：详细原因写后端日志，SSE 只推统一友好文案
    logger.error(
        "interpret worker exhausted retries for session %s, last_error=%s",
        session_id, last_error,
    )
    await _set_session_status(session_id, "failed", error=last_error, finished=True)
    task_queue.broadcast(session_id, "status", {"interpret_status": "failed"})
    task_queue.broadcast(
        session_id, "error",
        {"code": "AI_FAILED", "message": _AI_UNAVAILABLE_USER_MSG, "retryable": True}
    )


def _schedule_interpret(session_id: int) -> None:
    """投递解读任务（若已在跑则跳过）。"""
    task_queue.submit_task(session_id, lambda: _run_interpret_worker(session_id))


# ──────────────── 接口实现 ────────────────


@router.post("/report/interpret/start", response_model=InterpretStartResponse)
async def interpret_start(
    body: InterpretStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传报告 + 选咨询人 → 点【AI 开始解读】。秒级创建会话并异步启动解读。"""
    rep = await db.get(CheckupReport, body.report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    member_id = body.member_id or rep.family_member_id
    fm: Optional[FamilyMember] = None
    if member_id:
        fm = await db.get(FamilyMember, member_id)
        if not fm or fm.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    # 幂等：若已绑定则直接返回（不再重复创建/投递）
    if getattr(rep, "interpret_session_id", None):
        existing = await db.get(ChatSession, rep.interpret_session_id)
        if existing and existing.user_id == current_user.id and not existing.is_deleted:
            status = getattr(existing, "interpret_status", None) or "done"
            stream_url = f"/api/report/interpret/session/{existing.id}/stream"
            # 如果之前失败过且无重试记录，不自动续跑，由前端调 /retry
            return InterpretStartResponse(
                session_id=existing.id,
                type="report_interpret",
                interpret_status=status,
                redirect_url=f"/chat/{existing.id}?auto_start=1&type=report_interpret",
                stream_url=stream_url,
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
    try:
        session.report_id = rep.id  # type: ignore[attr-defined]
        session.member_relation = (fm.relationship_type if fm else None)  # type: ignore[attr-defined]
        session.interpret_status = "pending"  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(session)
    await db.flush()

    rep.interpret_session_id = session.id

    # [2026-04-25] 预写首条"隐式"用户 Prompt（is_hidden=1，前端默认不拉取）
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

    # 投递异步 worker
    _schedule_interpret(session.id)

    return InterpretStartResponse(
        session_id=session.id,
        type="report_interpret",
        interpret_status="pending",
        # 保留旧 redirect_url（前端已统一跳 /chat/:sid），兼容历史
        redirect_url=f"/chat/{session.id}?auto_start=1&type=report_interpret",
        stream_url=f"/api/report/interpret/session/{session.id}/stream",
    )


@router.post("/report/compare/start", response_model=InterpretStartResponse)
async def compare_start(
    body: CompareStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """报告对比 - 秒回创建对比会话并投递异步 worker。"""
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
        session.interpret_status = "pending"  # type: ignore[attr-defined]
    except Exception:
        pass
    db.add(session)
    await db.flush()

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
    session.message_count = 1

    await db.commit()

    _schedule_interpret(session.id)

    return InterpretStartResponse(
        session_id=session.id,
        type="report_compare",
        interpret_status="pending",
        redirect_url=f"/chat/{session.id}?auto_start=1&type=report_compare",
        stream_url=f"/api/report/interpret/session/{session.id}/stream",
    )


# ──────────────── SSE 订阅 ────────────────


async def _heartbeat_wrapped_sse(session_id: int, request: Request):
    """SSE 生成器：订阅 bus，合并 15s 心跳。若 session 已 done 直接回放最终消息。"""
    # 先读取 session 当前状态
    async with _async_session() as db:
        sess = await db.get(ChatSession, session_id)
        if sess is None:
            return
        status = getattr(sess, "interpret_status", None) or "done"

    # 若 done：直接回放最终 assistant 首条消息
    if status == "done":
        async with _async_session() as db:
            q = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.role == MessageRole.assistant,
                )
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .limit(1)
            )
            amsg = q.scalar_one_or_none()
        if amsg is not None:
            yield task_queue.sse_format(
                "message.done",
                {"message_id": amsg.id, "content": amsg.content or ""},
            )
        yield task_queue.sse_format("status", {"interpret_status": "done"})
        yield task_queue.sse_format("done", {"content": amsg.content if amsg else ""})
        return

    if status == "failed":
        yield task_queue.sse_format("status", {"interpret_status": "failed"})
        yield task_queue.sse_format(
            "error",
            {"code": "AI_FAILED", "message": "解读失败，请点击重新解读", "retryable": True},
        )
        return

    # pending / running：订阅 bus
    bus_iter = task_queue.subscribe(session_id)

    # 若 worker 尚未投递（进程重启兜底），尝试再投递
    if not task_queue.is_running(session_id):
        _schedule_interpret(session_id)

    async def _event_producer():
        async for ev, data in bus_iter:
            yield ev, data

    prod = _event_producer()

    while True:
        if await request.is_disconnected():
            break
        try:
            ev, data = await asyncio.wait_for(prod.__anext__(), timeout=15.0)
        except asyncio.TimeoutError:
            # 心跳
            yield task_queue.sse_format("ping", {})
            continue
        except StopAsyncIteration:
            break

        yield task_queue.sse_format(ev, data)
        # 兼容旧前端：额外发一份 type/content 语义
        if ev == "message.delta":
            yield task_queue.sse_format(
                "__compat__",
                {"type": "delta", "content": data.get("delta", "")},
            )
        elif ev == "message.done":
            yield task_queue.sse_format(
                "__compat__",
                {"type": "done", "content": data.get("content", ""), "message_id": data.get("message_id", 0)},
            )
        elif ev == "error":
            yield task_queue.sse_format(
                "__compat__",
                {"type": "error", "content": data.get("message", "AI 服务异常")},
            )

        if ev in ("done", "error"):
            break


def _sse_response(gen) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/report/interpret/session/{session_id}/stream")
async def interpret_stream(
    request: Request,
    session_id: int = Path(...),
    auto_start: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 订阅解读流。订阅由后台 worker 推送的 progress / message.delta / message.done / status / error / ping 事件。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    if sess.session_type not in (SessionType.report_interpret, SessionType.report_compare):
        raise HTTPException(status_code=400, detail="会话类型不支持")

    return _sse_response(_heartbeat_wrapped_sse(session_id, request))


# 同一 URL 支持 POST（兼容老前端用 POST 调 first-message-stream 的场景）
@router.post("/report/interpret/session/{session_id}/stream")
async def interpret_stream_post(
    request: Request,
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await interpret_stream(request, session_id, 1, current_user, db)


class InterpretChatRequest(BaseModel):
    content: str = Field(..., min_length=1)


@router.post("/report/interpret/session/{session_id}/chat")
async def interpret_chat_followup(
    session_id: int = Path(...),
    body: InterpretChatRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """追问接口 - SSE 流式。
    幂等：首轮解读 pending/running 时不接受追问，返回 409；done 后按普通流式处理。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    status = getattr(sess, "interpret_status", None) or "done"
    if status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="首轮解读尚未完成，请稍候再追问")
    if status == "failed":
        raise HTTPException(status_code=409, detail="首轮解读失败，请先点击重新解读")

    # 保存用户追问消息
    db.add(ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=body.content,
    ))
    sess.message_count = (sess.message_count or 0) + 1
    await db.commit()

    history = []
    async with _async_session() as _db2:
        q = await _db2.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(60)
        )
        for m in q.scalars().all():
            role_val = m.role.value if hasattr(m.role, "value") else str(m.role)
            if role_val in ("user", "assistant", "system"):
                history.append({"role": role_val, "content": m.content or ""})

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
                    msg_id = 0
                    try:
                        msg_id = await _save_assistant_message(session_id, final_text)
                    except Exception as se:
                        logger.error("save assistant msg failed: %s", se)
                    yield f"data: {json.dumps({'type':'done','content':final_text,'message_id':msg_id}, ensure_ascii=False)}\n\n"
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


class InterpretRetryResponse(BaseModel):
    session_id: int
    interpret_status: str


@router.post("/report/interpret/session/{session_id}/retry", response_model=InterpretRetryResponse)
async def interpret_retry(
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首轮解读失败后，用户点'重新解读'按钮 → 重新投递 worker。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    status = getattr(sess, "interpret_status", None) or "done"
    if status != "failed":
        raise HTTPException(status_code=409, detail=f"当前状态 {status}，不允许重试")

    try:
        sess.interpret_status = "pending"  # type: ignore[attr-defined]
        sess.interpret_error = None  # type: ignore[attr-defined]
        sess.interpret_started_at = None  # type: ignore[attr-defined]
        sess.interpret_finished_at = None  # type: ignore[attr-defined]
    except Exception:
        pass
    await db.commit()

    _schedule_interpret(session_id)
    return InterpretRetryResponse(session_id=session_id, interpret_status="pending")


# ──────────────── session info / messages ────────────────


class InterpretSessionInfo(BaseModel):
    id: int
    title: Optional[str] = None
    session_type: str
    family_member_id: Optional[int] = None
    report_id: Optional[int] = None
    compare_report_ids: Optional[str] = None
    member_relation: Optional[str] = None
    interpret_status: Optional[str] = None
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
        interpret_status=getattr(sess, "interpret_status", None),
        created_at=sess.created_at.isoformat() if sess.created_at else None,
    )


class InterpretTaskStatusResponse(BaseModel):
    """[2026-04-25 PRD F2/F4] 任务状态轮询接口返回结构（前端轮询兜底，不依赖 SSE）。"""
    session_id: int
    status: str  # pending | running | done | failed
    stage: str  # uploaded | ocr | ai | done | failed
    percent: int  # 0~100
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@router.get("/report/interpret/session/{session_id}/task-status", response_model=InterpretTaskStatusResponse)
async def interpret_task_status(
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-25 PRD F2-2/F4-1] 任务状态查询接口（前端轮询用）。
    返回粗粒度阶段：已上传 → OCR 中 → AI 解读中 → 完成 / 失败。
    """
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    status = getattr(sess, "interpret_status", None) or "done"
    error = getattr(sess, "interpret_error", None)
    started_at = getattr(sess, "interpret_started_at", None)
    finished_at = getattr(sess, "interpret_finished_at", None)

    # status -> stage / percent 的简化映射（大粒度即可，前端只展示阶段）
    if status == "pending":
        stage, percent = "uploaded", 10
    elif status == "running":
        stage, percent = "ai", 60
    elif status == "done":
        stage, percent = "done", 100
    elif status == "failed":
        stage, percent = "failed", 0
    else:
        stage, percent = status, 0

    return InterpretTaskStatusResponse(
        session_id=session_id,
        status=status,
        stage=stage,
        percent=percent,
        error=error,
        started_at=started_at.isoformat() if started_at else None,
        finished_at=finished_at.isoformat() if finished_at else None,
    )


class InterpretOcrDetailResponse(BaseModel):
    """[2026-04-25 PRD F5-2] OCR 原文按需查询接口返回结构。"""
    session_id: int
    report_id: Optional[int] = None
    ocr_text: str = ""
    has_ocr: bool = False


@router.get("/report/interpret/session/{session_id}/ocr-detail", response_model=InterpretOcrDetailResponse)
async def interpret_ocr_detail(
    session_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-25 PRD F5-2] OCR 原文按需查询接口。
    AI 对话页默认完全不展示 OCR 原文，用户点击「查看 OCR 识别详情 ▾」时再调本接口。
    """
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id or sess.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    rid = getattr(sess, "report_id", None)
    if not rid:
        # report_compare 场景：拼装两份报告 OCR
        compare_ids = getattr(sess, "compare_report_ids", None)
        if compare_ids:
            ids = [int(x) for x in str(compare_ids).split(",") if x.strip().isdigit()]
            parts = []
            for cid in ids:
                r = await db.get(CheckupReport, cid)
                if r:
                    t = _report_ocr_text(r)
                    if t:
                        parts.append(f"=== 报告 {cid} ===\n{t}")
            txt = "\n\n".join(parts)
            return InterpretOcrDetailResponse(session_id=session_id, report_id=None, ocr_text=txt, has_ocr=bool(txt))
        return InterpretOcrDetailResponse(session_id=session_id, report_id=None, ocr_text="", has_ocr=False)

    rep = await db.get(CheckupReport, rid)
    if not rep or rep.user_id != current_user.id:
        return InterpretOcrDetailResponse(session_id=session_id, report_id=rid, ocr_text="", has_ocr=False)
    txt = _report_ocr_text(rep)
    return InterpretOcrDetailResponse(
        session_id=session_id,
        report_id=rid,
        ocr_text=txt,
        has_ocr=bool(txt and txt.strip()),
    )


# [2026-04-25 PRD F5-7] OCR 详情点击埋点（轻量计数，不阻塞主流程）
class OcrDetailClickRequest(BaseModel):
    session_id: int
    action: str = "view"  # view | collapse


@router.post("/report/interpret/ocr-detail/click")
async def interpret_ocr_detail_click(
    body: OcrDetailClickRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-25 PRD F5-7] OCR 详情入口点击率埋点。
    采用 logger 记录，避免新增表，便于通过日志聚合统计。"""
    try:
        logger.info(
            "OCR_DETAIL_CLICK user=%s session=%s action=%s ts=%s",
            current_user.id, body.session_id, body.action, datetime.utcnow().isoformat(),
        )
    except Exception:
        pass
    return {"success": True}


@router.get("/report/interpret/session/{session_id}/messages")
async def interpret_session_messages(
    session_id: int = Path(...),
    include_hidden: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """消息列表。默认过滤 is_hidden=1 的消息；Admin 可通过 include_hidden=1 查看完整审计。"""
    sess = await db.get(ChatSession, session_id)
    if not sess or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    q = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    items = []
    is_admin = bool(getattr(current_user, "is_admin", False))
    for m in q.scalars().all():
        hidden = bool(getattr(m, "is_hidden", False))
        if hidden and not (include_hidden and is_admin):
            continue
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        items.append({
            "id": m.id,
            "role": role,
            "content": m.content or "",
            "is_hidden": hidden,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"items": items}


# ──────────────── 其他 ────────────────


@router.get("/report/interpret/detail/{report_id}", response_model=ReportDetailV2)
async def interpret_detail(
    report_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rep = await db.get(CheckupReport, report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    images: list[str] = []
    file_urls_val = getattr(rep, "file_urls", None)
    if isinstance(file_urls_val, list) and file_urls_val:
        images = [u for u in file_urls_val if u]
    elif isinstance(file_urls_val, str) and file_urls_val:
        try:
            parsed = json.loads(file_urls_val)
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


# ──────────────── 启动时孤儿任务恢复 ────────────────


async def recover_pending_sessions() -> None:
    """启动时扫描 interpret_status='pending' 且 started_at 超过 10 分钟的会话，重新投递 worker。
    由 main.py::lifespan 调用。"""
    try:
        async with _async_session() as db:
            q = await db.execute(
                select(ChatSession).where(ChatSession.session_type.in_([
                    SessionType.report_interpret,
                    SessionType.report_compare,
                ]))
            )
            rows = list(q.scalars().all())
            for s in rows:
                status = getattr(s, "interpret_status", None)
                if status in ("pending", "running"):
                    started = getattr(s, "interpret_started_at", None)
                    # 超 10 分钟未完成则视为孤儿任务
                    if status == "pending" or (started and datetime.utcnow() - started > timedelta(minutes=10)):
                        logger.info("recover pending interpret session %s", s.id)
                        _schedule_interpret(s.id)
    except Exception as e:  # noqa: BLE001
        logger.error("recover_pending_sessions failed: %s", e)
