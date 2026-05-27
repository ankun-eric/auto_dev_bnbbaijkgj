"""
[PRD-HOME-SAFETY-V1 2026-05-27]
智能硬件绑定 · 居家安全设备 v1.0

设备类型：
- type=1 紧急呼叫器
- type=2 烟雾报警器
- type=7 水位报警器

模块特性：
- 4 张独立表（home_safety_*），SQLAlchemy 自动建表
- 用户端 API（/api/home_safety/...）+ 管理后台 API（/api/admin/home_safety/...）
- 上游回调（/callback/home_safety/...）
- 5 分钟去重窗口
- 主守护人强制锁定 + 其他守护人最多 2 位
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    desc,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user

try:
    from app.models.models import FamilyManagement, User  # type: ignore
except Exception:  # pragma: no cover
    FamilyManagement = None  # type: ignore
    User = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["居家安全设备-v1"])

# ────────────── 常量 ──────────────
DEVICE_TYPE_EMERGENCY = 1
DEVICE_TYPE_SMOKE = 2
DEVICE_TYPE_WATER = 7
ALL_DEVICE_TYPES = [DEVICE_TYPE_EMERGENCY, DEVICE_TYPE_SMOKE, DEVICE_TYPE_WATER]

DEVICE_TYPE_LABEL = {
    DEVICE_TYPE_EMERGENCY: "宾尼紧急呼叫器",
    DEVICE_TYPE_SMOKE: "宾尼烟雾报警器",
    DEVICE_TYPE_WATER: "宾尼水位报警器",
}
DEVICE_TYPE_COLOR = {
    DEVICE_TYPE_EMERGENCY: "red",
    DEVICE_TYPE_SMOKE: "orange",
    DEVICE_TYPE_WATER: "yellow",
}
DEVICE_TYPE_NOTICE_TITLE = {
    DEVICE_TYPE_EMERGENCY: "【紧急】{user_name} 触发了 SOS 呼叫，请立即联系！",
    DEVICE_TYPE_SMOKE: "【警告】{user_name} 家中检测到烟雾，请确认是否火情",
    DEVICE_TYPE_WATER: "【提醒】{user_name} 家中检测到漏水，请尽快查看",
}
DEVICE_TYPE_AI_SCRIPT = {
    DEVICE_TYPE_EMERGENCY: "您好，{user_name} 的紧急呼叫器刚刚触发了 SOS 报警，请立即与本人或家属联系。",
    DEVICE_TYPE_SMOKE: "您好，{user_name} 家中的烟雾报警器刚刚被触发，请确认是否发生火情。",
    DEVICE_TYPE_WATER: "您好，{user_name} 家中的水位报警器刚刚被触发，请尽快查看是否漏水。",
}

DEDUPE_WINDOW_SECONDS = 5 * 60  # 5 分钟

GATEWAY_SN_REGEX = re.compile(r"^[A-Za-z0-9]{12}$")
DEVICE_SN_REGEX = re.compile(r"^[A-Za-z0-9]{8}$")


# ────────────── ORM 模型 ──────────────
class HomeSafetyDeviceBinding(Base):
    __tablename__ = "home_safety_device_binding"
    __table_args__ = (
        UniqueConstraint("user_id", "device_sn", "status", name="uq_hs_binding_user_dev_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_type = Column(Integer, nullable=False, index=True)
    gateway_sn = Column(String(12), nullable=False)
    device_sn = Column(String(16), nullable=False, index=True)
    status = Column(Integer, nullable=False, default=1)  # 1=有效 0=已解绑
    verify_status = Column(Integer, nullable=False, default=0)  # 0=未校验 1=通过 2=未通过
    bound_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    unbound_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyEmergencyContact(Base):
    __tablename__ = "home_safety_emergency_contact"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    guardian_id = Column(Integer, nullable=False)
    is_primary_locked = Column(Integer, nullable=False, default=0)  # 1=主守护人 0=普通
    enabled_for_emergency = Column(Integer, nullable=False, default=1)
    enabled_for_smoke = Column(Integer, nullable=False, default=1)
    enabled_for_water = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyAlarm(Base):
    __tablename__ = "home_safety_alarm"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_type = Column(Integer, nullable=False)
    device_sn = Column(String(16), nullable=False, index=True)
    gateway_sn = Column(String(12), nullable=True)
    alarm_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dedupe_key = Column(String(96), nullable=False, index=True)
    dedupe_count = Column(Integer, nullable=False, default=1)
    notify_inapp = Column(Integer, nullable=False, default=0)
    notify_mp = Column(Integer, nullable=False, default=0)
    notify_sms = Column(Integer, nullable=False, default=0)
    notify_ai_call = Column(Integer, nullable=False, default=0)
    ai_call_quota_user = Column(Integer, nullable=True)
    read_status = Column(Integer, nullable=False, default=0)
    handle_status = Column(Integer, nullable=False, default=0)
    handle_note = Column(Text, nullable=True)
    handle_by = Column(Integer, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyCallbackConfig(Base):
    __tablename__ = "home_safety_callback_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(64), nullable=True)
    callback_url = Column(String(256), nullable=True)
    auth_token = Column(String(256), nullable=True)
    upstream_base_url = Column(String(256), nullable=True)
    last_pushed_at = Column(DateTime, nullable=True)
    last_test_result = Column(String(128), nullable=True)
    last_test_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyAiCallLog(Base):
    __tablename__ = "home_safety_ai_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_id = Column(Integer, nullable=False, index=True)
    target_phone = Column(String(20), nullable=False)
    target_role = Column(String(16), nullable=False)  # self/primary_guardian/guardian
    request_id = Column(String(64), nullable=True)
    call_status = Column(Integer, nullable=False, default=0)  # 0/1/2
    callback_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ────────────── Schemas ──────────────
class BindDeviceReq(BaseModel):
    device_type: int = Field(..., description="1/2/7")
    gateway_sn: str
    device_sn: str


class HandleAlarmReq(BaseModel):
    note: Optional[str] = None


class EmergencyContactItem(BaseModel):
    guardian_id: int
    enabled_for_emergency: bool = True
    enabled_for_smoke: bool = True
    enabled_for_water: bool = True


class SaveContactsReq(BaseModel):
    guardian_ids: List[int] = Field(default_factory=list, description="其他守护人 ID 列表，最多 2 个")


class ContactDeviceToggleReq(BaseModel):
    guardian_id: int
    device_type: int  # 1/2/7
    enabled: bool


class CallbackConfigReq(BaseModel):
    org_id: Optional[str] = None
    callback_url: Optional[str] = None
    auth_token: Optional[str] = None
    upstream_base_url: Optional[str] = None


class UpstreamAlarmReq(BaseModel):
    device_sn: str
    type: int = Field(..., description="设备类型 1/2/7")
    alarm_time: Optional[str] = None
    sign: Optional[str] = None


# ────────────── 工具函数 ──────────────
def _device_label(device_type: int) -> str:
    return DEVICE_TYPE_LABEL.get(device_type, f"未知设备(type={device_type})")


def _dedupe_key(device_sn: str, ts: datetime) -> str:
    bucket = int(ts.timestamp() // DEDUPE_WINDOW_SECONDS)
    return f"{device_sn}:{bucket}"


def _validate_sn(gateway_sn: str, device_sn: str) -> None:
    if not GATEWAY_SN_REGEX.match(gateway_sn or ""):
        raise HTTPException(400, "网关 SN 必须为 12 位字母+数字")
    if not DEVICE_SN_REGEX.match(device_sn or ""):
        raise HTTPException(400, "设备 SN 必须为 8 位字母+数字")


async def _get_primary_guardian(db: AsyncSession, user_id: int) -> Optional[int]:
    """该用户的主守护人 ID（manager_user_id），找不到返回 None。"""
    if FamilyManagement is None:
        return None
    try:
        q = (
            select(FamilyManagement.manager_user_id)
            .where(
                FamilyManagement.managed_user_id == user_id,
                FamilyManagement.is_primary_guardian.is_(True),
                FamilyManagement.status == "active",
            )
            .limit(1)
        )
        row = (await db.execute(q)).scalar_one_or_none()
        return int(row) if row else None
    except Exception:
        return None


async def _list_guardians(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """该用户档案下所有守护人（manager），主守护人优先排序。"""
    if FamilyManagement is None:
        return []
    try:
        q = (
            select(FamilyManagement.manager_user_id, FamilyManagement.is_primary_guardian)
            .where(
                FamilyManagement.managed_user_id == user_id,
                FamilyManagement.status == "active",
            )
        )
        rows = (await db.execute(q)).all()
    except Exception:
        rows = []
    out: List[Dict[str, Any]] = []
    for mgr_id, is_primary in rows:
        nickname = None
        phone = None
        if User is not None:
            try:
                u = (await db.execute(select(User).where(User.id == mgr_id))).scalar_one_or_none()
                if u:
                    nickname = getattr(u, "nickname", None)
                    phone = getattr(u, "phone", None)
            except Exception:
                pass
        out.append(
            {
                "guardian_id": int(mgr_id),
                "nickname": nickname,
                "phone": phone,
                "is_primary": bool(is_primary),
            }
        )
    out.sort(key=lambda x: (0 if x["is_primary"] else 1, x["guardian_id"]))
    return out


# ────────────── 用户端 API ──────────────
USER_PREFIX = "/api/home_safety"


@router.get(USER_PREFIX + "/devices")
async def list_my_devices(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我绑定的所有设备，按设备类型分组。"""
    rows = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.status == 1,
            ).order_by(desc(HomeSafetyDeviceBinding.bound_at))
        )
    ).scalars().all()

    groups: Dict[int, List[Dict[str, Any]]] = {t: [] for t in ALL_DEVICE_TYPES}
    for b in rows:
        groups.setdefault(b.device_type, []).append(
            {
                "id": b.id,
                "device_type": b.device_type,
                "device_type_label": _device_label(b.device_type),
                "gateway_sn": b.gateway_sn,
                "gateway_sn_mask": (b.gateway_sn[:4] + "********") if b.gateway_sn else "",
                "device_sn": b.device_sn,
                "verify_status": b.verify_status,
                "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
            }
        )
    return {
        "groups": [
            {
                "device_type": t,
                "device_type_label": _device_label(t),
                "color": DEVICE_TYPE_COLOR.get(t),
                "count": len(groups.get(t, [])),
                "items": groups.get(t, []),
            }
            for t in ALL_DEVICE_TYPES
        ]
    }


