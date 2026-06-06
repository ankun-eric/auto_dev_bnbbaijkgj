"""[PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 健康档案页面优化 V1 后端接口。

本模块实现 PRD 中以下后端能力：

1. F5 邀请共管增强：复用现有 /api/family/invitation，本模块仅补充 GET 当前主账号下某 family_member
   的最新一份待接受邀请的查询接口。

2. F7 AI 外呼提醒（按被守护人维度，单层结构）：
   - GET  /api/health-archive/ai-call/settings           查询当前主账号下所有被守护人 + 自己的 AI 外呼配置
   - GET  /api/health-archive/ai-call/settings/{target}  查询单个被守护人维度的 AI 外呼配置
   - PUT  /api/health-archive/ai-call/settings/{target}  更新单个被守护人维度的 AI 外呼配置

3. F9 被守护人「TA 的设备」只读视图：
   - GET  /api/health-archive/guardian/{managed_user_id}/devices  以主账号视角只读查看被守护人名下的设备列表
   - POST /api/health-archive/guardian/{managed_user_id}/devices/remind-bind  提醒 TA 绑定设备（发送站内通知）

4. F5/F2 已守护 N 人快捷计数（与 family/management 兼容，简化前端调用）：
   - GET  /api/health-archive/guardian/summary  返回 {managed_count, managed_user_ids}

5. F2 用药计划"被守护"角标聚合：
   - GET  /api/health-archive/family-members/guarded-flags  返回每个家庭成员是否被本人守护
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyManagement,
    FamilyMember,
    GuardianAiCallSetting,
    Notification,
    NotificationType,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health-archive", tags=["健康档案优化 V1"])

# 默认外呼配置
DEFAULT_DND_START = "22:00"
DEFAULT_DND_END = "07:00"
DEFAULT_CALL_TARGET = "self"  # self=被守护人本人；guardian=守护者


# ───────────────────── Pydantic Schemas ─────────────────────

class AiCallSettingItem(BaseModel):
    target_user_id: int
    target_nickname: Optional[str] = None
    is_self: bool = False
    enabled: bool = False
    dnd_start: str = DEFAULT_DND_START
    dnd_end: str = DEFAULT_DND_END
    call_target: str = DEFAULT_CALL_TARGET
    has_guardian: bool = False


class AiCallSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    dnd_start: Optional[str] = Field(None, max_length=8)
    dnd_end: Optional[str] = Field(None, max_length=8)
    call_target: Optional[str] = Field(None, description="self | guardian")


class GuardianSummary(BaseModel):
    managed_count: int = 0
    managed_user_ids: List[int] = []
    managed_member_ids: List[int] = []


class DeviceItem(BaseModel):
    id: int
    device_type: str
    device_name: Optional[str] = None
    status: str = "active"
    last_sync_at: Optional[datetime] = None
    bound_at: Optional[datetime] = None


# ───────────────────── 工具函数 ─────────────────────


async def _list_managed_targets(db: AsyncSession, owner_user_id: int) -> List[Dict[str, Any]]:
    """返回 owner 视角下需要 AI 外呼配置的 target 列表：本人 + 已守护的家人。"""
    # owner 本人
    res_self = await db.execute(select(User).where(User.id == owner_user_id))
    self_user = res_self.scalar_one_or_none()
    out: List[Dict[str, Any]] = []
    if self_user:
        out.append({
            "target_user_id": owner_user_id,
            "target_nickname": self_user.nickname or "本人",
            "is_self": True,
            "has_guardian": False,
        })

    # 已守护的被守护人
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == owner_user_id,
            FamilyManagement.status == "active",
        )
    )
    mgmts = res.scalars().all()
    for m in mgmts:
        u_res = await db.execute(select(User).where(User.id == m.managed_user_id))
        u = u_res.scalar_one_or_none()
        out.append({
            "target_user_id": m.managed_user_id,
            "target_nickname": (u.nickname if u else None) or f"用户#{m.managed_user_id}",
            "is_self": False,
            "has_guardian": True,
        })
    return out


async def _get_or_default_setting(
    db: AsyncSession, owner_user_id: int, target_user_id: int
) -> GuardianAiCallSetting:
    res = await db.execute(
        select(GuardianAiCallSetting).where(
            GuardianAiCallSetting.owner_user_id == owner_user_id,
            GuardianAiCallSetting.target_user_id == target_user_id,
        )
    )
    setting = res.scalar_one_or_none()
    if setting is None:
        setting = GuardianAiCallSetting(
            owner_user_id=owner_user_id,
            target_user_id=target_user_id,
            enabled=False,
            dnd_start=DEFAULT_DND_START,
            dnd_end=DEFAULT_DND_END,
            call_target=DEFAULT_CALL_TARGET,
        )
        # 不立即提交，仅返回默认实例供读取
    return setting


def _setting_to_item(
    setting: GuardianAiCallSetting,
    target_nickname: Optional[str],
    is_self: bool,
    has_guardian: bool,
) -> AiCallSettingItem:
    call_target = setting.call_target or DEFAULT_CALL_TARGET
    # 业务约束：外呼对象选 guardian 但当前无守护关系 → 回退为 self
    if call_target == "guardian" and not has_guardian:
        call_target = "self"
    return AiCallSettingItem(
        target_user_id=setting.target_user_id,
        target_nickname=target_nickname,
        is_self=is_self,
        enabled=bool(setting.enabled),
        dnd_start=setting.dnd_start or DEFAULT_DND_START,
        dnd_end=setting.dnd_end or DEFAULT_DND_END,
        call_target=call_target,
        has_guardian=has_guardian,
    )


# ───────────────────── 接口 ─────────────────────


@router.get("/ai-call/settings")
async def list_ai_call_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前主账号下所有 AI 外呼配置（本人 + 已守护的家人）。"""
    targets = await _list_managed_targets(db, current_user.id)
    items: List[AiCallSettingItem] = []
    for t in targets:
        setting = await _get_or_default_setting(db, current_user.id, t["target_user_id"])
        items.append(_setting_to_item(setting, t.get("target_nickname"), t["is_self"], t["has_guardian"]))
    return {"items": [it.model_dump() for it in items], "total": len(items)}


