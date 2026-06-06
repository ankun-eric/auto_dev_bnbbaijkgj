"""[PRD-HEALTH-OPT-V1 2026-05-14] 健康档案优化：AI 外呼用药提醒 API。

包含：
- GET    /api/medication-reminder/plans/{plan_id}/ai-call          获取该计划的 AI 外呼配置
- PUT    /api/medication-reminder/plans/{plan_id}/ai-call          开启/关闭/更新 AI 外呼
- GET    /api/ai-call/quota                                        当前用户当月剩余额度
- GET    /api/admin/ai-call/membership-levels                      admin 列出会员等级
- POST   /api/admin/ai-call/membership-levels                      admin 新增会员等级
- PUT    /api/admin/ai-call/membership-levels/{level_id}           admin 修改会员等级
- DELETE /api/admin/ai-call/membership-levels/{level_id}           admin 删除会员等级
- GET    /api/admin/ai-call/config                                 admin 读取全局配置
- PUT    /api/admin/ai-call/config                                 admin 更新全局配置
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    AiCallGlobalConfig,
    AiCallMembershipLevel,
    MedicationPlan,
    Notification,
    User,
    UserMembership,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["PRD-HEALTH-OPT-V1 AI 外呼"])


# ───────────── Pydantic Schemas ─────────────


class AiCallPlanConfigOut(BaseModel):
    plan_id: int
    ai_call_enabled: bool
    ai_call_dnd_start: str
    ai_call_dnd_end: str
    ai_call_target_user_id: Optional[int]
    target_phone_masked: Optional[str]
    quota_used: int
    quota_total: int
    quota_remaining: int
    membership_level_code: str
    membership_display_name: str


class AiCallPlanConfigUpdate(BaseModel):
    ai_call_enabled: Optional[bool] = None
    ai_call_dnd_start: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    ai_call_dnd_end: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    # 当管理人为被管人开启时，前端可显式指定 target_user_id（被管人 user_id）；
    # 若不传，则取计划主人的 user_id。
    ai_call_target_user_id: Optional[int] = None


class QuotaOut(BaseModel):
    level_code: str
    level_display_name: str
    monthly_quota: int
    used: int
    remaining: int


class MembershipLevelIn(BaseModel):
    level_code: str
    display_name: str
    monthly_quota: int = 30
    sort_order: int = 100
    is_active: bool = True


class MembershipLevelOut(MembershipLevelIn):
    id: int


class GlobalConfigIn(BaseModel):
    default_dnd_start: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    default_dnd_end: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    default_script_template: Optional[str] = None
    retry_max: Optional[int] = Field(default=None, ge=0, le=10)
    retry_interval_minutes: Optional[int] = Field(default=None, ge=1, le=60)
    rule_a_per_plan_once: Optional[bool] = None
    rule_b_charge_on_answer: Optional[bool] = None


class GlobalConfigOut(BaseModel):
    default_dnd_start: str
    default_dnd_end: str
    default_script_template: str
    retry_max: int
    retry_interval_minutes: int
    rule_a_per_plan_once: bool
    rule_b_charge_on_answer: bool


# ───────────── Helpers ─────────────


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


async def _ensure_membership(db: AsyncSession, user_id: int) -> UserMembership:
    res = await db.execute(select(UserMembership).where(UserMembership.user_id == user_id))
    m = res.scalar_one_or_none()
    current_month = datetime.now().strftime("%Y-%m")
    if m is None:
        m = UserMembership(
            user_id=user_id,
            level_code="normal",
            ai_call_quota_used_month=0,
            quota_reset_month=current_month,
        )
        db.add(m)
        await db.flush()
        return m
    if m.quota_reset_month != current_month:
        m.ai_call_quota_used_month = 0
        m.quota_reset_month = current_month
        await db.flush()
    return m


async def _get_level(db: AsyncSession, level_code: str) -> Optional[AiCallMembershipLevel]:
    res = await db.execute(
        select(AiCallMembershipLevel).where(AiCallMembershipLevel.level_code == level_code)
    )
    return res.scalar_one_or_none()


async def _get_global_config(db: AsyncSession) -> AiCallGlobalConfig:
    res = await db.execute(select(AiCallGlobalConfig).limit(1))
    cfg = res.scalar_one_or_none()
    if cfg is None:
        cfg = AiCallGlobalConfig()
        db.add(cfg)
        await db.flush()
    return cfg


# ───────────── User-facing endpoints ─────────────


@router.get("/medication-reminder/plans/{plan_id}/ai-call", response_model=AiCallPlanConfigOut)
async def get_plan_ai_call(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MedicationPlan).where(MedicationPlan.id == plan_id))
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    # 权限：计划创建者或被管人
    if plan.user_id != current_user.id and plan.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该计划")

    target_user_id = getattr(plan, "ai_call_target_user_id", None) or plan.patient_id or plan.user_id
    target_phone: Optional[str] = None
    res2 = await db.execute(select(User).where(User.id == target_user_id))
    target_user = res2.scalar_one_or_none()
    if target_user:
        target_phone = target_user.phone

    membership = await _ensure_membership(db, current_user.id)
    level = await _get_level(db, membership.level_code) or AiCallMembershipLevel(
        level_code="normal", display_name="免费会员", monthly_quota=30
    )
    quota_total = int(level.monthly_quota or 0)
    used = int(membership.ai_call_quota_used_month or 0)
    return AiCallPlanConfigOut(
        plan_id=plan.id,
        ai_call_enabled=bool(getattr(plan, "ai_call_enabled", False) or False),
        ai_call_dnd_start=getattr(plan, "ai_call_dnd_start", None) or "22:00",
        ai_call_dnd_end=getattr(plan, "ai_call_dnd_end", None) or "07:00",
        ai_call_target_user_id=target_user_id,
        target_phone_masked=mask_phone(target_phone),
        quota_used=used,
        quota_total=quota_total,
        quota_remaining=max(0, quota_total - used),
        membership_level_code=level.level_code,
        membership_display_name=level.display_name,
    )


@router.put("/medication-reminder/plans/{plan_id}/ai-call", response_model=AiCallPlanConfigOut)
async def update_plan_ai_call(
    plan_id: int,
    payload: AiCallPlanConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MedicationPlan).where(MedicationPlan.id == plan_id))
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    if plan.user_id != current_user.id and plan.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该计划")

    is_caregiver_for_other = False
    target_user_id = plan.patient_id or plan.user_id
    if payload.ai_call_target_user_id is not None:
        target_user_id = payload.ai_call_target_user_id

    # 校验被叫号码存在性：若被管人无注册手机号 → 拒绝开启
    if payload.ai_call_enabled is True:
        res2 = await db.execute(select(User).where(User.id == target_user_id))
        target_user = res2.scalar_one_or_none()
        if not target_user or not target_user.phone:
            # 兼容：FamilyMember 档案无注册手机号
            raise HTTPException(
                status_code=400, detail="该家属未注册 App，无法使用 AI 外呼"
            )
        # 额度校验
        membership = await _ensure_membership(db, current_user.id)
        level = await _get_level(db, membership.level_code)
        quota_total = int(level.monthly_quota if level else 30)
        if membership.ai_call_quota_used_month >= quota_total:
            raise HTTPException(status_code=402, detail="本月 AI 外呼额度已用完")
        if target_user_id != current_user.id:
            is_caregiver_for_other = True

    if payload.ai_call_enabled is not None:
        setattr(plan, "ai_call_enabled", payload.ai_call_enabled)
    if payload.ai_call_dnd_start is not None:
        setattr(plan, "ai_call_dnd_start", payload.ai_call_dnd_start)
    if payload.ai_call_dnd_end is not None:
        setattr(plan, "ai_call_dnd_end", payload.ai_call_dnd_end)
    setattr(plan, "ai_call_target_user_id", target_user_id)
    await db.flush()

    # 5.3 通知：管理人为被管人开启 → 发送站内信
    if is_caregiver_for_other and payload.ai_call_enabled is True:
        try:
            res3 = await db.execute(select(User).where(User.id == target_user_id))
            target_user = res3.scalar_one_or_none()
            phone_masked = mask_phone(target_user.phone if target_user else None) or ""
            content_text = (
                f"您的管理人 {current_user.nickname or current_user.phone or '管理人'} "
                f"已为您开启 {plan.drug_name} 的 AI 外呼提醒，到点会自动拨打您的电话 {phone_masked}。"
                "如有疑问，可在『健康档案 → 共管与提醒』中查看或关闭。"
            )
            n = Notification(
                user_id=target_user_id,
                title="AI 外呼用药提醒已开启",
                content=content_text,
                event_type="ai_call_enabled",
                extra_data={"plan_id": plan.id, "drug_name": plan.drug_name},
            )
            db.add(n)
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.warning("AI 外呼通知发送失败: %s", e)

    await db.commit()
    return await get_plan_ai_call(plan_id, current_user, db)


@router.get("/ai-call/quota", response_model=QuotaOut)
async def get_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await _ensure_membership(db, current_user.id)
    level = await _get_level(db, membership.level_code)
    if not level:
        level = AiCallMembershipLevel(level_code="normal", display_name="免费会员", monthly_quota=30)
    await db.commit()
    return QuotaOut(
        level_code=level.level_code,
        level_display_name=level.display_name,
        monthly_quota=int(level.monthly_quota),
        used=int(membership.ai_call_quota_used_month or 0),
        remaining=max(0, int(level.monthly_quota) - int(membership.ai_call_quota_used_month or 0)),
    )


# ───────────── Admin endpoints ─────────────

admin_router = APIRouter(prefix="/api/admin/ai-call", tags=["PRD-HEALTH-OPT-V1 admin"])


def _require_admin(user: User) -> None:
    role_val = getattr(user, "role", None)
    role_str = getattr(role_val, "value", None) or str(role_val or "")
    is_super = bool(getattr(user, "is_superuser", False))
    if not (is_super or role_str in ("admin", "superuser")):
        raise HTTPException(status_code=403, detail="需要管理员权限")


@admin_router.get("/membership-levels", response_model=list[MembershipLevelOut])
async def list_levels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    res = await db.execute(
        select(AiCallMembershipLevel).order_by(AiCallMembershipLevel.sort_order.asc(), AiCallMembershipLevel.id.asc())
    )
    rows = res.scalars().all()
    return [
        MembershipLevelOut(
            id=r.id,
            level_code=r.level_code,
            display_name=r.display_name,
            monthly_quota=int(r.monthly_quota),
            sort_order=int(r.sort_order or 100),
            is_active=bool(r.is_active),
        )
        for r in rows
    ]


@admin_router.post("/membership-levels", response_model=MembershipLevelOut)
async def create_level(
    payload: MembershipLevelIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    res = await db.execute(
        select(AiCallMembershipLevel).where(AiCallMembershipLevel.level_code == payload.level_code)
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="level_code 已存在")
    obj = AiCallMembershipLevel(**payload.dict())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return MembershipLevelOut(id=obj.id, **payload.dict())


@admin_router.put("/membership-levels/{level_id}", response_model=MembershipLevelOut)
async def update_level(
    level_id: int,
    payload: MembershipLevelIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    res = await db.execute(select(AiCallMembershipLevel).where(AiCallMembershipLevel.id == level_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="等级不存在")
    for k, v in payload.dict().items():
        setattr(obj, k, v)
    await db.commit()
    return MembershipLevelOut(id=obj.id, **payload.dict())


@admin_router.delete("/membership-levels/{level_id}")
async def delete_level(
    level_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    res = await db.execute(select(AiCallMembershipLevel).where(AiCallMembershipLevel.id == level_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="等级不存在")
    if obj.level_code in ("normal", "health"):
        raise HTTPException(status_code=400, detail="内置等级不可删除")
    await db.delete(obj)
    await db.commit()
    return {"ok": True}


@admin_router.get("/config", response_model=GlobalConfigOut)
async def get_admin_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    cfg = await _get_global_config(db)
    await db.commit()
    return GlobalConfigOut(
        default_dnd_start=cfg.default_dnd_start,
        default_dnd_end=cfg.default_dnd_end,
        default_script_template=cfg.default_script_template,
        retry_max=int(cfg.retry_max),
        retry_interval_minutes=int(cfg.retry_interval_minutes),
        rule_a_per_plan_once=bool(cfg.rule_a_per_plan_once),
        rule_b_charge_on_answer=bool(cfg.rule_b_charge_on_answer),
    )


@admin_router.put("/config", response_model=GlobalConfigOut)
async def update_admin_config(
    payload: GlobalConfigIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    cfg = await _get_global_config(db)
    for k, v in payload.dict(exclude_none=True).items():
        setattr(cfg, k, v)
    await db.commit()
    return await get_admin_config(current_user, db)
