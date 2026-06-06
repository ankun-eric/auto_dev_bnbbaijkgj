"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 守护人体系一致性 + 真删除 + 配额防护 Bug 修复

PRD：「我守护的人」与「AI 首页选择咨询人」列表不一致 + 真删除 + 配额防护

新增/修改：
- DELETE /api/guardian/v13/family/member/{member_id}  真删除接口（R1-R4 闸门 + 8 张表硬删 + 3 类引用断开）
- 频次防护：50 次/UID/自然日（内存计数器，Redis 不可用时降级；仅成功才计数）
  注：删除成员的限流已统一收口到 family_member_v2.py，本文件不再拦截 delete_member
- 守护人邀请 nickname 必填
- AI 对话级联清理（chat_sessions + chat_messages）
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, delete as sql_delete, func, or_, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ChatMessage,
    ChatSession,
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    HealthProfile,
    MedicationReminder,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guardian/v13", tags=["守护人体系-真删除-v1"])

# [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 频次防护：每日上限 5→50。
# 同时从受控动作中移除 delete_member —— 删除成员的限流统一收口到
# family_member_v2.py 那一套，消除「双重拦截」。
RATE_LIMIT_PER_DAY = 50
RATE_LIMIT_ACTIONS = ("invite_create", "unguard")

# 内存频次计数器（key: "{action}:{uid}:{yyyymmdd}" → count）
# Redis 不可用时的兜底实现；进程级生效；多实例需要换 Redis（PRD 已定降级策略）
_rate_counter: dict[str, int] = defaultdict(int)
_rate_lock = Lock()
_rate_last_cleanup: date = date.today()


def _rate_limit_key(action: str, uid: int, today: date) -> str:
    return f"rate_limit:{action}:{uid}:{today.strftime('%Y%m%d')}"


def _cleanup_old_counters_unsafe(today: date) -> None:
    """清理过期日期的计数器（在持锁状态下调用）"""
    global _rate_last_cleanup
    if today == _rate_last_cleanup:
        return
    today_key = today.strftime("%Y%m%d")
    stale_keys = [k for k in _rate_counter if not k.endswith(today_key)]
    for k in stale_keys:
        _rate_counter.pop(k, None)
    _rate_last_cleanup = today


def _rate_limit_label(action: str) -> str:
    """[BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 超限文案（不再写死具体次数）。"""
    return {
        "invite_create": "今天创建邀请的次数已达上限，明天再继续吧～如有特殊情况请联系客服",
        "unguard": "今天解除守护的次数已达上限，明天再继续吧～如有特殊情况请联系客服",
    }.get(action, "今日操作次数已达上限，请明天再试")


def check_rate_limit_only(action: str, uid: int) -> None:
    """[BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 只查不记账；超限抛 429。

    若 action 不在受控列表中，直接放行。
    """
    if action not in RATE_LIMIT_ACTIONS:
        return
    today = datetime.now().date()
    key = _rate_limit_key(action, uid, today)
    with _rate_lock:
        _cleanup_old_counters_unsafe(today)
        if _rate_counter.get(key, 0) >= RATE_LIMIT_PER_DAY:
            raise HTTPException(status_code=429, detail=_rate_limit_label(action))


def incr_rate_limit(action: str, uid: int) -> None:
    """[BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 仅记一次账（不抛异常）。

    在动作真正成功之后调用，确保「点了取消 / 被其他规则拦住没成功」都不计入额度。
    """
    if action not in RATE_LIMIT_ACTIONS:
        return
    today = datetime.now().date()
    key = _rate_limit_key(action, uid, today)
    with _rate_lock:
        _cleanup_old_counters_unsafe(today)
        _rate_counter[key] = _rate_counter.get(key, 0) + 1


def check_and_incr_rate_limit(action: str, uid: int) -> None:
    """[兼容保留] 检查并递增频次计数；超限抛 429 异常。

    若 action 不在受控列表中，直接放行（兼容未来扩展）。
    新代码请改用「先 check_rate_limit_only 再在成功后 incr_rate_limit」的两步式。
    """
    if action not in RATE_LIMIT_ACTIONS:
        return
    check_rate_limit_only(action, uid)
    incr_rate_limit(action, uid)


def peek_rate_limit_used(action: str, uid: int) -> int:
    """查看当前已使用次数（不递增），主要用于调试 / 测试"""
    today = datetime.now().date()
    key = _rate_limit_key(action, uid, today)
    with _rate_lock:
        return _rate_counter.get(key, 0)


