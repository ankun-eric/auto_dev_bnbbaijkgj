from datetime import datetime
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_password_hash, require_role
from app.models.models import (
    AccountIdentity,
    IdentityType,
    MerchantCategory,
    MerchantMemberRole,
    MerchantProfile,
    MerchantRoleTemplate,
    MerchantStore,
    MerchantStoreMembership,
    MerchantStorePermission,
    User,
    UserRole,
)
from app.schemas.merchant import (
    MerchantAccountImportRequest,
    MerchantAccountSummaryResponse,
    MerchantAccountUpsert,
    MerchantRoleTemplateResponse,
    MerchantStoreCreate,
    MerchantStoreResponse,
    MerchantStoreUpdate,
)

router = APIRouter(prefix="/api/admin/merchant", tags=["商家管理"])

admin_dep = require_role("admin")

# [2026-04-24] 商家端模块权限扩充到 8 个
FULL_MODULE_CODES = [
    "dashboard", "verify", "records", "messages", "profile",
    "finance", "staff", "settings",
]

# [2026-04-24] 平台内置角色 → (member_role 映射, 默认模块)
# 角色模板 default_modules 以 DB 为准；此处仅作落库失败时兜底
ROLE_TO_MEMBER_ROLE: dict[str, MerchantMemberRole] = {
    "boss": MerchantMemberRole.owner,
    "manager": MerchantMemberRole.store_manager,
    "finance": MerchantMemberRole.finance,
    "clerk": MerchantMemberRole.verifier,
}
ROLE_NAME_MAP: dict[str, str] = {
    "boss": "老板",
    "manager": "店长",
    "finance": "财务",
    "clerk": "店员",
}
ROLE_DEFAULT_FALLBACK: dict[str, list[str]] = {
    "boss": FULL_MODULE_CODES,
    "manager": FULL_MODULE_CODES,
    "finance": ["dashboard", "records", "messages", "profile", "finance"],
    "clerk": ["dashboard", "verify", "records", "messages", "profile"],
}


async def _load_role_template(db: AsyncSession, code: str) -> tuple[str, list[str]]:
    """返回 (role_name, default_modules)，DB 无记录时用兜底。"""
    res = await db.execute(select(MerchantRoleTemplate).where(MerchantRoleTemplate.code == code))
    tpl = res.scalar_one_or_none()
    if tpl:
        raw = tpl.default_modules or []
        if isinstance(raw, str):
            try:
                import json as _json
                raw = _json.loads(raw)
            except Exception:
                raw = []
        mods = [m for m in (raw or []) if m in FULL_MODULE_CODES]
        if not mods:
            mods = list(ROLE_DEFAULT_FALLBACK.get(code, []))
        return tpl.name, mods
    return ROLE_NAME_MAP.get(code, code), list(ROLE_DEFAULT_FALLBACK.get(code, []))


async def _ensure_identity(db: AsyncSession, user_id: int, identity_type: IdentityType) -> None:
    result = await db.execute(
        select(AccountIdentity).where(
            AccountIdentity.user_id == user_id,
            AccountIdentity.identity_type == identity_type,
        )
    )
    identity = result.scalar_one_or_none()
    if identity:
        identity.status = "active"
        identity.updated_at = datetime.utcnow()
        return
    db.add(AccountIdentity(user_id=user_id, identity_type=identity_type))


async def _remove_identity(db: AsyncSession, user_id: int, identity_type: IdentityType) -> None:
    result = await db.execute(
        select(AccountIdentity).where(
            AccountIdentity.user_id == user_id,
            AccountIdentity.identity_type == identity_type,
        )
    )
    identity = result.scalar_one_or_none()
    if identity:
        await db.delete(identity)


