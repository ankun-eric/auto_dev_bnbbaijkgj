import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    DiseasePreset,
    FamilyMember,
    HealthProfile,
    Notification,
    NotificationType,
    RelationType,
    User,
)
# [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 关系徽章字工具
from app.utils.relation_badge import relation_badge_char

logger = logging.getLogger(__name__)
from app.schemas.health_v2 import DiseasePresetResponse, RelationTypeResponse
from app.schemas.user import FamilyMemberCreate, FamilyMemberResponse, FamilyMemberUpdate

router = APIRouter(tags=["家庭成员"])


def _guard_status(member: FamilyMember) -> str:
    """[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2] 与 health_archive_optim_v2 保持一致的守护状态枚举。"""
    if member.is_self:
        return "self"
    return "guarded" if member.member_user_id else "unguarded"


def _to_member_response(member: FamilyMember) -> FamilyMemberResponse:
    relation_type_name = None
    if member.relation_type is not None:
        relation_type_name = member.relation_type.name
    return FamilyMemberResponse(
        id=member.id,
        user_id=member.user_id,
        member_user_id=member.member_user_id,
        relationship_type=member.relationship_type,
        nickname=member.nickname,
        is_self=member.is_self,
        relation_type_id=member.relation_type_id,
        relation_type_name=relation_type_name,
        birthday=member.birthday,
        gender=member.gender,
        height=member.height,
        weight=member.weight,
        medical_histories=member.medical_histories,
        allergies=member.allergies,
        status=member.status,
        created_at=member.created_at,
    )


def _enrich_member_dict(member: FamilyMember, fallback_color_index: int | None = None) -> dict:
    """[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 在 FamilyMemberResponse 基础上
    附加 avatar_color_index / relation_badge_char / guard_status 三个字段。

    fallback_color_index：当库内字段为 NULL 时（极少数旧数据），使用该值作为兜底。
    """
    base = _to_member_response(member).model_dump()
    color_index = member.avatar_color_index
    if color_index is None:
        color_index = fallback_color_index if fallback_color_index is not None else 0
    relation_for_badge = "本人" if member.is_self else (
        member.relationship_type or (member.relation_type.name if member.relation_type else "")
    )
    base["avatar_color_index"] = int(color_index) % 5
    base["relation_badge_char"] = relation_badge_char(relation_for_badge, member.nickname)
    base["guard_status"] = _guard_status(member)
    base["pending_invitation"] = None  # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 由 list_family_members 注入
    return base


