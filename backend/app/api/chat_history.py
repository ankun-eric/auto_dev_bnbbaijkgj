import io
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import ChatMessage, ChatSession, MessageRole, SessionType, User
from app.schemas.chat_history import (
    AdminChatMessageItem,
    AdminChatSessionDetail,
    AdminChatSessionItem,
    ChatSessionPinRequest,
    ChatSessionUpdate,
    SharedChatMessageItem,
    SharedChatResponse,
    UserChatSessionCreate,
    UserChatSessionItem,
)

router = APIRouter(tags=["对话记录"])

admin_dep = require_role("admin")


# [BUG-461 (2026-05-11)] 关系名称中文 → 前端 6 色键归一化
# 前端 ChatHistoryItem.askerRole 期望 key 为：self / spouse / father / mother / child / elder。
# 此映射兼容历史数据库中以中文存储的 relationship_type。
# 命中即返回对应英文 key，未命中保留原值（前端会回退到默认色）。
_RELATION_CN_TO_EN = {
    "本人": "self",
    "自己": "self",
    "我": "self",
    "配偶": "spouse",
    "丈夫": "spouse",
    "妻子": "spouse",
    "老公": "spouse",
    "老婆": "spouse",
    "爸爸": "father",
    "父亲": "father",
    "爹": "father",
    "妈妈": "mother",
    "母亲": "mother",
    "娘": "mother",
    "孩子": "child",
    "儿子": "child",
    "女儿": "child",
    "小孩": "child",
    "子女": "child",
    "爷爷": "elder",
    "奶奶": "elder",
    "外公": "elder",
    "外婆": "elder",
    "姥爷": "elder",
    "姥姥": "elder",
    "祖父": "elder",
    "祖母": "elder",
    "外祖父": "elder",
    "外祖母": "elder",
    "长辈": "elder",
}


def _normalize_relation(raw: Optional[str]) -> str:
    """将 FamilyMember.relationship_type 归一化为前端 6 色键。

    - None/空 → 'self'
    - 已是英文 key → 原样返回
    - 中文常见称谓 → 映射为英文 key
    - 未能识别 → 原样返回，前端按 hash 调色板回退
    """
    if not raw:
        return "self"
    key = str(raw).strip()
    if not key:
        return "self"
    low = key.lower()
    if low in {"self", "spouse", "father", "mother", "child", "elder"}:
        return low
    return _RELATION_CN_TO_EN.get(key, key)


# ──────────────── 管理端 API ────────────────