@router.get("/ai-call/settings/{target_user_id}")
async def get_ai_call_setting(
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询单个被守护人/本人的 AI 外呼配置。"""
    # 权限校验：target 必须是本人或已守护对象
    is_self = target_user_id == current_user.id
    has_guardian = False
    target_nickname: Optional[str] = None
    if not is_self:
        mgmt_res = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == target_user_id,
                FamilyManagement.status == "active",
            )
        )
        mgmt = mgmt_res.scalar_one_or_none()
        if mgmt is None:
            raise HTTPException(status_code=403, detail="无权访问该被守护人的 AI 外呼配置")
        has_guardian = True
        u_res = await db.execute(select(User).where(User.id == target_user_id))
        u = u_res.scalar_one_or_none()
        target_nickname = (u.nickname if u else None) or f"用户#{target_user_id}"
    else:
        target_nickname = current_user.nickname or "本人"

    setting = await _get_or_default_setting(db, current_user.id, target_user_id)
    return _setting_to_item(setting, target_nickname, is_self, has_guardian).model_dump()


@router.put("/ai-call/settings/{target_user_id}")
async def update_ai_call_setting(
    target_user_id: int,
    data: AiCallSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新单个被守护人/本人的 AI 外呼配置（单层结构，被守护人名下所有用药计划共用）。"""
    # 权限校验
    is_self = target_user_id == current_user.id
    has_guardian = False
    if not is_self:
        mgmt_res = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == target_user_id,
                FamilyManagement.status == "active",
            )
        )
        mgmt = mgmt_res.scalar_one_or_none()
        if mgmt is None:
            raise HTTPException(status_code=403, detail="无权配置该被守护人的 AI 外呼")
        has_guardian = True

    res = await db.execute(
        select(GuardianAiCallSetting).where(
            GuardianAiCallSetting.owner_user_id == current_user.id,
            GuardianAiCallSetting.target_user_id == target_user_id,
        )
    )
    setting = res.scalar_one_or_none()
    if setting is None:
        setting = GuardianAiCallSetting(
            owner_user_id=current_user.id,
            target_user_id=target_user_id,
            enabled=False,
            dnd_start=DEFAULT_DND_START,
            dnd_end=DEFAULT_DND_END,
            call_target=DEFAULT_CALL_TARGET,
        )
        db.add(setting)
        await db.flush()

    if data.enabled is not None:
        setting.enabled = bool(data.enabled)
    if data.dnd_start is not None:
        setting.dnd_start = data.dnd_start or None
    if data.dnd_end is not None:
        setting.dnd_end = data.dnd_end or None
    if data.call_target is not None:
        if data.call_target not in ("self", "guardian"):
            raise HTTPException(status_code=400, detail="call_target 只能是 self 或 guardian")
        # 外呼对象选 guardian 但无守护关系 → 自动回退 self
        if data.call_target == "guardian" and not has_guardian:
            setting.call_target = "self"
        else:
            setting.call_target = data.call_target

    setting.updated_at = datetime.now()
    await db.flush()

    target_nickname: Optional[str] = None
    if is_self:
        target_nickname = current_user.nickname or "本人"
    else:
        u_res = await db.execute(select(User).where(User.id == target_user_id))
        u = u_res.scalar_one_or_none()
        target_nickname = (u.nickname if u else None) or f"用户#{target_user_id}"
    return _setting_to_item(setting, target_nickname, is_self, has_guardian).model_dump()