def reset_rate_limit_for_test(uid: int | None = None) -> None:
    """仅供测试使用：清空指定用户（或全部）的计数器"""
    with _rate_lock:
        if uid is None:
            _rate_counter.clear()
            return
        prefix_list = [f"rate_limit:{a}:{uid}:" for a in RATE_LIMIT_ACTIONS]
        keys = [k for k in list(_rate_counter.keys()) if any(k.startswith(p) for p in prefix_list)]
        for k in keys:
            _rate_counter.pop(k, None)


# ─────────── 工具：闸门校验 ───────────


async def _check_has_bound_device(db: AsyncSession, managed_user_id: Optional[int]) -> bool:
    """R2：检查是否有绑定中的硬件设备（home_safety_device_binding.status=1 有效绑定）"""
    if not managed_user_id:
        return False
    try:
        from app.api.home_safety_v1 import HomeSafetyDeviceBinding  # type: ignore
        res = await db.execute(
            select(func.count(HomeSafetyDeviceBinding.id)).where(
                HomeSafetyDeviceBinding.user_id == managed_user_id,
                HomeSafetyDeviceBinding.status == 1,
            )
        )
        return int(res.scalar() or 0) > 0
    except Exception as e:
        logger.warning("[guardian-bugfix] check device failed: %s", e)
        return False


async def _check_has_pending_invitation(
    db: AsyncSession, *, inviter_user_id: int, member_id: int
) -> bool:
    """R3：检查是否有未取消的 pending 邀请"""
    now = datetime.now()
    res = await db.execute(
        select(func.count(FamilyInvitation.id)).where(
            FamilyInvitation.inviter_user_id == inviter_user_id,
            FamilyInvitation.member_id == member_id,
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at > now,
        )
    )
    return int(res.scalar() or 0) > 0


async def _check_has_active_medication(
    db: AsyncSession, *, managed_user_id: Optional[int], member_id: int
) -> bool:
    """R4：检查是否有进行中的服药计划（关联 family_member_id 或 user_id）"""
    try:
        q = select(func.count(MedicationReminder.id)).where(
            MedicationReminder.status == "active",
            MedicationReminder.is_paused == False,  # noqa: E712
        )
        if managed_user_id:
            q = q.where(
                or_(
                    MedicationReminder.family_member_id == member_id,
                    MedicationReminder.user_id == managed_user_id,
                )
            )
        else:
            q = q.where(MedicationReminder.family_member_id == member_id)
        res = await db.execute(q)
        return int(res.scalar() or 0) > 0
    except Exception as e:
        logger.warning("[guardian-bugfix] check medication failed: %s", e)
        return False


# ─────────── 数据量预览（最终确认弹窗用） ───────────


class DeleteImpactPreview(BaseModel):
    health_profile_count: int = 0
    health_report_count: int = 0
    medication_reminder_count: int = 0
    ai_conversation_count: int = 0
    ai_message_count: int = 0
    emergency_contact_ref_count: int = 0


async def _calc_delete_impact(
    db: AsyncSession,
    *,
    member: FamilyMember,
    managed_user_id: Optional[int],
) -> DeleteImpactPreview:
    impact = DeleteImpactPreview()

    # 1. health_profile（按 family_member_id 或 user_id）
    hp_q = select(func.count(HealthProfile.id)).where(
        HealthProfile.family_member_id == member.id
    )
    impact.health_profile_count = int((await db.execute(hp_q)).scalar() or 0)

    # 2. health_report（尝试通过 ChatSession.report_id 没有直接关联；保守取 0）
    impact.health_report_count = 0

    # 3. medication_reminder
    med_q = select(func.count(MedicationReminder.id)).where(
        MedicationReminder.family_member_id == member.id
    )
    impact.medication_reminder_count = int((await db.execute(med_q)).scalar() or 0)

    # 4. AI 对话（chat_sessions）
    cs_q = select(func.count(ChatSession.id)).where(
        ChatSession.family_member_id == member.id
    )
    impact.ai_conversation_count = int((await db.execute(cs_q)).scalar() or 0)

    # 5. AI 消息（chat_messages 通过 session_id 关联）
    cs_ids_q = select(ChatSession.id).where(ChatSession.family_member_id == member.id)
    cs_ids = [r[0] for r in (await db.execute(cs_ids_q)).all()]
    if cs_ids:
        msg_q = select(func.count(ChatMessage.id)).where(
            ChatMessage.session_id.in_(cs_ids)
        )
        impact.ai_message_count = int((await db.execute(msg_q)).scalar() or 0)

    # 6. emergency_contact 引用（home_safety_emergency_contact）
    try:
        from app.api.home_safety_v1 import HomeSafetyEmergencyContact  # type: ignore
        ec_q = select(func.count(HomeSafetyEmergencyContact.id)).where(
            HomeSafetyEmergencyContact.guardian_id == member.id
        )
        impact.emergency_contact_ref_count = int((await db.execute(ec_q)).scalar() or 0)
    except Exception:
        impact.emergency_contact_ref_count = 0

    return impact


