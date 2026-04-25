"""账号安全相关 API（PRD V1.0 / 2026-04-25）

涵盖：
- M7：图形验证码生成
- M1 / M3：admin / 商家个人信息
- M1 / M3 / M4：admin / 商家修改密码（含强制重登）
- M5：商家端老板创建员工 / 修复回显 Bug
- M6：老板重置员工密码（含全端踢出）
- 首次登录强制改密接口

PRD §10 接口约定（落地）：
- GET  /api/captcha/image          → 图形验证码（PNG）
- GET  /api/admin/profile          → admin 个人信息
- PUT  /api/admin/password         → admin 修改密码
- GET  /api/merchant/profile       → 商家端个人信息（PC + H5 共用）
- PUT  /api/merchant/password      → 商家端修改密码
- POST /api/merchant/staff/reset-password   → 老板重置员工密码
- POST /api/merchant/staff/create           → 老板创建员工
- POST /api/merchant/staff/toggle-status    → 启停员工（修复 Bug）
- POST /api/auth/force-change-password      → 首次登录强制改密
- POST /api/admin/merchant/accounts/{id}/reset-password → admin 重置老板密码
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.password_policy import (
    PasswordValidationError,
    clear_must_change_password,
    is_must_change_password,
    mark_must_change_password,
    revoke_all_tokens_for_user,
    revoke_token,
    validate_password_strength,
)
from app.core.security import (
    get_current_user,
    get_identity_codes_for_user,
    get_password_hash,
    require_role,
    verify_password,
)
from app.models.models import (
    AccountIdentity,
    IdentityType,
    MerchantMemberRole,
    MerchantProfile,
    MerchantRoleTemplate,
    MerchantStore,
    MerchantStoreMembership,
    MerchantStorePermission,
    User,
    UserRole,
)
from app.services.captcha_service import (
    CAPTCHA_TTL_SECONDS,
    acquire_issue_rate,
    issue_captcha,
    verify_captcha,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["账号安全"])

# 商家端 8 个模块（与 admin_merchant.FULL_MODULE_CODES 同步）
_MERCHANT_MODULE_CODES = [
    "dashboard", "verify", "records", "messages", "profile",
    "finance", "staff", "settings",
]
_MERCHANT_ROLE_DEFAULT_MODULES: dict[str, list[str]] = {
    "boss": _MERCHANT_MODULE_CODES,
    "manager": _MERCHANT_MODULE_CODES,
    "finance": ["dashboard", "records", "messages", "profile", "finance"],
    "clerk": ["dashboard", "verify", "records", "messages", "profile"],
}
_MERCHANT_ROLE_NAMES = {"boss": "老板", "manager": "店长", "finance": "财务", "clerk": "店员"}
_MERCHANT_ROLE_TO_MEMBER = {
    "boss": MerchantMemberRole.owner,
    "manager": MerchantMemberRole.store_manager,
    "finance": MerchantMemberRole.finance,
    "clerk": MerchantMemberRole.verifier,
}


# ════════════════ Schemas ════════════════

class CaptchaImageResponse(BaseModel):
    captcha_id: str
    image_base64: str  # data:image/png;base64,...
    expire_seconds: int = CAPTCHA_TTL_SECONDS


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class ForceChangePasswordRequest(BaseModel):
    """首次登录或被重置后强制改密；无需 old_password"""
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class AdminProfileResponse(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "admin"
    role_name: str = "管理员"
    merchant_name: str = "平台"
    is_superuser: bool = False
    must_change_password: bool = False


class MerchantProfileFullResponse(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    role_code: str
    role_name: str
    merchant_name: Optional[str] = None
    store_names: List[str] = Field(default_factory=list)
    store_ids: List[int] = Field(default_factory=list)
    must_change_password: bool = False


class StaffCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=11, max_length=20)
    role_code: str = Field(..., description="manager / finance / clerk")
    store_ids: List[int] = Field(..., min_length=1)
    avatar: Optional[str] = None
    hire_date: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=200)


class StaffResetPasswordRequest(BaseModel):
    target_user_id: int
    reset_type: str = Field(..., description="default | custom")
    new_password: Optional[str] = None


class StaffToggleStatusRequest(BaseModel):
    target_user_id: int
    status: str = Field(..., description="active / disabled")


class AdminResetMerchantPasswordRequest(BaseModel):
    reset_type: str = Field(..., description="default | custom")
    new_password: Optional[str] = None


# ════════════════ §M7.2 图形验证码 ════════════════

@router.get("/api/captcha/image", response_model=CaptchaImageResponse)
async def get_captcha_image(request: Request, response: Response) -> CaptchaImageResponse:
    """生成 4 位图形验证码（PNG / Base64）。

    PRD 规格：
    - 4 位字符（数字 2-9 + 大写字母去 OIL，共 31 字符）
    - 图片 160 × 60，字号 38px，干扰线 2~3 条 + 少量噪点
    - 5 分钟过期，一次性使用
    - IP 级限流：1 秒最多 5 次（防刷）
    - 不缓存
    """
    import base64

    client_ip = (
        (request.client.host if request.client else None)
        or request.headers.get("x-forwarded-for")
        or "unknown"
    )
    if not acquire_issue_rate(client_ip):
        raise HTTPException(status_code=429, detail="验证码请求过于频繁，请稍后再试")

    captcha_id, png_bytes = issue_captcha()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return CaptchaImageResponse(
        captcha_id=captcha_id,
        image_base64=f"data:image/png;base64,{b64}",
        expire_seconds=CAPTCHA_TTL_SECONDS,
    )


# ════════════════ §M1 admin 个人信息 / 改密 ════════════════

@router.get("/api/admin/profile", response_model=AdminProfileResponse)
async def admin_get_profile(
    current_user: User = Depends(require_role("admin")),
):
    return AdminProfileResponse(
        id=current_user.id,
        name=current_user.nickname or "管理员",
        phone=current_user.phone,
        role="admin",
        role_name="管理员",
        merchant_name="平台",
        is_superuser=bool(current_user.is_superuser),
        must_change_password=is_must_change_password(current_user.id),
    )


@router.put("/api/admin/password")
async def admin_change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await _change_password_common(data, request, current_user, db)


# ════════════════ §M3 / M4 商家个人信息 / 改密 ════════════════

async def _require_merchant(current_user: User, db: AsyncSession) -> User:
    codes = await get_identity_codes_for_user(db, current_user.id)
    if not ({"merchant_owner", "merchant_staff"} & codes):
        raise HTTPException(status_code=403, detail="非商家账号")
    return current_user


@router.get("/api/merchant/profile", response_model=MerchantProfileFullResponse)
async def merchant_get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_merchant(current_user, db)
    rows = (await db.execute(
        select(MerchantStoreMembership, MerchantStore)
        .join(MerchantStore, MerchantStore.id == MerchantStoreMembership.store_id)
        .where(
            MerchantStoreMembership.user_id == current_user.id,
            MerchantStoreMembership.status == "active",
        )
    )).all()
    role_code = None
    store_names: list[str] = []
    store_ids: list[int] = []
    seen_store_ids: set[int] = set()
    for m, s in rows:
        if m.store_id not in seen_store_ids:
            store_names.append(s.store_name)
            store_ids.append(m.store_id)
            seen_store_ids.add(m.store_id)
        rc = getattr(m, "role_code", None)
        if rc:
            # 优先取 boss > manager > finance > clerk
            order = {"boss": 4, "manager": 3, "finance": 2, "clerk": 1}
            if role_code is None or order.get(rc, 0) > order.get(role_code, 0):
                role_code = rc
        elif role_code is None and m.member_role == MerchantMemberRole.owner:
            role_code = "boss"
    if role_code is None:
        role_code = "clerk"

    profile = (await db.execute(
        select(MerchantProfile).where(MerchantProfile.user_id == current_user.id)
    )).scalar_one_or_none()
    merchant_name = profile.nickname if profile and profile.nickname else (
        store_names[0] if store_names else None
    )
    return MerchantProfileFullResponse(
        id=current_user.id,
        name=current_user.nickname,
        phone=current_user.phone,
        role_code=role_code,
        role_name=_MERCHANT_ROLE_NAMES.get(role_code, role_code),
        merchant_name=merchant_name,
        store_names=store_names,
        store_ids=store_ids,
        must_change_password=is_must_change_password(current_user.id),
    )


@router.put("/api/merchant/password")
async def merchant_change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_merchant(current_user, db)
    return await _change_password_common(data, request, current_user, db)


@router.post("/api/auth/force-change-password")
async def force_change_password(
    data: ForceChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首次登录或被老板/平台重置密码后强制修改密码（无需输入原密码）"""
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")
    try:
        validate_password_strength(data.new_password)
    except PasswordValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current_user.password_hash = get_password_hash(data.new_password)
    current_user.updated_at = datetime.utcnow()
    await db.commit()

    clear_must_change_password(current_user.id)
    # 当前 token 也失效，要求用户用新密码重新登录
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        revoke_token(auth[7:].strip())
    revoke_all_tokens_for_user(current_user.id)
    return {"message": "密码修改成功，请使用新密码重新登录"}