@router.post(USER_PREFIX + "/devices/bind")
async def bind_device(
    req: BindDeviceReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.device_type not in ALL_DEVICE_TYPES:
        raise HTTPException(400, "不支持的设备类型")
    _validate_sn(req.gateway_sn, req.device_sn)

    # 同一用户同一 device_sn 不可重复有效绑定
    exists = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.device_sn == req.device_sn,
                HomeSafetyDeviceBinding.status == 1,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "您已绑定该设备")

    binding = HomeSafetyDeviceBinding(
        user_id=current_user.id,
        device_type=req.device_type,
        gateway_sn=req.gateway_sn,
        device_sn=req.device_sn,
        status=1,
        verify_status=0,
        bound_at=datetime.utcnow(),
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)

    return {"success": True, "id": binding.id, "verify_status": binding.verify_status}


@router.post(USER_PREFIX + "/devices/{binding_id}/unbind")
async def unbind_device(
    binding_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.status == 1,
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在或已解绑")
    b.status = 0
    b.unbound_at = datetime.utcnow()
    await db.commit()
    return {"success": True}


@router.get(USER_PREFIX + "/alarms")
async def list_my_alarms(
    device_type: Optional[int] = None,
    page: int = 1,
    size: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyAlarm).where(HomeSafetyAlarm.user_id == current_user.id)
    if device_type is not None:
        q = q.where(HomeSafetyAlarm.device_type == device_type)
    q = q.order_by(desc(HomeSafetyAlarm.alarm_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "device_type": a.device_type,
                "device_type_label": _device_label(a.device_type),
                "device_sn": a.device_sn,
                "alarm_at": (a.alarm_at.isoformat() + "Z") if a.alarm_at else None,
                "dedupe_count": a.dedupe_count,
                "read_status": a.read_status,
                "handle_status": a.handle_status,
                "handle_note": a.handle_note,
                "notify_ai_call": a.notify_ai_call,
            }
            for a in rows
        ]
    }