@router.get("/guardian/summary", response_model=GuardianSummary)
async def guardian_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前主账号「已守护 N 人」聚合：返回数量与对应 user_id / member_id 列表。"""
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    mgmts = res.scalars().all()
    return GuardianSummary(
        managed_count=len(mgmts),
        managed_user_ids=[m.managed_user_id for m in mgmts],
        managed_member_ids=[m.managed_member_id for m in mgmts if m.managed_member_id is not None],
    )


@router.get("/family-members/guarded-flags")
async def family_members_guarded_flags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出本主账号下所有 family_member，标注其是否被本人守护（用于头像「被守护」角标）。

    返回：{ items: [ { member_id, is_self, guarded, managed_user_id } ] }
    """
    # 获取所有家庭成员
    mem_res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "bound",
        )
    )
    members = list(mem_res.scalars().all())

    # 获取已守护的 managed_member_id
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    mgmts = list(mgmt_res.scalars().all())
    guarded_member_ids = {m.managed_member_id for m in mgmts if m.managed_member_id is not None}
    member_to_user = {m.managed_member_id: m.managed_user_id for m in mgmts if m.managed_member_id is not None}

    items = []
    for m in members:
        # 本人自己不显示「被守护」角标
        is_self = bool(getattr(m, "is_self", False))
        guarded = (not is_self) and (m.id in guarded_member_ids)
        items.append({
            "member_id": m.id,
            "is_self": is_self,
            "guarded": guarded,
            "managed_user_id": member_to_user.get(m.id),
        })
    return {"items": items, "total": len(items)}


@router.get("/guardian/{managed_user_id}/devices")
async def list_managed_user_devices(
    managed_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD F9-3] TA 的设备（只读）。

    业务约束：一台设备只能绑定一个登录账号；主账号无法直接增/删/解绑被守护人名下的设备，
    本接口仅返回只读视图。
    """
    # 权限校验：必须当前是守护者
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        )
    )
    mgmt = mgmt_res.scalar_one_or_none()
    if mgmt is None:
        raise HTTPException(status_code=403, detail="无权查看该用户的设备")

    # 查询 DeviceBinding（models.py 中的版本，绑定到 user_id）
    from app.models.models import DeviceBinding  # 延迟 import，避免循环

    res = await db.execute(
        select(DeviceBinding).where(
            DeviceBinding.user_id == managed_user_id,
            DeviceBinding.status == "active",
        )
    )
    devices = list(res.scalars().all())
    items: List[Dict[str, Any]] = []
    for d in devices:
        items.append({
            "id": d.id,
            "device_type": d.device_type,
            "device_name": d.device_name,
            "device_sn": d.device_sn,
            "status": d.status,
            "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            "bound_at": d.bound_at.isoformat() if d.bound_at else None,
            "readonly": True,
        })
    return {"items": items, "total": len(items)}


@router.post("/guardian/{managed_user_id}/devices/remind-bind")
async def remind_bind_device(
    managed_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD F9-3] 当被守护人尚无设备时，提醒 TA 绑定设备（发送站内通知）。"""
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        )
    )
    mgmt = mgmt_res.scalar_one_or_none()
    if mgmt is None:
        raise HTTPException(status_code=403, detail="无权对该用户发送提醒")

    op_name = current_user.nickname or current_user.phone or "您的家人"
    db.add(Notification(
        user_id=managed_user_id,
        title="家人提醒您绑定设备",
        content=f"{op_name} 提醒您绑定健康监测设备，绑定后家人可在家庭守护中查看到您的健康数据。",
        type=NotificationType.system,
        extra_data={
            "type": "remind_bind_device",
            "from_user_id": current_user.id,
        },
    ))
    await db.flush()
    return {"message": "已提醒 TA 绑定设备"}