async def _sync_memberships(
    db: AsyncSession,
    user_id: int,
    merchant_identity_type: str,
    store_ids: Iterable[int],
    store_permissions: dict[int, list[str]],
    role_code: Optional[str] = None,
) -> None:
    existing_result = await db.execute(
        select(MerchantStoreMembership).where(MerchantStoreMembership.user_id == user_id)
    )
    existing_memberships = existing_result.scalars().all()
    membership_map = {membership.store_id: membership for membership in existing_memberships}

    target_store_ids = set(store_ids)
    for membership in existing_memberships:
        if membership.store_id not in target_store_ids:
            perm_result = await db.execute(
                select(MerchantStorePermission).where(
                    MerchantStorePermission.membership_id == membership.id
                )
            )
            for permission in perm_result.scalars().all():
                await db.delete(permission)
            await db.delete(membership)

    # 推导 member_role：优先用 role_code 映射，否则退回 owner/staff
    if role_code and role_code in ROLE_TO_MEMBER_ROLE:
        member_role = ROLE_TO_MEMBER_ROLE[role_code]
    else:
        member_role = (
            MerchantMemberRole.owner
            if merchant_identity_type == "owner"
            else MerchantMemberRole.staff
        )

    for store_id in target_store_ids:
        membership = membership_map.get(store_id)
        if not membership:
            membership = MerchantStoreMembership(
                user_id=user_id,
                store_id=store_id,
                member_role=member_role,
                role_code=role_code,
                status="active",
            )
            db.add(membership)
            await db.flush()
        else:
            membership.member_role = member_role
            membership.role_code = role_code or membership.role_code
            membership.status = "active"
            membership.updated_at = datetime.utcnow()

        perm_result = await db.execute(
            select(MerchantStorePermission).where(
                MerchantStorePermission.membership_id == membership.id
            )
        )
        existing_permissions = perm_result.scalars().all()
        existing_modules = {permission.module_code for permission in existing_permissions}
        target_modules = sorted(set(store_permissions.get(store_id, [])))
        # owner/boss 默认全模块
        if not target_modules and merchant_identity_type == "owner":
            target_modules = FULL_MODULE_CODES
        for permission in existing_permissions:
            if permission.module_code not in target_modules:
                await db.delete(permission)
        for module_code in target_modules:
            if module_code not in existing_modules:
                db.add(
                    MerchantStorePermission(
                        membership_id=membership.id,
                        module_code=module_code,
                    )
                )


async def _build_store_response(
    db: AsyncSession,
    membership: MerchantStoreMembership,
) -> MerchantStoreResponse | None:
    store_result = await db.execute(select(MerchantStore).where(MerchantStore.id == membership.store_id))
    store = store_result.scalar_one_or_none()
    if not store:
        return None
    if membership.member_role == MerchantMemberRole.owner:
        module_codes = FULL_MODULE_CODES
    else:
        perm_result = await db.execute(
            select(MerchantStorePermission.module_code).where(
                MerchantStorePermission.membership_id == membership.id
            )
        )
        module_codes = sorted(set(perm_result.scalars().all()))
    category_code = None
    category_name = None
    if getattr(store, "category_id", None):
        cat_res = await db.execute(select(MerchantCategory).where(MerchantCategory.id == store.category_id))
        cat = cat_res.scalar_one_or_none()
        if cat:
            category_code = cat.code
            category_name = cat.name
    return MerchantStoreResponse(
        id=store.id,
        store_name=store.store_name,
        store_code=store.store_code,
        contact_name=store.contact_name,
        contact_phone=store.contact_phone,
        address=store.address,
        status=store.status,
        member_role=membership.member_role.value,
        module_codes=module_codes,
        category_id=getattr(store, "category_id", None),
        category_code=category_code,
        category_name=category_name,
    )


async def _build_account_summary(
    db: AsyncSession,
    user: User,
) -> MerchantAccountSummaryResponse:
    profile_result = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    identity_result = await db.execute(
        select(AccountIdentity.identity_type).where(
            AccountIdentity.user_id == user.id,
            AccountIdentity.status == "active",
        )
    )
    identity_codes = sorted(
        identity.value if hasattr(identity, "value") else str(identity)
        for identity in identity_result.scalars().all()
    )
    memberships_result = await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == user.id,
            MerchantStoreMembership.status == "active",
        )
    )
    stores = []
    merchant_identity_type = None
    role_code: Optional[str] = None
    for membership in memberships_result.scalars().all():
        if membership.member_role == MerchantMemberRole.owner:
            merchant_identity_type = "owner"
        elif merchant_identity_type is None:
            merchant_identity_type = "staff"
        if role_code is None and getattr(membership, "role_code", None):
            role_code = membership.role_code
        store_item = await _build_store_response(db, membership)
        if store_item:
            stores.append(store_item)
    # 兜底推断 role_code：历史数据未写入时根据 member_role 推导
    if role_code is None:
        if merchant_identity_type == "owner":
            role_code = "boss"
        elif merchant_identity_type == "staff":
            role_code = "clerk"
    role_name = ROLE_NAME_MAP.get(role_code) if role_code else None
    return MerchantAccountSummaryResponse(
        id=user.id,
        phone=user.phone or "",
        status=user.status,
        user_nickname=user.nickname,
        merchant_nickname=profile.nickname if profile else None,
        identity_codes=identity_codes,
        merchant_identity_type=merchant_identity_type,
        role_code=role_code,
        role_name=role_name,
        stores=stores,
        created_at=user.created_at,
    )