@router.get("/api/admin/chat-sessions")
async def admin_list_sessions(
    user_search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keyword: Optional[str] = None,
    model_name: Optional[str] = None,
    min_rounds: Optional[int] = None,
    max_rounds: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).join(User, ChatSession.user_id == User.id)
    count_query = select(func.count(ChatSession.id)).join(User, ChatSession.user_id == User.id)

    if user_search:
        user_filter = or_(
            User.nickname.like(f"%{user_search}%"),
            User.phone.like(f"%{user_search}%"),
        )
        query = query.where(user_filter)
        count_query = count_query.where(user_filter)

    if start_date:
        query = query.where(ChatSession.created_at >= start_date)
        count_query = count_query.where(ChatSession.created_at >= start_date)

    if end_date:
        query = query.where(ChatSession.created_at <= end_date)
        count_query = count_query.where(ChatSession.created_at <= end_date)

    if model_name:
        query = query.where(ChatSession.model_name == model_name)
        count_query = count_query.where(ChatSession.model_name == model_name)

    if min_rounds is not None:
        query = query.where(ChatSession.message_count >= min_rounds)
        count_query = count_query.where(ChatSession.message_count >= min_rounds)

    if max_rounds is not None:
        query = query.where(ChatSession.message_count <= max_rounds)
        count_query = count_query.where(ChatSession.message_count <= max_rounds)

    if keyword:
        sub = select(ChatMessage.session_id).where(
            ChatMessage.content.like(f"%{keyword}%")
        ).distinct()
        query = query.where(ChatSession.id.in_(sub))
        count_query = count_query.where(ChatSession.id.in_(sub))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(ChatSession.user))
        .order_by(ChatSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        first_msg_result = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.session_id == s.id, ChatMessage.role == MessageRole.user)
            .order_by(ChatMessage.created_at.asc())
            .limit(1)
        )
        first_msg = first_msg_result.scalar_one_or_none()

        items.append(AdminChatSessionItem(
            id=s.id,
            user_id=s.user_id,
            user_nickname=s.user.nickname if s.user else None,
            user_avatar=s.user.avatar if s.user else None,
            session_type=s.session_type.value if hasattr(s.session_type, "value") else s.session_type,
            title=s.title,
            first_message=first_msg[:30] if first_msg else None,
            message_count=s.message_count or 0,
            model_name=s.model_name,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/api/admin/chat-sessions/{session_id}")
async def admin_get_session_detail(
    session_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.user), selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = [
        AdminChatMessageItem(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            message_type=m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            file_url=m.file_url,
            image_urls=m.image_urls,
            file_urls=m.file_urls,
            response_time_ms=m.response_time_ms,
            prompt_tokens=m.prompt_tokens,
            completion_tokens=m.completion_tokens,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return AdminChatSessionDetail(
        id=session.id,
        user_id=session.user_id,
        user_nickname=session.user.nickname if session.user else None,
        user_avatar=session.user.avatar if session.user else None,
        session_type=session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        title=session.title,
        model_name=session.model_name,
        message_count=session.message_count or 0,
        device_info=session.device_info,
        ip_address=session.ip_address,
        ip_location=session.ip_location,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


@router.get("/api/admin/chat-sessions/{session_id}/export")
async def admin_export_session(
    session_id: int,
    format: str = Query("xlsx", regex="^(xlsx|csv)$"),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.user), selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    rows = []
    for m in session.messages:
        rows.append({
            "角色": m.role.value if hasattr(m.role, "value") else m.role,
            "内容": m.content,
            "消息类型": m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            "回复耗时(ms)": m.response_time_ms or "",
            "Prompt Tokens": m.prompt_tokens or "",
            "Completion Tokens": m.completion_tokens or "",
            "时间": str(m.created_at) if m.created_at else "",
        })

    if format == "csv":
        import csv

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        content_bytes = output.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="chat_{session_id}.csv"'},
        )

    # xlsx
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器未安装openpyxl，无法导出xlsx格式")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "对话记录"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row[h] for h in headers])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="chat_{session_id}.xlsx"'},
    )


# ──────────────── 用户端 API ────────────────


@router.get("/api/chat-sessions", response_model=list)
async def user_list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query("archived"),
    consult_target_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19]
    新增 status / consult_target_id 入参；默认仅返回 status='archived' 的会话（历史会话），
    与"历史"语义对齐。前端历史抽屉固定传 status='archived'，需要全量时传 status='all'。
    """
    # [BUG-460 (2026-05-11)] MySQL 不支持 `NULLS LAST` 语法，使用 `pinned_at IS NULL` 表达式
    # 模拟「NULL 排在最后」的效果（IS NULL 结果 0/1，ASC 时 0 在前 → 非 NULL 在前）。
    # 排序优先级：① 置顶在前 ② 置顶内按 pinned_at 倒序（NULL 置后） ③ 最近活跃在前。
    pinned_at_is_null = case((ChatSession.pinned_at.is_(None), 1), else_=0)
    # [PRD-AI-HOME-IDLE-ARCHIVE-V1] 状态过滤：默认 archived，可传 active / all
    status_norm = (status or "archived").strip().lower()
    if status_norm not in {"archived", "active", "all"}:
        status_norm = "archived"
    # [BUG-461 (2026-05-11)] selectinload(family_member) 关联拉取，避免 N+1；
    # 关联为空时统一兜底 relation='self'。
    query = (
        select(ChatSession)
        .options(selectinload(ChatSession.family_member))
        .where(ChatSession.user_id == current_user.id, ChatSession.is_deleted == False)
    )
    if status_norm != "all":
        query = query.where(ChatSession.status == status_norm)
    if consult_target_id is not None:
        # consult_target_id 解释：None / 0 / 负值 → 本人会话；正数 → 对应家庭成员
        try:
            tid = int(consult_target_id)
        except Exception:
            tid = -1
        if tid > 0:
            query = query.where(ChatSession.family_member_id == tid)
        else:
            query = query.where(ChatSession.family_member_id.is_(None))
    # 排序：置顶在前；同状态内按 last_active_at 倒序（兜底 updated_at）
    query = (
        query.order_by(
            ChatSession.is_pinned.desc(),
            pinned_at_is_null.asc(),
            ChatSession.pinned_at.desc(),
            ChatSession.last_active_at.desc(),
            ChatSession.updated_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    try:
        result = await db.execute(query)
        sessions = result.scalars().all()
    except Exception:
        # [BUG-460 (2026-05-11)] 接口健壮性兜底：极端情况下查询异常不应直接 500，
        # 影响左侧抽屉「历史对话」整列加载。退化为按 updated_at 倒序，保证可读性。
        fallback_query = (
            select(ChatSession)
            .options(selectinload(ChatSession.family_member))
            .where(ChatSession.user_id == current_user.id, ChatSession.is_deleted == False)
            .order_by(ChatSession.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(fallback_query)
        sessions = result.scalars().all()

    items = []
    for s in sessions:
        # [BUG-460] 历史脏数据兜底：session_type/title/created_at/updated_at 取值时全部容错，
        # 任何单条数据异常不应导致整列接口 500。
        try:
            session_type_value = s.session_type.value if hasattr(s.session_type, "value") else (s.session_type or "consultation")
            # [BUG-461 (2026-05-11)] 提取咨询人信息：family_member 关联可能为 None
            family_member_relation: Optional[str] = "self"
            family_member_nickname: Optional[str] = None
            if s.family_member is not None:
                try:
                    rel_raw = getattr(s.family_member, "relationship_type", None)
                    family_member_relation = _normalize_relation(rel_raw)
                    family_member_nickname = getattr(s.family_member, "nickname", None)
                except Exception:
                    # 关联对象异常不阻塞整列输出，回退为 self
                    family_member_relation = "self"
                    family_member_nickname = None
            items.append(
                UserChatSessionItem(
                    id=s.id,
                    session_type=session_type_value or "consultation",
                    title=s.title,
                    message_count=s.message_count or 0,
                    is_pinned=bool(s.is_pinned) if s.is_pinned is not None else False,
                    family_member_id=s.family_member_id,
                    family_member_relation=family_member_relation,
                    family_member_nickname=family_member_nickname,
                    # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 新增三个状态字段
                    status=(s.status or "archived"),
                    archived_at=s.archived_at,
                    last_active_at=s.last_active_at or s.updated_at or s.created_at,
                    created_at=s.created_at or datetime.utcnow(),
                    updated_at=s.updated_at or s.created_at or datetime.utcnow(),
                )
            )
        except Exception:
            # 单条异常静默跳过，保证整列其他会话仍可正常展示
            continue
    return items


# [BUG-461 (2026-05-11)] 新增用户端「直接创建新会话」接口
# 用于「切换咨询人 → 立即开新会话」流程（Bug-C 修复）：
# 前端在用户确认切换咨询人后，调用此接口落库新会话，拿到 session_id 再跳转。
@router.post("/api/chat-sessions")
async def user_create_session(
    data: UserChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户端直接创建新会话（轻量版）。

    [BUG-461 修复 Bug-C] 与 `POST /api/chat/sessions` 同义但路径对齐抽屉
    `GET /api/chat-sessions` 列表接口，便于前端"列表 + 创建"成对调用，
    并支持 family_member_id 立即落库（空会话允许存在）。
    """
    # session_type 兜底：传入非法值或缺失时统一回退为 health_qa
    raw_type = (data.session_type or "health_qa").strip()
    try:
        session_type = SessionType(raw_type)
    except Exception:
        session_type = SessionType.health_qa

    # family_member 校验：若提供则必须属于当前用户
    family_member_id = data.family_member_id
    family_member_relation: Optional[str] = "self"
    family_member_nickname: Optional[str] = None
    if family_member_id is not None:
        from app.models.models import FamilyMember as _FM

        fm_result = await db.execute(
            select(_FM).where(_FM.id == family_member_id, _FM.user_id == current_user.id)
        )
        member = fm_result.scalar_one_or_none()
        if not member:
            # 不存在 / 不属于当前用户 → 视为本人会话，避免越权
            family_member_id = None
        else:
            family_member_relation = _normalize_relation(
                getattr(member, "relationship_type", None)
            )
            family_member_nickname = getattr(member, "nickname", None)

    # [BUG-466 (2026-05-11)] 切咨询对象 / 6 小时切片 强一致归档：
    # 若请求体携带 archive_previous_session_id，则在同事务里把旧会话的 updated_at
    # 推到当前时间，确保抽屉历史列表立刻把"刚刚发生的活跃对话"提到顶部。
    # 仅校验：会话存在 + 属于当前用户 + 未删除；非法 / 越权 ID 静默忽略，
    # 不阻塞主流程（新会话仍然能创建出来）。
    now = datetime.utcnow()
    archived_old_ids: List[int] = []
    if data.archive_previous_session_id is not None:
        try:
            prev_result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == int(data.archive_previous_session_id),
                    ChatSession.user_id == current_user.id,
                    ChatSession.is_deleted == False,
                )
            )
            prev_session = prev_result.scalar_one_or_none()
            if prev_session is not None:
                # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 真正改 status
                prev_session.status = "archived"
                if prev_session.archived_at is None:
                    prev_session.archived_at = now
                prev_session.updated_at = now
                archived_old_ids.append(prev_session.id)
        except Exception:
            # 归档失败不影响新会话创建
            pass

    # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 强约束：
    # 创建新 active 会话前，先把当前用户在同一咨询对象下的所有 active 会话归档
    try:
        existing_active = await db.execute(
            select(ChatSession).where(
                ChatSession.user_id == current_user.id,
                ChatSession.is_deleted == False,
                ChatSession.status == "active",
            )
        )
        for s in existing_active.scalars().all():
            # 只要属于当前用户，全部归档（避免出现两个 active）
            s.status = "archived"
            if s.archived_at is None:
                s.archived_at = now
            s.updated_at = now
            if s.id not in archived_old_ids:
                archived_old_ids.append(s.id)
    except Exception:
        pass

    new_session = ChatSession(
        user_id=current_user.id,
        session_type=session_type,
        title=data.title or "新对话",
        family_member_id=family_member_id,
        message_count=0,
        is_pinned=False,
        is_deleted=False,
        status="active",
        last_active_at=now,
    )
    db.add(new_session)
    await db.flush()
    await db.refresh(new_session)

    return {
        "id": new_session.id,
        "session_type": session_type.value if hasattr(session_type, "value") else str(session_type),
        "title": new_session.title,
        "family_member_id": new_session.family_member_id,
        "family_member_relation": family_member_relation,
        "family_member_nickname": family_member_nickname,
        "message_count": 0,
        "is_pinned": False,
        "status": new_session.status,
        "last_active_at": new_session.last_active_at.isoformat() if new_session.last_active_at else None,
        "archived_previous_session_id": data.archive_previous_session_id,
        "archived_old_ids": archived_old_ids,
        "created_at": new_session.created_at.isoformat() if new_session.created_at else None,
        "updated_at": new_session.updated_at.isoformat() if new_session.updated_at else None,
    }