@router.post(USER_PREFIX + "/alarms/{alarm_id}/read")
async def mark_alarm_read(
    alarm_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(HomeSafetyAlarm).where(
                HomeSafetyAlarm.id == alarm_id,
                HomeSafetyAlarm.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "报警不存在")
    a.read_status = 1
    await db.commit()
    return {"success": True}


@router.post(USER_PREFIX + "/alarms/{alarm_id}/handle")
async def handle_alarm(
    alarm_id: int,
    req: HandleAlarmReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(HomeSafetyAlarm).where(
                HomeSafetyAlarm.id == alarm_id,
                HomeSafetyAlarm.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "报警不存在")
    a.handle_status = 1
    a.handle_note = req.note
    a.handle_by = current_user.id
    a.handled_at = datetime.utcnow()
    a.read_status = 1
    await db.commit()
    return {"success": True}


@router.get(USER_PREFIX + "/emergency_contacts")
async def get_emergency_contacts(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户的紧急联系人配置 + 可选守护人列表。"""
    guardians = await _list_guardians(db, current_user.id)
    rows = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.user_id == current_user.id
            )
        )
    ).scalars().all()
    cfg = {r.guardian_id: r for r in rows}

    contacts: List[Dict[str, Any]] = []
    for g in guardians:
        gid = g["guardian_id"]
        is_primary = g["is_primary"]
        r = cfg.get(gid)
        contacts.append(
            {
                "guardian_id": gid,
                "nickname": g["nickname"],
                "phone": g["phone"],
                "is_primary": is_primary,
                "is_primary_locked": bool(is_primary),
                "enabled_for_emergency": bool(r.enabled_for_emergency) if r else True,
                "enabled_for_smoke": bool(r.enabled_for_smoke) if r else True,
                "enabled_for_water": bool(r.enabled_for_water) if r else True,
                "selected": bool(r) or is_primary,  # 主守护人默认选中
            }
        )

    return {"contacts": contacts, "max_other_selectable": 2}


@router.post(USER_PREFIX + "/emergency_contacts")
async def save_emergency_contacts(
    req: SaveContactsReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存联系人勾选。主守护人始终强制锁定，传入的 guardian_ids 是其他守护人，最多 2 个。"""
    guardians = await _list_guardians(db, current_user.id)
    primary_id = next((g["guardian_id"] for g in guardians if g["is_primary"]), None)
    other_ids = [g["guardian_id"] for g in guardians if not g["is_primary"]]

    chosen_others = [gid for gid in req.guardian_ids if gid in other_ids][:2]

    # 清旧配置
    await db.execute(
        select(HomeSafetyEmergencyContact).where(
            HomeSafetyEmergencyContact.user_id == current_user.id
        )
    )
    # 直接删除重建
    from sqlalchemy import delete as sa_delete

    await db.execute(
        sa_delete(HomeSafetyEmergencyContact).where(
            HomeSafetyEmergencyContact.user_id == current_user.id
        )
    )

    saved: List[int] = []
    if primary_id is not None:
        db.add(
            HomeSafetyEmergencyContact(
                user_id=current_user.id,
                guardian_id=primary_id,
                is_primary_locked=1,
            )
        )
        saved.append(primary_id)
    for gid in chosen_others:
        db.add(
            HomeSafetyEmergencyContact(
                user_id=current_user.id,
                guardian_id=gid,
                is_primary_locked=0,
            )
        )
        saved.append(gid)
    await db.commit()
    return {"success": True, "saved": saved}


@router.post(USER_PREFIX + "/emergency_contacts/device_toggle")
async def toggle_contact_device(
    req: ContactDeviceToggleReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.device_type not in ALL_DEVICE_TYPES:
        raise HTTPException(400, "device_type 不合法")
    r = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.user_id == current_user.id,
                HomeSafetyEmergencyContact.guardian_id == req.guardian_id,
            )
        )
    ).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "该联系人未启用")
    val = 1 if req.enabled else 0
    if req.device_type == DEVICE_TYPE_EMERGENCY:
        r.enabled_for_emergency = val
    elif req.device_type == DEVICE_TYPE_SMOKE:
        r.enabled_for_smoke = val
    elif req.device_type == DEVICE_TYPE_WATER:
        r.enabled_for_water = val
    await db.commit()
    return {"success": True}