async def _upsert_merchant_account(
    db: AsyncSession,
    data: MerchantAccountUpsert,
    existing_user: User | None = None,
) -> MerchantAccountSummaryResponse:
    if data.merchant_identity_type not in {"owner", "staff"}:
        raise HTTPException(status_code=400, detail="商家身份类型无效")

    # [2026-04-24] role_code 校验
    role_code = (data.role_code or "").strip() or None
    if role_code is not None and role_code not in ROLE_TO_MEMBER_ROLE:
        raise HTTPException(status_code=400, detail=f"无效的角色 code: {role_code}")

    # owner 身份必须落到 boss 角色；staff 身份禁止使用 boss
    if data.merchant_identity_type == "owner":
        if role_code is None:
            role_code = "boss"
        elif role_code != "boss":
            raise HTTPException(status_code=400, detail="主账号角色必须为老板 (boss)")
    else:  # staff
        if role_code == "boss":
            raise HTTPException(status_code=400, detail="员工账号不能使用老板角色")
        if role_code is None:
            role_code = "clerk"  # 缺省为店员

    user = existing_user
    if not user:
        result = await db.execute(select(User).where(User.phone == data.phone))
        user = result.scalar_one_or_none()
    if not user:
        user = User(
            phone=data.phone,
            nickname=data.user_nickname or (data.merchant_nickname or f"账号{data.phone[-4:]}"),
            status=data.status,
            role=UserRole.user if data.enable_user_identity else UserRole.merchant,
        )
        if data.password:
            user.password_hash = get_password_hash(data.password)
        db.add(user)
        await db.flush()
    else:
        if user.role == UserRole.admin:
            raise HTTPException(status_code=400, detail="管理员账号不能配置为商家账号")
        user.phone = data.phone
        if data.user_nickname is not None:
            user.nickname = data.user_nickname
        if data.user_avatar is not None:
            user.avatar = data.user_avatar
        if data.password:
            user.password_hash = get_password_hash(data.password)
        user.status = data.status
        user.role = UserRole.user if data.enable_user_identity else UserRole.merchant
        user.updated_at = datetime.utcnow()

    if data.enable_user_identity:
        await _ensure_identity(db, user.id, IdentityType.user)
    else:
        await _remove_identity(db, user.id, IdentityType.user)

    if data.merchant_identity_type == "owner":
        await _ensure_identity(db, user.id, IdentityType.merchant_owner)
        await _remove_identity(db, user.id, IdentityType.merchant_staff)
        target_store_ids = data.store_ids
        store_permissions = {store_id: FULL_MODULE_CODES for store_id in data.store_ids}
    else:
        await _ensure_identity(db, user.id, IdentityType.merchant_staff)
        await _remove_identity(db, user.id, IdentityType.merchant_owner)
        target_store_ids = [item.store_id for item in data.store_permissions]
        # [2026-04-24] 若前端未传 module_codes（空列表），按角色默认模板自动填充
        _, role_default_modules = await _load_role_template(db, role_code)
        store_permissions = {}
        for item in data.store_permissions:
            mods = list(item.module_codes) if item.module_codes else []
            if not mods:
                mods = list(role_default_modules)
            # 过滤非法 module（只保留 8 个合法 code）
            mods = [m for m in mods if m in FULL_MODULE_CODES]
            store_permissions[item.store_id] = mods

    if not target_store_ids:
        raise HTTPException(status_code=400, detail="至少需要配置一个门店")

    stores_result = await db.execute(
        select(func.count(MerchantStore.id)).where(MerchantStore.id.in_(target_store_ids))
    )
    if (stores_result.scalar() or 0) != len(set(target_store_ids)):
        raise HTTPException(status_code=400, detail="存在无效门店")

    profile_result = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        profile = MerchantProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
    profile.nickname = data.merchant_nickname or user.nickname
    profile.avatar = data.merchant_avatar
    profile.updated_at = datetime.utcnow()

    await _sync_memberships(
        db,
        user.id,
        data.merchant_identity_type,
        target_store_ids,
        store_permissions,
        role_code=role_code,
    )
    await db.flush()
    await db.refresh(user)
    return await _build_account_summary(db, user)