@router.get("/api/family/members")
async def list_family_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-02 改动点3]
    # 顶部成员 Tab 与入口卡「已管理 N」的成员口径必须一致：
    # - 入口卡 count_managed_family_members 使用 status != 'deleted'
    # - 官方权威状态机 /api/family/member/state/list 使用 status != 'deleted'
    # - 旧口径 status == 'active' 会漏掉 cancelled_by_target / pending 等中间态
    # 现统一为「排除已软删除」语义。本项目历史上 DELETE 接口写入的是 'removed'，
    # 状态机接口约定的是 'deleted'，因此两个软删除标记都需排除。
    #
    # [BUGFIX-SELF-TAB-ALWAYS-VISIBLE-V1 2026-06-03] 本人记录(is_self=True)无视 status 过滤：
    # 早期注册流程历史脏数据可能把本人 status 写成 'pending' 等非 active 值（实测 6399 账号），
    # 本人作为账号持有者天然不应被任何业务状态过滤，必须永远出现在顶部 Tab 的第一位。
    # 因此过滤条件改为：本人记录直接放行；其余成员仍按"排除已软删除"口径。
    DELETED_STATUSES = ("deleted", "removed")
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(
            FamilyMember.user_id == current_user.id,
            or_(
                FamilyMember.is_self.is_(True),
                FamilyMember.status.notin_(DELETED_STATUSES),
            ),
        )
    )
    members = list(result.scalars().all())

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 本人永远第一，其余按 created_at 升序
    from datetime import datetime as _dt
    self_members = [m for m in members if m.is_self]
    other_members = sorted(
        [m for m in members if not m.is_self],
        key=lambda x: (x.created_at or _dt.min, x.id),
    )
    ordered = self_members + other_members

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 顺带回填配色（极少数 NULL 数据兜底）
    items = [_enrich_member_dict(m, fallback_color_index=idx % 5) for idx, m in enumerate(ordered)]

    # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 注入 pending_invitation 用于"邀请中"置灰
    from app.models.models import FamilyInvitation as _FamilyInvitation, FamilyManagement as _FamilyManagement
    from datetime import datetime as _dt2
    pending_res = await db.execute(
        select(_FamilyInvitation).where(
            _FamilyInvitation.inviter_user_id == current_user.id,
            _FamilyInvitation.status == "pending",
            _FamilyInvitation.expires_at > _dt2.utcnow(),
            _FamilyInvitation.member_id.is_not(None),
        ).order_by(_FamilyInvitation.created_at.desc())
    )
    pending_by_member: dict[int, dict] = {}
    now = _dt2.utcnow()
    for inv in pending_res.scalars().all():
        if inv.member_id in pending_by_member:
            continue  # 只保留最新（按 created_at desc 取首条）
        remaining_seconds = max(0, int((inv.expires_at - now).total_seconds()))
        remaining_hours = int(remaining_seconds // 3600)
        pending_by_member[inv.member_id] = {
            "invite_code": inv.invite_code,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "remaining_hours": remaining_hours,
        }
    for it in items:
        it["pending_invitation"] = pending_by_member.get(it.get("id"))

    # [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 为「对方已退出」加灰标，便于 AI 首页选择咨询人识别
    target_left_res = await db.execute(
        select(_FamilyManagement).where(
            _FamilyManagement.manager_user_id == current_user.id,
            _FamilyManagement.status == "cancelled_by_target",
        )
    )
    target_left_member_ids = set()
    for mgmt in target_left_res.scalars().all():
        if mgmt.managed_member_id:
            target_left_member_ids.add(int(mgmt.managed_member_id))
    for it in items:
        it["target_left"] = int(it.get("id", 0)) in target_left_member_ids

    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V2 2026-06-03]
    # v3_main_status / v3_sub_status 字段已下线（治本后 status / sub_status 即真值）。
    # 但 can_reinvite / can_edit / show_simplified_view 这三个视图开关仍由
    # derive_v3_state 计算后回填到 sub_status 同字段，便于前端复用。
    # 同时为兼容存量前端代码，临时把 status/sub_status 也通过 derive 函数走一遍
    # （治本后该函数对干净数据是恒等映射，对未迁移的脏数据仍能保底正确）。
    try:
        from app.services.family_member_status import derive_v3_state
        member_by_id = {m.id: m for m in ordered}
        for it in items:
            mb = member_by_id.get(it.get("id"))
            if mb is None:
                continue
            v3 = await derive_v3_state(db, member=mb)
            # 主+子状态：用 derive 结果覆盖（治本后等于库真值，对脏数据是兜底纠错）
            it["status"] = v3["main_status"]
            it["sub_status"] = v3["sub_status"]
            it["can_reinvite"] = v3["can_reinvite"]
            it["can_edit"] = v3["can_edit"]
            it["show_simplified_view"] = v3["show_simplified_view"]
    except Exception as _v3_err:
        # 视图开关字段是增强字段,推导失败不影响主流程
        logger.warning(f"family state derivation skipped: {_v3_err}")

    return {"items": items, "total": len(items)}


@router.post("/api/family/members", response_model=FamilyMemberResponse)
async def add_family_member(
    data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.relation_type_id and not data.relationship_type:
        raise HTTPException(status_code=400, detail="成员关系为必填项")

    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03] 防御性堵漏 #7：
    # 治本范围已明确——系统不支持"直接建档+绑定"路径（必须先建档再走邀请流）。
    # 旧代码在传入 member_user_id 时把 status 直接写成 'bound'，是脏数据的源头之一。
    # 现在硬性拒绝：新建家庭成员时 member_user_id 必须为空，否则 400。
    if data.member_user_id:
        raise HTTPException(
            status_code=400,
            detail="不允许直接绑定守护人，请通过邀请流程建立守护关系",
        )

    # [BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 姓名必填强校验：
    # 不允许 None / 空串 / 纯空格；统一返回 400 "姓名不能为空"。
    nickname = ((data.nickname or data.name) or "").strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="姓名不能为空")

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 新成员入档时分配 avatar_color_index：
    # 当前用户已入档成员数（含本人） % 5
    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03 兼容修复]
    # V3 状态机后新建成员 status 为 unbound（而非老的 bound），
    # 此处的颜色索引计数只应排除已软删除记录（deleted/removed），不限定 bound。
    count_res = await db.execute(
        select(func.count(FamilyMember.id)).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status.notin_(["deleted", "removed"]),
        )
    )
    existing_count = int(count_res.scalar() or 0)
    next_color_index = existing_count % 5

    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03]
    # 治本后，新建家庭成员一律为 unbound/not_applied —— 已通过上方硬校验
    # 拒绝了 member_user_id 非空的请求，这里不再有 "建档即 bound" 的分支。
    initial_status = "unbound"
    initial_sub_status = "not_applied"

    member = FamilyMember(
        user_id=current_user.id,
        member_user_id=data.member_user_id,
        relationship_type=data.relationship_type,
        nickname=nickname,
        relation_type_id=data.relation_type_id,
        birthday=data.birthday,
        gender=data.gender,
        height=data.height,
        weight=data.weight,
        medical_histories=data.medical_histories if data.medical_histories else None,
        allergies=data.allergies if data.allergies else None,
        is_self=False,
        avatar_color_index=next_color_index,
        status=initial_status,
        sub_status=initial_sub_status,
    )
    db.add(member)
    await db.flush()

    health_profile = HealthProfile(
        user_id=current_user.id,
        family_member_id=member.id,
        name=nickname,
        gender=data.gender,
        birthday=data.birthday,
        height=data.height,
        weight=data.weight,
        medical_histories=data.medical_histories if data.medical_histories else None,
        allergies=data.allergies if data.allergies else None,
    )
    db.add(health_profile)
    await db.flush()

    result2 = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member.id)
    )
    member = result2.scalar_one()

    return _enrich_member_dict(member, fallback_color_index=next_color_index)