async def _change_password_common(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User,
    db: AsyncSession,
):
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")
    if not current_user.password_hash or not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误，请重新输入")
    try:
        validate_password_strength(data.new_password)
    except PasswordValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    current_user.password_hash = get_password_hash(data.new_password)
    current_user.updated_at = datetime.utcnow()
    await db.commit()

    clear_must_change_password(current_user.id)
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        revoke_token(auth[7:].strip())
    revoke_all_tokens_for_user(current_user.id)
    return {"message": "密码修改成功，请重新登录"}


# ════════════════ §M5 商家端老板创建员工 ════════════════

async def _user_is_boss_in_any_store(db: AsyncSession, user_id: int) -> tuple[bool, list[int]]:
    """返回 (是否是老板, 该用户作为老板覆盖的门店 ids)"""
    rows = (await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == user_id,
            MerchantStoreMembership.status == "active",
            MerchantStoreMembership.member_role == MerchantMemberRole.owner,
        )
    )).scalars().all()
    return (len(rows) > 0, [m.store_id for m in rows])


def _phone_last6(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) < 6:
        return p.rjust(6, "0")
    return p[-6:]


@router.post("/api/merchant/staff/create")
async def merchant_staff_create(
    data: StaffCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """老板创建员工（PRD §M5.3 / §M5.6 / §M5.8）"""
    is_boss, owner_store_ids = await _user_is_boss_in_any_store(db, current_user.id)
    if not is_boss:
        raise HTTPException(status_code=403, detail="仅老板可创建员工")

    role_code = (data.role_code or "").strip().lower()
    if role_code not in ("manager", "finance", "clerk"):
        raise HTTPException(status_code=400, detail="角色必须是店长 / 财务 / 店员")

    requested = set(data.store_ids)
    if not requested.issubset(set(owner_store_ids)):
        raise HTTPException(status_code=403, detail="所属门店超出您的管辖范围")

    phone = data.phone.strip()
    if len(phone) < 11:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    target = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
    initial_password = _phone_last6(phone)
    if target is None:
        target = User(
            phone=phone,
            nickname=data.name,
            password_hash=get_password_hash(initial_password),
            role=UserRole.merchant,
            status="active",
            avatar=data.avatar,
        )
        db.add(target)
        await db.flush()
    else:
        if target.role == UserRole.admin:
            raise HTTPException(status_code=400, detail="该手机号是管理员账号，不能作为员工")
        # 同商家内不允许重复绑定
        existing_membership_in_my_stores = (await db.execute(
            select(MerchantStoreMembership).where(
                MerchantStoreMembership.user_id == target.id,
                MerchantStoreMembership.store_id.in_(owner_store_ids),
            )
        )).scalars().all()
        if existing_membership_in_my_stores:
            raise HTTPException(status_code=400, detail="该手机号已是您商家下的员工")
        target.nickname = data.name or target.nickname
        if data.avatar:
            target.avatar = data.avatar
        target.password_hash = get_password_hash(initial_password)
        target.updated_at = datetime.utcnow()

    # 落 identity_type
    has_identity = (await db.execute(
        select(AccountIdentity).where(
            AccountIdentity.user_id == target.id,
            AccountIdentity.identity_type == IdentityType.merchant_staff,
        )
    )).scalar_one_or_none()
    if not has_identity:
        db.add(AccountIdentity(user_id=target.id, identity_type=IdentityType.merchant_staff))

    member_role = _MERCHANT_ROLE_TO_MEMBER[role_code]
    default_modules = _MERCHANT_ROLE_DEFAULT_MODULES[role_code]
    for sid in requested:
        membership = MerchantStoreMembership(
            user_id=target.id,
            store_id=sid,
            member_role=member_role,
            role_code=role_code,
            status="active",
        )
        db.add(membership)
        await db.flush()
        for mc in default_modules:
            db.add(MerchantStorePermission(membership_id=membership.id, module_code=mc))

    # 标记首次登录强制改密
    mark_must_change_password(target.id)
    await db.commit()
    return {
        "message": f"员工创建成功，初始密码为手机号后 6 位（{initial_password}），请告知员工首次登录修改密码",
        "user_id": target.id,
        "initial_password": initial_password,
    }


# ════════════════ §M6 老板重置员工密码 ════════════════

@router.post("/api/merchant/staff/reset-password")
async def merchant_staff_reset_password(
    data: StaffResetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_boss, owner_store_ids = await _user_is_boss_in_any_store(db, current_user.id)
    if not is_boss:
        raise HTTPException(status_code=403, detail="仅老板可重置员工密码")
    target = (await db.execute(select(User).where(User.id == data.target_user_id))).scalar_one_or_none()
    if not target or not target.phone:
        raise HTTPException(status_code=404, detail="员工不存在")

    target_memberships = (await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == target.id,
            MerchantStoreMembership.store_id.in_(owner_store_ids),
        )
    )).scalars().all()
    if not target_memberships:
        raise HTTPException(status_code=403, detail="该员工不在您管辖范围内")
    # 不能重置另一个老板
    for m in target_memberships:
        rc = getattr(m, "role_code", None) or ("boss" if m.member_role == MerchantMemberRole.owner else None)
        if rc == "boss":
            raise HTTPException(status_code=403, detail="不能重置其他老板的密码")

    if data.reset_type == "default":
        new_password = _phone_last6(target.phone)
    elif data.reset_type == "custom":
        if not data.new_password:
            raise HTTPException(status_code=400, detail="请输入自定义密码")
        try:
            validate_password_strength(data.new_password)
        except PasswordValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        new_password = data.new_password
    else:
        raise HTTPException(status_code=400, detail="reset_type 必须是 default 或 custom")

    target.password_hash = get_password_hash(new_password)
    target.updated_at = datetime.utcnow()
    mark_must_change_password(target.id)
    revoke_all_tokens_for_user(target.id)

    # 操作日志（PRD §M6.4）：本期落控制台 + 标记字段，无独立日志表的情况下使用 logger
    logger.info(
        "[STAFF_PASSWORD_RESET] reset_by=%s target=%s reset_type=%s ts=%s",
        current_user.id, target.id, data.reset_type, datetime.utcnow().isoformat(),
    )
    await db.commit()

    return {
        "message": "密码已重置，请告知员工新密码",
        "reset_type": data.reset_type,
        "new_password_hint": "手机号后 6 位" if data.reset_type == "default" else "已自定义",
    }


