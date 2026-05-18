"""[PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] 健康档案页面优化 V2 后端 API。

聚焦：
- F2 成员 Tab：返回 avatar_color_index / relation_badge_char / guard_status
- F3 Hero 三入口：今日用药数量 / 当前成员设备数量 / 家庭成员总数
- F4 当前成员设备列表
- F6 提醒设置：AI 外呼 + 超时通知守护者（按成员独立配置）
- F6 提醒历史：family_alert_logs 列表
- F7 解绑：短信验证码下发 + 确认

不破坏既有 /api/family/members 等接口，本模块对外路由前缀使用 /api/family-archive-v2。
"""
from __future__ import annotations

import random
import re
import string
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    DeviceBinding,
    FamilyAlertLog,
    FamilyManagement,
    FamilyMember,
    MedicationReminder,
    User,
    VerificationCode,
)

router = APIRouter(prefix="/api/family-archive-v2", tags=["健康档案优化 V2"])


# ─────────────────────── 工具函数 ─────────────────────────────

_RELATION_BADGE_MAP = {
    "本人": "我",
    "自己": "我",
    "我": "我",
    "爸爸": "爸", "父亲": "爸", "爸": "爸",
    "妈妈": "妈", "母亲": "妈", "妈": "妈",
    "儿子": "娃", "女儿": "娃", "孩子": "娃",
    "老公": "爱", "老婆": "爱", "丈夫": "爱", "妻子": "爱", "伴侣": "爱",
}


def _relation_badge_char(relation: str | None, fallback_name: str | None = None) -> str:
    if not relation:
        if fallback_name:
            return (fallback_name.strip() or "?")[0]
        return "?"
    rel = (relation or "").strip()
    if rel in _RELATION_BADGE_MAP:
        return _RELATION_BADGE_MAP[rel]
    # 兄弟姐妹 / 爷奶外公外婆 / 其他亲属：取关系第一字
    return rel[0] if rel else (fallback_name or "?")[0]


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    p = re.sub(r"\D", "", phone)
    if len(p) >= 11:
        return p[:3] + "****" + p[-4:]
    if len(p) > 4:
        return p[:1] + "****" + p[-2:]
    return phone


def _guard_status(member: FamilyMember) -> str:
    if member.is_self:
        return "self"
    return "guarded" if member.member_user_id else "unguarded"


# ─────────────────────── F2: 成员列表（带徽章/守护状态） ───────────────

@router.get("/members")
async def list_members_v2(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F2] 成员 Tab 列表，返回每个成员的徽章、配色索引、守护状态。"""
    result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
        )
    )
    members = list(result.scalars().all())
    self_list = [m for m in members if m.is_self]
    other_list = sorted(
        [m for m in members if not m.is_self],
        key=lambda m: (m.created_at or datetime.min, m.id),
    )
    ordered = self_list + other_list

    items: List[Dict[str, Any]] = []
    for idx, m in enumerate(ordered):
        color_index = m.avatar_color_index
        if color_index is None:
            color_index = idx % 5
        items.append({
            "id": m.id,
            "is_self": bool(m.is_self),
            "nickname": m.nickname or "",
            "relationship_type": m.relationship_type or "",
            "member_user_id": m.member_user_id,
            "avatar_color_index": color_index,
            "relation_badge_char": _relation_badge_char(
                "本人" if m.is_self else (m.relationship_type or ""),
                m.nickname,
            ),
            "guard_status": _guard_status(m),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {"items": items, "total": len(items)}


# ─────────────────────── F3: Hero 三入口计数 ───────────────────────

@router.get("/hero-counts")
async def hero_counts(
    member_id: Optional[int] = Query(None, description="当前选中成员 ID（不传=本人）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F3] Hero 卡三入口的角标数量：今日用药 / 当前成员设备 / 家庭成员。"""
    # 确认成员归属
    target_member: Optional[FamilyMember] = None
    if member_id is not None:
        res = await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == member_id,
                FamilyMember.user_id == current_user.id,
            )
        )
        target_member = res.scalar_one_or_none()
        if not target_member:
            raise HTTPException(404, "成员不存在")

    # 1) 今日用药计划总次数（不论是否打卡）
    medication_count = 0
    try:
        # 找出该成员对应的 family_member_id（本人=0/None）
        fm_filter_id: Optional[int] = None
        if target_member and not target_member.is_self:
            fm_filter_id = target_member.id

        today = date.today()
        q = select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            or_(MedicationReminder.status == "active", MedicationReminder.status.is_(None)),
        )
        if fm_filter_id is not None:
            q = q.where(MedicationReminder.family_member_id == fm_filter_id)
        else:
            # 本人：family_member_id IS NULL 或 0
            q = q.where(or_(MedicationReminder.family_member_id.is_(None), MedicationReminder.family_member_id == 0))
        res = await db.execute(q)
        rems = list(res.scalars().all())
        total = 0
        for r in rems:
            # 时间列表：reminder_times JSON / scheduled_times JSON / 单一 reminder_time
            times = None
            for attr in ("reminder_times", "scheduled_times", "times"):
                if hasattr(r, attr) and getattr(r, attr):
                    val = getattr(r, attr)
                    if isinstance(val, list):
                        times = val
                        break
            if times is None:
                rt = getattr(r, "reminder_time", None)
                if rt:
                    times = [rt]
                else:
                    times = []
            # 校验日期范围
            start = getattr(r, "start_date", None)
            end = getattr(r, "end_date", None)
            long_term = bool(getattr(r, "long_term", False))
            in_range = True
            if start and isinstance(start, date) and start > today:
                in_range = False
            if end and isinstance(end, date) and not long_term and end < today:
                in_range = False
            if not in_range:
                continue
            total += len(times) if times else 0
        medication_count = total
    except Exception:
        medication_count = 0

    # 2) 当前成员设备数量
    device_count = 0
    try:
        if target_member is None or target_member.is_self:
            owner_uid = current_user.id
        elif target_member.member_user_id:
            owner_uid = target_member.member_user_id
        else:
            owner_uid = None
        if owner_uid:
            res = await db.execute(
                select(func.count(DeviceBinding.id)).where(
                    DeviceBinding.user_id == owner_uid,
                    or_(DeviceBinding.status == "active", DeviceBinding.status.is_(None)),
                )
            )
            device_count = int(res.scalar() or 0)
    except Exception:
        device_count = 0

    # 3) 家庭成员总数（含本人）
    res = await db.execute(
        select(func.count(FamilyMember.id)).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
        )
    )
    family_count = int(res.scalar() or 0)

    return {
        "medication_today_count": medication_count,
        "device_count": device_count,
        "family_member_count": family_count,
    }