async def _validate_category_id(db: AsyncSession, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    res = await db.execute(select(MerchantCategory).where(MerchantCategory.id == category_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="无效的门店类别 category_id")


@router.get("/stores")
async def list_stores(
    keyword: str | None = None,
    category_code: str | None = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 加载全部类别（便于按 code 过滤 + 注入响应）
    cat_res = await db.execute(select(MerchantCategory))
    category_by_id = {c.id: c for c in cat_res.scalars().all()}
    category_by_code = {c.code: c for c in category_by_id.values()}

    query = select(MerchantStore).order_by(MerchantStore.created_at.desc())
    if keyword:
        query = query.where(
            MerchantStore.store_name.contains(keyword)
            | MerchantStore.store_code.contains(keyword)
        )
    if category_code:
        cat = category_by_code.get(category_code)
        if not cat:
            return {"items": []}
        query = query.where(MerchantStore.category_id == cat.id)
    result = await db.execute(query)
    items = []
    for store in result.scalars().all():
        cat = category_by_id.get(getattr(store, "category_id", None)) if getattr(store, "category_id", None) else None
        items.append({
            "id": store.id,
            "store_name": store.store_name,
            "store_code": store.store_code,
            "category_id": getattr(store, "category_id", None),
            "category_code": cat.code if cat else None,
            "category_name": cat.name if cat else None,
            "contact_name": store.contact_name,
            "contact_phone": store.contact_phone,
            "address": store.address,
            "status": store.status,
            "created_at": store.created_at.isoformat() if store.created_at else None,
        })
    return {"items": items}


@router.post("/stores")
async def create_store(
    data: MerchantStoreCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(MerchantStore).where(MerchantStore.store_code == data.store_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="门店编码已存在")
    # [2026-04-24] 新建门店必选类别
    if data.category_id is None:
        raise HTTPException(status_code=400, detail="请选择门店所属类别")
    await _validate_category_id(db, data.category_id)
    store = MerchantStore(**data.model_dump())
    db.add(store)
    await db.flush()
    return {"id": store.id, "message": "门店创建成功"}


@router.get("/stores/{store_id}")
async def get_store(
    store_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    category = None
    if getattr(store, "category_id", None):
        cat_res = await db.execute(select(MerchantCategory).where(MerchantCategory.id == store.category_id))
        cat = cat_res.scalar_one_or_none()
        if cat:
            category = {"id": cat.id, "code": cat.code, "name": cat.name}
    return {
        "id": store.id,
        "store_name": store.store_name,
        "store_code": store.store_code,
        "category_id": getattr(store, "category_id", None),
        "category": category,
        "contact_name": store.contact_name,
        "contact_phone": store.contact_phone,
        "address": store.address,
        "status": store.status,
    }


@router.put("/stores/{store_id}")
async def update_store(
    store_id: int,
    data: MerchantStoreUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload:
        await _validate_category_id(db, payload["category_id"])
    for key, value in payload.items():
        setattr(store, key, value)
    store.updated_at = datetime.utcnow()
    return {"message": "门店更新成功"}


@router.get("/accounts")
async def list_accounts(
    keyword: str | None = None,
    role_code: str | None = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    identity_result = await db.execute(
        select(AccountIdentity.user_id).where(
            AccountIdentity.identity_type.in_([IdentityType.merchant_owner, IdentityType.merchant_staff]),
            AccountIdentity.status == "active",
        )
    )
    user_ids = sorted(set(identity_result.scalars().all()))
    if not user_ids:
        return {"items": []}

    query = select(User).where(User.id.in_(user_ids)).order_by(User.created_at.desc())
    if keyword:
        query = query.where(
            User.phone.contains(keyword) | User.nickname.contains(keyword)
        )
    result = await db.execute(query)
    items = [await _build_account_summary(db, user) for user in result.scalars().all()]
    # [2026-04-24] 支持按角色过滤（基于 _build_account_summary 兜底推断后的 role_code）
    if role_code:
        rc = role_code.strip()
        if rc:
            items = [it for it in items if (it.role_code or "") == rc]
    return {"items": items}


@router.post("/accounts")
async def upsert_account(
    data: MerchantAccountUpsert,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    account = await _upsert_merchant_account(db, data)
    return {"message": "商家账号保存成功", "item": account}


@router.put("/accounts/{user_id}")
async def update_account(
    user_id: int,
    data: MerchantAccountUpsert,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.id == user_id))
    user = existing.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    if user.phone != data.phone:
        phone_result = await db.execute(select(User).where(User.phone == data.phone, User.id != user_id))
        if phone_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="手机号已存在")
    account = await _upsert_merchant_account(db, data, existing_user=user)
    return {"message": "商家账号更新成功", "item": account}


@router.post("/accounts/import")
async def import_accounts(
    data: MerchantAccountImportRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    items = []
    for item in data.items:
        account = await _upsert_merchant_account(
            db,
            MerchantAccountUpsert(
                phone=item.phone,
                password=item.password,
                user_nickname=item.user_nickname,
                enable_user_identity=item.enable_user_identity,
                merchant_nickname=item.merchant_nickname,
                merchant_identity_type=item.merchant_identity_type,
                role_code=getattr(item, "role_code", None),
                status=item.status,
                store_permissions=item.store_permissions,
            ),
        )
        items.append(account)
    return {"message": "导入完成", "items": items}