# ─────────── 接口 ───────────


@router.get("/family/member/{member_id}/delete-preview")
async def get_delete_preview(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] 真删除前的影响预览（前端弹窗用）

    返回数据量清单 + 闸门校验结果，前端用于显示最终确认弹窗。
    """
    member = await db.get(FamilyMember, member_id)
    if not member or member.user_id != current_user.id or member.status == "deleted":
        raise HTTPException(status_code=404, detail="家庭成员不存在或已被删除")
    if member.is_self:
        raise HTTPException(status_code=400, detail="本人档案不可删除")

    # 找关联的 FamilyManagement
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member.id,
        ).order_by(FamilyManagement.created_at.desc())
    )
    mgmt = mgmt_res.scalars().first()
    managed_user_id = mgmt.managed_user_id if mgmt else None

    # R1 闸门：active 状态不可删
    r1_pass = True
    r1_msg = None
    if mgmt and mgmt.status == "active":
        r1_pass = False
        r1_msg = "请先解除守护关系，再来彻底删除"

    # R2 闸门：硬件设备
    has_device = await _check_has_bound_device(db, managed_user_id)
    r2_pass = not has_device
    r2_msg = "请先在『设备管理』解绑该家人名下的设备" if has_device else None

    # R3 闸门：pending 邀请
    has_pending = await _check_has_pending_invitation(
        db, inviter_user_id=current_user.id, member_id=member.id
    )
    r3_pass = not has_pending
    r3_msg = "请先撤回未接受的邀请" if has_pending else None

    # R4 闸门：在途服药计划
    has_med = await _check_has_active_medication(
        db, managed_user_id=managed_user_id, member_id=member.id
    )
    r4_pass = not has_med
    r4_msg = "请先终止该家人名下的服药计划" if has_med else None

    impact = await _calc_delete_impact(db, member=member, managed_user_id=managed_user_id)

    return {
        "member_id": member.id,
        "member_nickname": member.nickname or "未命名成员",
        "can_delete": r1_pass and r2_pass and r3_pass and r4_pass,
        "gates": {
            "r1_not_active": {"pass": r1_pass, "message": r1_msg},
            "r2_no_device": {"pass": r2_pass, "message": r2_msg},
            "r3_no_pending_invitation": {"pass": r3_pass, "message": r3_msg},
            "r4_no_active_medication": {"pass": r4_pass, "message": r4_msg},
        },
        "impact": impact.model_dump(),
    }


@router.delete("/family/member/{member_id}")
async def delete_family_member_hard(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] 真删除（物理删 8 张表 + 断开 3 类引用）

    前置校验（R1~R4 全部通过才允许删除）：
    - R1: 关联 family_management 状态不能为 active
    - R2: 不能有绑定中的硬件设备
    - R3: 不能有 pending 邀请
    - R4: 不能有进行中的服药计划

    硬删表（8 张）：
    1. family_member（档案本体）
    2. family_management（守护关系记录）
    3. family_invitation（邀请记录）
    4. health_profile（健康档案）
    5. health_report（暂未关联，跳过）
    6. medication_reminder（用药提醒）
    7. chat_sessions（AI 对话）
    8. chat_messages（AI 消息）

    断开引用（3 类）：
    1. home_safety_device_binding：保留（R2 已校验，理论上无引用）
    2. home_safety_emergency_contact：guardian_id=该成员的记录置为 0 或软标记
    3. 对方账户的镜像档案：不动
    """
    # [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 移除此处的删除频次拦截：
    # 删除成员的限流统一收口到 family_member_v2.py 那一套，消除「双重拦截」。
    member = await db.get(FamilyMember, member_id)
    if not member or member.user_id != current_user.id or member.status == "deleted":
        raise HTTPException(status_code=404, detail="家庭成员不存在或已被删除")
    if member.is_self:
        raise HTTPException(status_code=400, detail="本人档案不可删除")

    # 找关联的 FamilyManagement
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member.id,
        )
    )
    mgmts = mgmt_res.scalars().all()
    managed_user_id = next((m.managed_user_id for m in mgmts if m.managed_user_id), None)

    # R1：active 状态不允许真删
    has_active_mgmt = any(m.status == "active" for m in mgmts)
    if has_active_mgmt:
        raise HTTPException(status_code=400, detail="请先解除守护关系，再来彻底删除")

    # R2：硬件设备
    if await _check_has_bound_device(db, managed_user_id):
        raise HTTPException(status_code=400, detail="请先在『设备管理』解绑该家人名下的设备")

    # R3：pending 邀请
    if await _check_has_pending_invitation(
        db, inviter_user_id=current_user.id, member_id=member.id
    ):
        raise HTTPException(status_code=400, detail="请先撤回未接受的邀请")

    # R4：服药计划
    if await _check_has_active_medication(
        db, managed_user_id=managed_user_id, member_id=member.id
    ):
        raise HTTPException(status_code=400, detail="请先终止该家人名下的服药计划")

    # 计算影响（用于返回）
    impact = await _calc_delete_impact(db, member=member, managed_user_id=managed_user_id)

    # === 开始事务级联硬删 ===

    # 8. chat_messages（先删，避免外键）
    cs_ids_q = select(ChatSession.id).where(ChatSession.family_member_id == member.id)
    cs_ids = [r[0] for r in (await db.execute(cs_ids_q)).all()]
    if cs_ids:
        await db.execute(sql_delete(ChatMessage).where(ChatMessage.session_id.in_(cs_ids)))

    # 7. chat_sessions
    await db.execute(sql_delete(ChatSession).where(ChatSession.family_member_id == member.id))

    # 6. medication_reminder
    await db.execute(
        sql_delete(MedicationReminder).where(MedicationReminder.family_member_id == member.id)
    )

    # 4. health_profile
    await db.execute(
        sql_delete(HealthProfile).where(HealthProfile.family_member_id == member.id)
    )

    # 3. family_invitation（按 member_id；按 inviter_user_id 限定本人发起的）
    await db.execute(
        sql_delete(FamilyInvitation).where(
            FamilyInvitation.member_id == member.id,
            FamilyInvitation.inviter_user_id == current_user.id,
        )
    )

    # 2. family_management
    for m in mgmts:
        await db.delete(m)

    # 断开引用：home_safety_emergency_contact（如有 guardian_id 引用该 member）
    try:
        from app.api.home_safety_v1 import HomeSafetyEmergencyContact  # type: ignore
        ec_rows_q = await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.guardian_id == member.id
            )
        )
        for ec in ec_rows_q.scalars().all():
            # 标记为已删除：guardian_id=-1 + enabled=0
            ec.guardian_id = -1
            ec.enabled_for_emergency = 0
            ec.enabled_for_smoke = 0
            ec.enabled_for_water = 0
    except Exception:
        pass

    # 1. family_member（最后删，因为有外键约束）
    await db.delete(member)

    await db.flush()

    # 推送 WebSocket / 长轮询事件（如有 notification 系统）
    try:
        from app.models.models import Notification, NotificationType  # type: ignore
        db.add(Notification(
            user_id=current_user.id,
            title="档案已彻底删除",
            content=f"档案「{member.nickname or '未命名成员'}」及其关联数据已彻底删除",
            type=NotificationType.system,
            extra_data={
                "type": "conversation_target_deleted",
                "deleted_member_id": member_id,
                "via": "guardian_bugfix_v1",
            },
        ))
        await db.flush()
    except Exception:
        pass

    return {
        "deleted": True,
        "member_id": member_id,
        "impact": impact.model_dump(),
        "message": "已彻底删除",
        "event": "conversation_target_deleted",
    }