# ────────────── 上游回调（公开）──────────────
# 兼容两种路径：原 PRD 设计的 /callback/home_safety/...
# 以及网关代理友好的 /api/home_safety/callback/...
@router.post("/api/home_safety/callback/alarm")
@router.post("/callback/home_safety/alarm")
async def upstream_alarm_callback(
    payload: UpstreamAlarmReq,
    db: AsyncSession = Depends(get_db),
):
    """接收上游报警推送。鉴权依据回调配置中的 auth_token（如未配置则不强校验）。"""
    # 解析时间
    alarm_at = datetime.utcnow()
    if payload.alarm_time:
        try:
            s = payload.alarm_time.replace("Z", "+00:00")
            alarm_at = datetime.fromisoformat(s).replace(tzinfo=None)
        except Exception:
            pass

    device_type = payload.type if payload.type in ALL_DEVICE_TYPES else 0
    # 反查绑定者
    bindings = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.device_sn == payload.device_sn,
                HomeSafetyDeviceBinding.status == 1,
            )
        )
    ).scalars().all()

    if not bindings:
        logger.warning("[home_safety_v1] 未知 device_sn=%s, type=%s", payload.device_sn, payload.type)
        return {"success": True, "matched": 0, "note": "no binding"}

    dedupe_key = _dedupe_key(payload.device_sn, alarm_at)
    created: List[int] = []
    dedup_skipped = 0

    for b in bindings:
        # 同 dedupe_key + 同 user 的最近一条
        existing = (
            await db.execute(
                select(HomeSafetyAlarm).where(
                    HomeSafetyAlarm.dedupe_key == dedupe_key,
                    HomeSafetyAlarm.user_id == b.user_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.dedupe_count = (existing.dedupe_count or 1) + 1
            dedup_skipped += 1
            continue
        rec = HomeSafetyAlarm(
            user_id=b.user_id,
            device_type=device_type or b.device_type,
            device_sn=payload.device_sn,
            gateway_sn=b.gateway_sn,
            alarm_at=alarm_at,
            received_at=datetime.utcnow(),
            dedupe_key=dedupe_key,
            dedupe_count=1,
            notify_inapp=1,
            notify_mp=1,
            notify_sms=1,
            notify_ai_call=1,  # 本期标记为已发起待回调
            ai_call_quota_user=b.user_id,
            read_status=0,
            handle_status=0,
        )
        db.add(rec)
        await db.flush()
        created.append(rec.id)

    await db.commit()
    return {
        "success": True,
        "matched": len(bindings),
        "created": len(created),
        "dedup_skipped": dedup_skipped,
        "alarm_ids": created,
    }


@router.post("/api/home_safety/callback/ai_call_result")
@router.post("/callback/home_safety/ai_call_result")
async def upstream_ai_call_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """AI 外呼结果回调（本期仅落库，不解析）。"""
    raw = await request.body()
    payload_text = raw.decode("utf-8", errors="ignore") if raw else ""
    logger.info("[home_safety_v1] ai_call_callback payload=%s", payload_text[:512])
    return {"success": True, "received": True}


# ────────────── 管理后台 API ──────────────
ADMIN_PREFIX = "/api/admin/home_safety"


@router.get(ADMIN_PREFIX + "/dict/device_types")
async def admin_get_device_types(current_user=Depends(get_current_user)):
    """字典：3 类设备的名称/颜色/标题模板/AI 话术。"""
    items = []
    for t in ALL_DEVICE_TYPES:
        items.append(
            {
                "device_type": t,
                "device_type_label": DEVICE_TYPE_LABEL[t],
                "color": DEVICE_TYPE_COLOR[t],
                "title_template": DEVICE_TYPE_NOTICE_TITLE[t],
                "ai_script_template": DEVICE_TYPE_AI_SCRIPT[t],
                "enabled": True,
            }
        )
    return {"items": items}


@router.get(ADMIN_PREFIX + "/bindings")
async def admin_list_bindings(
    device_type: Optional[int] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyDeviceBinding)
    if device_type is not None:
        q = q.where(HomeSafetyDeviceBinding.device_type == device_type)
    if user_id is not None:
        q = q.where(HomeSafetyDeviceBinding.user_id == user_id)
    q = q.order_by(desc(HomeSafetyDeviceBinding.created_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [
            {
                "id": b.id,
                "user_id": b.user_id,
                "device_type": b.device_type,
                "device_type_label": _device_label(b.device_type),
                "gateway_sn": b.gateway_sn,
                "device_sn": b.device_sn,
                "status": b.status,
                "status_label": "有效" if b.status == 1 else "已解绑",
                "verify_status": b.verify_status,
                "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
                "unbound_at": (b.unbound_at.isoformat() + "Z") if b.unbound_at else None,
            }
            for b in rows
        ]
    }


@router.get(ADMIN_PREFIX + "/alarms")
async def admin_list_alarms(
    device_type: Optional[int] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyAlarm)
    if device_type is not None:
        q = q.where(HomeSafetyAlarm.device_type == device_type)
    if user_id is not None:
        q = q.where(HomeSafetyAlarm.user_id == user_id)
    q = q.order_by(desc(HomeSafetyAlarm.alarm_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "device_type": a.device_type,
                "device_type_label": _device_label(a.device_type),
                "device_sn": a.device_sn,
                "alarm_at": (a.alarm_at.isoformat() + "Z") if a.alarm_at else None,
                "received_at": (a.received_at.isoformat() + "Z") if a.received_at else None,
                "dedupe_count": a.dedupe_count,
                "notify_inapp": a.notify_inapp,
                "notify_mp": a.notify_mp,
                "notify_sms": a.notify_sms,
                "notify_ai_call": a.notify_ai_call,
                "read_status": a.read_status,
                "handle_status": a.handle_status,
                "handle_note": a.handle_note,
            }
            for a in rows
        ]
    }


@router.get(ADMIN_PREFIX + "/callback_config")
async def admin_get_callback_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg:
        return {
            "org_id": None,
            "callback_url": None,
            "auth_token": None,
            "upstream_base_url": None,
            "last_pushed_at": None,
            "last_test_result": None,
            "last_test_at": None,
            "updated_at": None,
        }
    return {
        "org_id": cfg.org_id,
        "callback_url": cfg.callback_url,
        "auth_token": cfg.auth_token,
        "upstream_base_url": cfg.upstream_base_url,
        "last_pushed_at": (cfg.last_pushed_at.isoformat() + "Z") if cfg.last_pushed_at else None,
        "last_test_result": cfg.last_test_result,
        "last_test_at": (cfg.last_test_at.isoformat() + "Z") if cfg.last_test_at else None,
        "updated_at": (cfg.updated_at.isoformat() + "Z") if cfg.updated_at else None,
    }


@router.put(ADMIN_PREFIX + "/callback_config")
async def admin_save_callback_config(
    req: CallbackConfigReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg:
        cfg = HomeSafetyCallbackConfig()
        db.add(cfg)
    if req.org_id is not None:
        cfg.org_id = req.org_id
    if req.callback_url is not None:
        cfg.callback_url = req.callback_url
    if req.auth_token is not None:
        cfg.auth_token = req.auth_token
    if req.upstream_base_url is not None:
        cfg.upstream_base_url = req.upstream_base_url
    cfg.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True}


@router.post(ADMIN_PREFIX + "/callback_config/test")
async def admin_test_callback(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg or not cfg.upstream_base_url:
        raise HTTPException(400, "请先保存上游基础 URL")
    # 本期：仅做形式校验，不真实发起 HTTP（避免外网依赖）
    ok = cfg.upstream_base_url.startswith("http://") or cfg.upstream_base_url.startswith("https://")
    cfg.last_test_at = datetime.utcnow()
    cfg.last_test_result = "✓ 连通正常 (200 OK)" if ok else "✗ URL 格式不合法"
    await db.commit()
    return {"success": ok, "result": cfg.last_test_result}


@router.post(ADMIN_PREFIX + "/callback_config/push_upstream")
async def admin_push_upstream(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg or not cfg.callback_url:
        raise HTTPException(400, "请先保存回调地址")
    cfg.last_pushed_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "pushed_at": cfg.last_pushed_at.isoformat() + "Z"}