@router.get("/api/family/members/{member_id}", response_model=FamilyMemberResponse)
async def get_family_member(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    return _enrich_member_dict(member)


@router.put("/api/family/members/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: int,
    data: FamilyMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    update_data = data.model_dump(exclude_unset=True)
    # [BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 编辑档案时若显式传入 nickname/name，
    # 必须 trim 校验，避免被改为空串；未传则不动原值。
    if "nickname" in update_data:
        nv = (update_data.get("nickname") or "").strip()
        if not nv:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        update_data["nickname"] = nv
    if "name" in update_data:
        nv = (update_data.get("name") or "").strip()
        if not nv:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        update_data["name"] = nv

    for key, value in update_data.items():
        setattr(member, key, value)

    await db.flush()

    result2 = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id)
    )
    member = result2.scalar_one()

    return _enrich_member_dict(member)


@router.delete("/api/family/members/{member_id}")
async def remove_family_member(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    if member.is_self:
        raise HTTPException(status_code=400, detail="本人成员不可删除")

    # [BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03] 防御性堵漏 #8：
    # 删除前必须确认成员未处于绑定态——若 status='bound'（或老枚举 'active'）
    # 直接拒绝，迫使调用方先走"解除守护关系"流程，避免删后留下游离 mgmt 记录。
    cur_status = (member.status or "").strip()
    if cur_status in ("bound", "active"):
        raise HTTPException(status_code=400, detail="请先解除绑定关系再删除档案")

    # 软删除该成员的健康档案
    hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == member_id,
        )
    )
    health_profile = hp_result.scalar_one_or_none()
    if health_profile:
        await db.delete(health_profile)

    member.status = "deleted"
    member.sub_status = "self_deleted"
    member.status_changed_at = datetime.utcnow()
    member.status_changed_by = current_user.id
    member.status_reason = "user_delete_family_member"
    await db.flush()
    return {"message": "已移除家庭成员"}


@router.get("/api/relation-types")
async def list_relation_types(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationType)
        .where(RelationType.is_active == True)  # noqa: E712
        .order_by(RelationType.sort_order)
    )
    items = [RelationTypeResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items}


@router.get("/api/disease-presets")
async def list_disease_presets(
    category: Optional[str] = Query(None, description="chronic 或 genetic"),
    db: AsyncSession = Depends(get_db),
):
    query = select(DiseasePreset).where(DiseasePreset.is_active == True)  # noqa: E712
    if category:
        query = query.where(DiseasePreset.category == category)
    query = query.order_by(DiseasePreset.sort_order)
    result = await db.execute(query)
    items = [DiseasePresetResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items}


@router.post("/api/family/sos")
async def send_sos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id, FamilyMember.status == "bound")
    )
    members = result.scalars().all()

    notified_count = 0
    for member in members:
        if member.member_user_id:
            notification = Notification(
                user_id=member.member_user_id,
                title="紧急求助",
                content=f"您的家人 {current_user.nickname or current_user.phone} 发来了紧急求助信号，请及时关注！",
                type=NotificationType.health,
                extra_data={"sos_user_id": current_user.id, "sos_type": "emergency"},
            )
            db.add(notification)
            notified_count += 1

    return {"message": "求助信号已发送", "notified_count": notified_count}