# ─────────── 解除守护：包装原接口，加 R1 校验 + 频次防护 ───────────


class UnguardRequest(BaseModel):
    management_id: int


@router.post("/family/relation/unguard")
async def unguard_relation(
    payload: UnguardRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] 解除守护关系（带频次防护）

    与 DELETE /api/family/management/{id} 行为一致，但增加 50 次/天频次防护
    （仅成功才计数）。
    """
    # [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 先查不记账
    check_rate_limit_only("unguard", current_user.id)

    mgmt = await db.get(FamilyManagement, payload.management_id)
    if not mgmt:
        raise HTTPException(status_code=404, detail="管理关系不存在")
    if mgmt.manager_user_id != current_user.id and mgmt.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此管理关系")
    if mgmt.status != "active":
        raise HTTPException(status_code=400, detail="该守护关系已不在生效中")

    # 如果是被守护人主动退出 → cancelled_by_target；如果是守护人解除 → cancelled
    if mgmt.managed_user_id == current_user.id:
        mgmt.status = "cancelled_by_target"
    else:
        mgmt.status = "cancelled"
    mgmt.cancelled_at = datetime.now()
    mgmt.cancelled_by = current_user.id

    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V2 2026-06-03] 治本：守护关系取消同步回滚 FamilyMember
    from app.services.family_member_status_rollback import (
        rollback_member_for_management_cancel,
    )
    await rollback_member_for_management_cancel(
        db,
        manager_user_id=mgmt.manager_user_id,
        managed_member_id=mgmt.managed_member_id,
    )

    await db.flush()

    # [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 仅在成功解除后才记一次额度
    incr_rate_limit("unguard", current_user.id)

    return {"message": "已解除守护", "management_id": mgmt.id, "status": mgmt.status}