# [BUG-466 (2026-05-11)] 新增「会话归档」接口
# 用于将指定会话标记为「已归档」（不删除，仅推 updated_at 到当前时间），
# 确保抽屉历史列表按"最近活动"排序时立刻被提到顶部。
# 既可被切咨询对象主流程合并到创建接口里使用，也可单独被前端撤销动作调用。
@router.post("/api/chat-sessions/{session_id}/archive")
async def user_archive_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将指定会话标记为「已归档」。

    [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 真正修改 status='archived'，并写入 archived_at。
    - 不删除消息、不修改 `is_deleted`、不修改其它业务字段
    - 仅会话属于当前用户、未删除时生效；否则返回 404
    - 幂等：已是 archived 状态时不报错，archived_at 保留首次归档时间
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    now = datetime.utcnow()
    session.status = "archived"
    if session.archived_at is None:
        session.archived_at = now
    session.updated_at = now
    await db.flush()
    return {
        "message": "归档成功",
        "id": session.id,
        "status": session.status,
        "archived_at": session.archived_at.isoformat() if session.archived_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


# [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 新增获取当前活跃会话接口
@router.get("/api/chat-sessions/active")
async def user_get_active_session(
    consult_target_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户在指定咨询对象下的 active 会话；不存在时返回 {"session": null}。"""
    query = (
        select(ChatSession)
        .options(selectinload(ChatSession.family_member))
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
            ChatSession.status == "active",
        )
    )
    if consult_target_id is not None:
        try:
            tid = int(consult_target_id)
        except Exception:
            tid = -1
        if tid > 0:
            query = query.where(ChatSession.family_member_id == tid)
        else:
            query = query.where(ChatSession.family_member_id.is_(None))
    query = query.order_by(ChatSession.last_active_at.desc(), ChatSession.updated_at.desc()).limit(1)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        return {"session": None}
    return {
        "session": {
            "id": session.id,
            "session_type": session.session_type.value if hasattr(session.session_type, "value") else str(session.session_type),
            "title": session.title,
            "family_member_id": session.family_member_id,
            "message_count": session.message_count or 0,
            "status": session.status,
            "is_pinned": bool(session.is_pinned),
            "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
    }


# [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 新增恢复（resume）接口
@router.post("/api/chat-sessions/{session_id}/resume")
async def user_resume_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """把已归档会话恢复为 active；同事务把同咨询对象下的旧 active 会话归档。

    返回：
      - session: 被恢复的会话详情
      - archived_old_ids: 被归档的旧 active 会话 id 数组
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="对话不存在")

    now = datetime.utcnow()
    archived_old_ids: List[int] = []
    try:
        existing_active = await db.execute(
            select(ChatSession).where(
                ChatSession.user_id == current_user.id,
                ChatSession.is_deleted == False,
                ChatSession.status == "active",
                ChatSession.id != target.id,
            )
        )
        for s in existing_active.scalars().all():
            s.status = "archived"
            if s.archived_at is None:
                s.archived_at = now
            s.updated_at = now
            archived_old_ids.append(s.id)
    except Exception:
        pass

    target.status = "active"
    target.last_active_at = now
    target.updated_at = now
    # resume 后清掉 archived_at，便于后续如果再次归档时取最新时间
    target.archived_at = None
    await db.flush()
    return {
        "message": "恢复成功",
        "session": {
            "id": target.id,
            "session_type": target.session_type.value if hasattr(target.session_type, "value") else str(target.session_type),
            "title": target.title,
            "family_member_id": target.family_member_id,
            "message_count": target.message_count or 0,
            "status": target.status,
            "is_pinned": bool(target.is_pinned),
            "last_active_at": target.last_active_at.isoformat() if target.last_active_at else None,
            "updated_at": target.updated_at.isoformat() if target.updated_at else None,
        },
        "archived_old_ids": archived_old_ids,
    }


# [BUG-461 业务规则② (2026-05-11)] 检查是否应该开启新会话
# 前端在进入 AI 对话页时调用，依据 AI_CHAT_AUTO_NEW_SESSION_HOURS 阈值判断
# 上一活动会话是否已超过 N 小时未活动；如超过则提示前端开新会话。
@router.get("/api/chat-sessions/active-check")
async def user_check_active_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """检查用户上一次活动会话是否需要切片为新会话。

    返回：
      - should_new_session: bool  是否建议开新会话
      - last_session_id: int|None 上一次活动会话 ID
      - last_updated_at: ISO 时间字符串
      - inactive_hours: float    距上次活动的小时数
      - threshold_hours: int     阈值（来自 AI_CHAT_AUTO_NEW_SESSION_HOURS）

    判定逻辑：取该用户最近一条 `updated_at` 最大的非删除会话，
    若距今 ≥ 阈值则 should_new_session=True。
    """
    threshold = max(1, int(getattr(settings, "AI_CHAT_AUTO_NEW_SESSION_HOURS", 6) or 6))
    try:
        result = await db.execute(
            select(ChatSession)
            .where(
                ChatSession.user_id == current_user.id,
                ChatSession.is_deleted == False,
            )
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
    except Exception:
        last = None

    if last is None:
        return {
            "should_new_session": False,
            "last_session_id": None,
            "last_updated_at": None,
            "inactive_hours": 0.0,
            "threshold_hours": threshold,
        }

    now = datetime.utcnow()
    last_ts = last.updated_at or last.created_at or now
    delta = now - last_ts
    inactive_hours = max(0.0, delta.total_seconds() / 3600.0)
    return {
        "should_new_session": inactive_hours >= threshold,
        "last_session_id": last.id,
        "last_updated_at": last_ts.isoformat() if last_ts else None,
        "inactive_hours": round(inactive_hours, 2),
        "threshold_hours": threshold,
    }


@router.get("/api/chat-sessions/{session_id}")
async def user_get_session_detail(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages), selectinload(ChatSession.family_member))
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = [
        {
            "id": m.id,
            "role": m.role.value if hasattr(m.role, "value") else m.role,
            "content": m.content,
            "message_type": m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            "file_url": m.file_url,
            "image_urls": m.image_urls,
            "file_urls": m.file_urls,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in session.messages
    ]

    # [BUG-460 (2026-05-11)] 详情接口同步加固字段健壮性：family_member 关联可能为 None，
    # session_type/枚举字段历史脏数据兜底，避免 selectinload 关联缺失时 500。
    try:
        session_type_value = (
            session.session_type.value if hasattr(session.session_type, "value") else (session.session_type or "consultation")
        )
    except Exception:
        session_type_value = "consultation"

    family_member_relation = "self"
    family_member_nickname = None
    if session.family_member is not None:
        try:
            family_member_relation = _normalize_relation(
                getattr(session.family_member, "relationship_type", None)
            )
            family_member_nickname = getattr(session.family_member, "nickname", None)
        except Exception:
            pass

    return {
        "id": session.id,
        "session_type": session_type_value,
        "title": session.title,
        "family_member_id": session.family_member_id,
        "family_member_relation": family_member_relation,
        "family_member_nickname": family_member_nickname,
        "message_count": session.message_count or 0,
        "is_pinned": bool(session.is_pinned) if session.is_pinned is not None else False,
        # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 透出 status / archived_at / last_active_at
        "status": session.status or "archived",
        "archived_at": session.archived_at.isoformat() if session.archived_at else None,
        "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": messages,
    }


@router.put("/api/chat-sessions/{session_id}")
async def user_update_session(
    session_id: int,
    data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.title = data.title
    await db.flush()
    await db.refresh(session)
    return {"message": "更新成功", "title": session.title}


@router.put("/api/chat-sessions/{session_id}/pin")
async def user_pin_session(
    session_id: int,
    data: ChatSessionPinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.is_pinned = data.is_pinned
    session.pinned_at = datetime.utcnow() if data.is_pinned else None
    await db.flush()
    return {"message": "操作成功", "is_pinned": session.is_pinned}


@router.post("/api/chat-sessions/batch-delete")
async def user_batch_delete_sessions(
    session_ids: List[int] = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not session_ids:
        raise HTTPException(status_code=400, detail="请提供需要删除的对话ID列表")

    await db.execute(
        update(ChatSession)
        .where(
            ChatSession.id.in_(session_ids),
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
        .values(is_deleted=True)
    )
    await db.flush()
    return {"message": "批量删除成功"}


@router.delete("/api/chat-sessions/clear-all")
async def user_clear_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
        .values(is_deleted=True)
    )
    await db.flush()
    return {"message": "已清空全部对话"}


@router.delete("/api/chat-sessions/{session_id}")
async def user_delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.is_deleted = True
    await db.flush()
    return {"message": "删除成功"}


@router.post("/api/chat-sessions/{session_id}/share")
async def user_share_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    if not session.share_token:
        session.share_token = uuid.uuid4().hex
        await db.flush()

    return {
        "share_token": session.share_token,
        "share_url": f"/api/shared/chat/{session.share_token}",
    }


# ──────────────── 分享页 API (公开) ────────────────


@router.get("/api/shared/chat/{share_token}")
async def get_shared_chat(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.share_token == share_token, ChatSession.is_deleted == False)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="分享链接不存在或已失效")

    messages = [
        SharedChatMessageItem(
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            message_type=m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            file_url=m.file_url,
            image_urls=m.image_urls,
            file_urls=m.file_urls,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return SharedChatResponse(
        title=session.title,
        session_type=session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        message_count=session.message_count or 0,
        created_at=session.created_at,
        messages=messages,
    )