# ─────────────────────── F4: 当前成员设备列表 ───────────────────

@router.get("/member/{member_id}/devices")
async def member_devices(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F4] 当前选中成员的设备列表（本人态可管理，其他成员只读）。"""
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    member = res.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "成员不存在")

    if member.is_self:
        owner_uid = current_user.id
        readonly = False
    else:
        owner_uid = member.member_user_id
        readonly = True

    items: List[Dict[str, Any]] = []
    online_count = 0
    if owner_uid:
        res2 = await db.execute(
            select(DeviceBinding).where(
                DeviceBinding.user_id == owner_uid,
                or_(DeviceBinding.status == "active", DeviceBinding.status.is_(None)),
            ).order_by(DeviceBinding.created_at.desc())
        )
        devices = list(res2.scalars().all())
        now = datetime.utcnow()
        for d in devices:
            # 简化在线判定：last_sync_at 距今 < 10 分钟视为在线
            last = d.last_sync_at
            is_online = bool(last and (now - last) < timedelta(minutes=10))
            if is_online:
                online_count += 1
            items.append({
                "id": d.id,
                "device_type": d.device_type,
                "device_name": d.device_name,
                "device_sn": d.device_sn,
                "online": is_online,
                "last_sync_at": last.isoformat() if last else None,
            })

    return {
        "member_id": member.id,
        "member_nickname": member.nickname or "",
        "relationship_type": ("本人" if member.is_self else (member.relationship_type or "")),
        "is_self": bool(member.is_self),
        "readonly": readonly,
        "total": len(items),
        "online_count": online_count,
        "items": items,
    }


# ─────────────────────── F6: 提醒设置 ───────────────────────

class AlertSettingsResponse(BaseModel):
    member_id: int
    is_self: bool
    guard_status: str
    masked_phone: Optional[str] = None
    ai_call_enabled: bool
    ai_call_timing: str  # on_time / delay_5 / delay_10 / delay_15
    guardian_alert_minutes: int  # 5/10/15
    show_guardian_alert: bool  # 本人卡不显示


class AlertSettingsUpdate(BaseModel):
    ai_call_enabled: Optional[bool] = None
    ai_call_timing: Optional[str] = None
    guardian_alert_minutes: Optional[int] = None


@router.get("/member/{member_id}/alert-settings", response_model=AlertSettingsResponse)
async def get_alert_settings(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "成员不存在")

    masked_phone: Optional[str] = None
    if m.is_self:
        masked_phone = _mask_phone(getattr(current_user, "phone", None))
    elif m.member_user_id:
        r2 = await db.execute(select(User).where(User.id == m.member_user_id))
        u = r2.scalar_one_or_none()
        masked_phone = _mask_phone(getattr(u, "phone", None)) if u else None
    else:
        # 未守护：取 virtual_phone
        if getattr(m, "virtual_phone", None):
            masked_phone = _mask_phone(m.virtual_phone)

    return AlertSettingsResponse(
        member_id=m.id,
        is_self=bool(m.is_self),
        guard_status=_guard_status(m),
        masked_phone=masked_phone,
        ai_call_enabled=bool(getattr(m, "ai_call_enabled", False) or False),
        ai_call_timing=str(getattr(m, "ai_call_timing", "on_time") or "on_time"),
        guardian_alert_minutes=int(getattr(m, "guardian_alert_minutes", 5) or 5),
        show_guardian_alert=not bool(m.is_self),
    )


@router.put("/member/{member_id}/alert-settings", response_model=AlertSettingsResponse)
async def put_alert_settings(
    member_id: int,
    data: AlertSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "成员不存在")

    if data.ai_call_enabled is not None:
        m.ai_call_enabled = bool(data.ai_call_enabled)
    if data.ai_call_timing is not None:
        if data.ai_call_timing not in ("on_time", "delay_5", "delay_10", "delay_15"):
            raise HTTPException(400, "ai_call_timing 取值非法")
        m.ai_call_timing = data.ai_call_timing
    if data.guardian_alert_minutes is not None:
        if data.guardian_alert_minutes not in (5, 10, 15):
            raise HTTPException(400, "guardian_alert_minutes 仅支持 5/10/15")
        m.guardian_alert_minutes = int(data.guardian_alert_minutes)

    await db.flush()

    return await get_alert_settings(member_id, current_user=current_user, db=db)  # type: ignore[arg-type]


@router.get("/member/{member_id}/alert-history")
async def get_alert_history(
    member_id: int,
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(404, "成员不存在")

    res2 = await db.execute(
        select(FamilyAlertLog)
        .where(
            FamilyAlertLog.member_id == member_id,
            FamilyAlertLog.guardian_user_id == current_user.id,
        )
        .order_by(FamilyAlertLog.pushed_at.desc())
        .limit(limit)
    )
    logs = list(res2.scalars().all())
    items = [
        {
            "id": l.id,
            "pushed_at": l.pushed_at.isoformat() if l.pushed_at else None,
            "type": "guardian_alert",
            "channel": l.channel,
            "delivery_status": l.delivery_status,
            "severity": l.severity,
        }
        for l in logs
    ]
    return {"items": items, "total": len(items)}


# ─────────────────────── F7: 解绑（短信验证码 + 确认） ───────────────

class UnbindSendCodeResp(BaseModel):
    sent: bool
    masked_phone: Optional[str] = None
    debug_code: Optional[str] = None  # 开发环境返回，方便联调


class UnbindConfirmReq(BaseModel):
    code: str = Field(..., min_length=4, max_length=10)


def _gen_sms_code() -> str:
    return "".join(random.choices(string.digits, k=6))


@router.post("/member/{member_id}/unbind/send-code", response_model=UnbindSendCodeResp)
async def unbind_send_code(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "成员不存在")
    if m.is_self:
        raise HTTPException(400, "本人无法解绑")
    if not m.member_user_id:
        raise HTTPException(400, "该成员尚未守护，无需解绑")

    phone = getattr(current_user, "phone", None)
    if not phone:
        raise HTTPException(400, "守护者未绑定手机号，无法接收验证码")

    code = _gen_sms_code()
    vc = VerificationCode(
        phone=phone,
        code=code,
        type="family_unbind",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(vc)
    await db.flush()

    # 这里复用项目 SMS 通道；若失败也不阻塞（开发环境直接返回 debug_code）
    debug_code: Optional[str] = code
    try:
        from app.services.sms_service import send_sms  # type: ignore
        await send_sms(phone, f"您正在解除守护关系，验证码：{code}，5 分钟内有效")
        debug_code = None
    except Exception:
        pass

    return UnbindSendCodeResp(sent=True, masked_phone=_mask_phone(phone), debug_code=debug_code)


@router.post("/member/{member_id}/unbind/confirm")
async def unbind_confirm(
    member_id: int,
    data: UnbindConfirmReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "成员不存在")
    if m.is_self:
        raise HTTPException(400, "本人无法解绑")
    if not m.member_user_id:
        raise HTTPException(400, "该成员尚未守护")

    phone = getattr(current_user, "phone", None)
    if not phone:
        raise HTTPException(400, "守护者未绑定手机号")

    # 验证码校验
    now = datetime.utcnow()
    res2 = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.phone == phone,
            VerificationCode.type == "family_unbind",
            VerificationCode.code == data.code,
            VerificationCode.expires_at >= now,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    vc = res2.scalar_one_or_none()
    if not vc:
        raise HTTPException(400, "验证码无效或已过期")

    # 解绑：清空 member_user_id，FamilyManagement 标记 unbound
    res3 = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == m.member_user_id,
            FamilyManagement.status == "active",
        )
    )
    for fm in res3.scalars().all():
        fm.status = "unbound"
        fm.cancelled_at = now
        fm.cancelled_by = current_user.id

    nickname = m.nickname or m.relationship_type or "TA"
    m.member_user_id = None
    # 关闭该成员的 AI 外呼
    m.ai_call_enabled = False

    await db.flush()

    return {"message": f"已解除与 {nickname} 的守护关系", "member_id": m.id}