# ════════════════ §M5.10 启停员工（修复 H5 弹回 Bug） ════════════════

@router.post("/api/merchant/staff/toggle-status")
async def merchant_staff_toggle_status(
    data: StaffToggleStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一封装的"启停"接口，避免不同请求体导致 H5 端 422 回滚。

    Bug 根因：H5 端调用旧 PUT /staff/{id}/status 时，部分网络代理对带 body 的 PUT 请求处理异常，
    或前后端字段名不一致导致 422 错误，开关被前端"成功后才本地置位"的乐观更新逻辑回滚。
    本接口接受 POST + JSON 简体字段，且业务校验放宽（老板可以管全部，店长管自己门店的非老板/非店长），
    成功返回明确的 status，前端据此渲染。
    """
    target_user_id = data.target_user_id
    new_status = data.status
    if new_status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 必须是 active 或 disabled")

    is_boss, owner_store_ids = await _user_is_boss_in_any_store(db, current_user.id)
    my_active_store_ids = [m.store_id for m in (await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == current_user.id,
            MerchantStoreMembership.status == "active",
        )
    )).scalars().all()]

    # 是否店长
    is_manager_rows = (await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == current_user.id,
            MerchantStoreMembership.status == "active",
            MerchantStoreMembership.member_role == MerchantMemberRole.store_manager,
        )
    )).scalars().all()
    is_manager = len(is_manager_rows) > 0
    if not (is_boss or is_manager):
        raise HTTPException(status_code=403, detail="无权限操作员工")

    # 取目标在"当前操作者管辖范围"内的所有 membership
    scope_store_ids = owner_store_ids if is_boss else [m.store_id for m in is_manager_rows]
    target_memberships = (await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == target_user_id,
            MerchantStoreMembership.store_id.in_(scope_store_ids),
        )
    )).scalars().all()
    if not target_memberships:
        raise HTTPException(status_code=404, detail="员工不在您的管辖范围内")

    # 角色校验：老板可启停 manager/finance/clerk；店长仅可启停 finance/clerk
    for m in target_memberships:
        rc = getattr(m, "role_code", None) or (
            "boss" if m.member_role == MerchantMemberRole.owner else None
        )
        if rc == "boss":
            raise HTTPException(status_code=403, detail="不能启停老板账号")
        if (not is_boss) and rc == "manager":
            raise HTTPException(status_code=403, detail="店长不能启停其他店长")

    for m in target_memberships:
        m.status = new_status
        m.updated_at = datetime.utcnow()

    # 同步 user.status：若所有 membership 都被禁用则 user.status=disabled，否则 active
    target_user = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if target_user:
        all_mems = (await db.execute(
            select(MerchantStoreMembership).where(MerchantStoreMembership.user_id == target_user_id)
        )).scalars().all()
        if all_mems and all(mm.status == "disabled" for mm in all_mems):
            target_user.status = "disabled"
        else:
            target_user.status = "active"
        target_user.updated_at = datetime.utcnow()
        if new_status == "disabled":
            revoke_all_tokens_for_user(target_user_id)

    await db.commit()
    return {"message": "状态已更新", "status": new_status, "target_user_id": target_user_id}


# ════════════════ §M2 / §M7.5 admin 重置老板密码 ════════════════

@router.post("/api/admin/merchant/accounts/{user_id}/reset-password")
async def admin_reset_merchant_password(
    user_id: int,
    data: AdminResetMerchantPasswordRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target or not target.phone:
        raise HTTPException(status_code=404, detail="账号不存在")

    if data.reset_type == "default":
        new_password = _phone_last6(target.phone)
    elif data.reset_type == "custom":
        if not data.new_password:
            raise HTTPException(status_code=400, detail="请输入自定义密码")
        try:
            validate_password_strength(data.new_password)
        except PasswordValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        new_password = data.new_password
    else:
        raise HTTPException(status_code=400, detail="reset_type 必须是 default 或 custom")

    target.password_hash = get_password_hash(new_password)
    target.updated_at = datetime.utcnow()
    mark_must_change_password(target.id)
    revoke_all_tokens_for_user(target.id)
    logger.info(
        "[ADMIN_RESET_MERCHANT_PASSWORD] admin=%s target=%s reset_type=%s",
        current_user.id, target.id, data.reset_type,
    )
    await db.commit()
    return {
        "message": "密码已重置",
        "reset_type": data.reset_type,
        "new_password_hint": "手机号后 6 位" if data.reset_type == "default" else "已自定义",
    }
