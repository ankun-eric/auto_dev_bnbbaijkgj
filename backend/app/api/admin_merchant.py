from datetime import datetime
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
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
    MerchantStaffItemResponse,
    MerchantStaffListResponse,
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

# [2026-04-26 PRD v1.0] 商家角色统一治理 — 全平台仅保留 4 个 role_code：
#   boss / store_manager / finance / clerk
# 废除（仅做兼容映射，下个版本删除）：
#   - verifier 核销员 → 合并入 clerk（核销职责由店员承担）
#   - staff（与 clerk 重复）→ clerk
#   - owner（历史别名）→ boss
#   - manager（历史别名）→ store_manager
# DB 物理 Enum (MerchantMemberRole) 暂保留 5 值（owner/store_manager/finance/verifier/staff）以避免破坏存量数据，
# 但业务读写**一律以 role_code 为权威**，display 名称统一从 ROLE_NAME_MAP 取值。
ROLE_TO_MEMBER_ROLE: dict[str, MerchantMemberRole] = {
    "boss": MerchantMemberRole.owner,
    "store_manager": MerchantMemberRole.store_manager,
    "finance": MerchantMemberRole.finance,
    "clerk": MerchantMemberRole.verifier,  # clerk 在 DB 物理上落到 verifier 枚举
}
ROLE_NAME_MAP: dict[str, str] = {
    "boss": "老板",
    "store_manager": "店长",
    "finance": "财务",
    "clerk": "店员",
}
ROLE_DEFAULT_FALLBACK: dict[str, list[str]] = {
    "boss": FULL_MODULE_CODES,
    "store_manager": FULL_MODULE_CODES,
    "finance": ["dashboard", "records", "messages", "profile", "finance"],
    "clerk": ["dashboard", "verify", "records", "messages", "profile"],
}

# [2026-04-26] member_role 物理枚举 → 主 role_code 反推（含 verifier/staff 历史值）
MEMBER_ROLE_TO_ROLE_CODE: dict[MerchantMemberRole, str] = {
    MerchantMemberRole.owner: "boss",
    MerchantMemberRole.store_manager: "store_manager",
    MerchantMemberRole.finance: "finance",
    MerchantMemberRole.verifier: "clerk",  # 核销员合并到店员
    MerchantMemberRole.staff: "clerk",     # 历史 staff 合并到店员
}

# [2026-04-26] 历史/别名 role_code 全量归一化为 4 角色之一
ROLE_LEGACY_MAP: dict[str, str] = {
    "owner": "boss",
    "manager": "store_manager",
    "verifier": "clerk",
    "staff": "clerk",
}

def _normalize_role_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    code = str(raw).strip().lower()
    if not code:
        return None
    return ROLE_LEGACY_MAP.get(code, code)


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
        # [2026-05-01 门店地图能力 PRD v1.0] 经纬度 + 省市区
        lat=float(store.lat) if getattr(store, "lat", None) is not None else None,
        lng=float(store.lng) if getattr(store, "lng", None) is not None else None,
        longitude=float(store.lng) if getattr(store, "lng", None) is not None else None,
        latitude=float(store.lat) if getattr(store, "lat", None) is not None else None,
        province=getattr(store, "province", None),
        city=getattr(store, "city", None),
        district=getattr(store, "district", None),
        status=store.status,
        member_role=membership.member_role.value,
        module_codes=module_codes,
        category_id=getattr(store, "category_id", None),
        category_code=category_code,
        category_name=category_name,
        # [2026-05-02 H5 下单流程优化 PRD v1.0]
        slot_capacity=getattr(store, "slot_capacity", 10) or 10,
        business_start=getattr(store, "business_start", None),
        business_end=getattr(store, "business_end", None),
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
    primary_member_role: Optional[MerchantMemberRole] = None
    user_id_for_staff_count = user.id
    boss_store_ids: set[int] = set()
    for membership in memberships_result.scalars().all():
        if membership.member_role == MerchantMemberRole.owner:
            merchant_identity_type = "owner"
            boss_store_ids.add(membership.store_id)
        elif merchant_identity_type is None:
            merchant_identity_type = "staff"
        # 主 member_role 取第一条非 None 的记录（owner 优先）
        if primary_member_role is None or membership.member_role == MerchantMemberRole.owner:
            primary_member_role = membership.member_role
        if role_code is None and getattr(membership, "role_code", None):
            role_code = _normalize_role_code(membership.role_code)
        store_item = await _build_store_response(db, membership)
        if store_item:
            stores.append(store_item)
    # [2026-04-26] 兜底推断 role_code：优先按 member_role 真实枚举映射，
    # 然后再归一化历史值，确保最终落在 4 角色之一
    if role_code is None and primary_member_role is not None:
        role_code = MEMBER_ROLE_TO_ROLE_CODE.get(primary_member_role)
    if role_code is None:
        role_code = "boss" if merchant_identity_type == "owner" else "clerk"
    role_code = _normalize_role_code(role_code) or role_code
    role_name = ROLE_NAME_MAP.get(role_code) if role_code else None

    # [2026-04-26] 计算该商家下"非老板员工"数量，仅当本账号是老板时才有意义
    staff_count = 0
    if role_code == "boss" and boss_store_ids:
        cnt_res = await db.execute(
            select(func.count(func.distinct(MerchantStoreMembership.user_id))).where(
                MerchantStoreMembership.store_id.in_(boss_store_ids),
                MerchantStoreMembership.user_id != user_id_for_staff_count,
                MerchantStoreMembership.status == "active",
                MerchantStoreMembership.member_role != MerchantMemberRole.owner,
            )
        )
        staff_count = int(cnt_res.scalar() or 0)

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
        staff_count=staff_count,
    )


async def _upsert_merchant_account(
    db: AsyncSession,
    data: MerchantAccountUpsert,
    existing_user: User | None = None,
) -> MerchantAccountSummaryResponse:
    if data.merchant_identity_type not in {"owner", "staff"}:
        raise HTTPException(status_code=400, detail="商家身份类型无效")

    # [2026-04-26] role_code 校验：先归一化历史别名，再校验是否属于 4 角色
    role_code = _normalize_role_code((data.role_code or "").strip() or None)
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
    include_inactive: bool = False,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cat_res = await db.execute(select(MerchantCategory))
    category_by_id = {c.id: c for c in cat_res.scalars().all()}
    category_by_code = {c.code: c for c in category_by_id.values()}

    # [2026-04-29] 排序：active 在前，再按 created_at desc
    query = select(MerchantStore).order_by(
        case((MerchantStore.status == "active", 0), else_=1),
        MerchantStore.created_at.desc(),
    )
    # [2026-04-29] 已停用门店显示控制
    if not include_inactive:
        query = query.where(MerchantStore.status == "active")
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
            # [2026-05-01 门店地图能力 PRD v1.0] 经纬度 + 省市区
            "lat": float(store.lat) if store.lat is not None else None,
            "lng": float(store.lng) if store.lng is not None else None,
            "longitude": float(store.lng) if store.lng is not None else None,
            "latitude": float(store.lat) if store.lat is not None else None,
            "province": getattr(store, "province", None),
            "city": getattr(store, "city", None),
            "district": getattr(store, "district", None),
            "status": store.status,
            "created_at": store.created_at.isoformat() if store.created_at else None,
        })
    return {"items": items}


async def _generate_store_code(db: AsyncSession) -> str:
    """自动生成门店编号：MD + 5位数字，如 MD00001"""
    result = await db.execute(
        select(MerchantStore.store_code).where(
            MerchantStore.store_code.like("MD%")
        ).order_by(MerchantStore.store_code.desc()).limit(1)
    )
    last_code = result.scalar()
    if last_code:
        try:
            max_num = int(last_code[2:])
        except (ValueError, IndexError):
            max_num = 0
    else:
        max_num = 0
    next_num = max_num + 1
    if next_num > 99999:
        raise HTTPException(status_code=400, detail="门店编号已达上限(MD99999)，无法继续创建")
    return f"MD{next_num:05d}"


def _normalize_lat_lng(payload: dict) -> dict:
    """[2026-05-01 门店地图能力 PRD v1.0] 兼容 longitude/latitude 与 lat/lng 双命名。
    任一字段非空即可，统一回写到 lat/lng；同时校验范围合法性。
    """
    lat = payload.pop("latitude", None)
    lng = payload.pop("longitude", None)
    if lat is not None and payload.get("lat") is None:
        payload["lat"] = lat
    if lng is not None and payload.get("lng") is None:
        payload["lng"] = lng
    if payload.get("lat") is not None:
        try:
            v = float(payload["lat"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="纬度必须是数字")
        if v < -90 or v > 90:
            raise HTTPException(status_code=400, detail="纬度必须在 -90 到 90 之间")
        payload["lat"] = v
    if payload.get("lng") is not None:
        try:
            v = float(payload["lng"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="经度必须是数字")
        if v < -180 or v > 180:
            raise HTTPException(status_code=400, detail="经度必须在 -180 到 180 之间")
        payload["lng"] = v
    return payload


@router.post("/stores")
async def create_store(
    data: MerchantStoreCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # [2026-04-24] 新建门店必选类别
    if data.category_id is None:
        raise HTTPException(status_code=400, detail="请选择门店所属类别")
    await _validate_category_id(db, data.category_id)
    # [2026-04-29] 自动生成 store_code
    store_code = await _generate_store_code(db)
    store_data = data.model_dump(exclude={"store_code"})
    # [2026-05-01 门店地图能力 PRD v1.0] 经纬度新建必填
    store_data = _normalize_lat_lng(store_data)
    if store_data.get("lat") is None or store_data.get("lng") is None:
        raise HTTPException(status_code=400, detail="请在地图上选择门店位置（经纬度必填）")
    store_data["store_code"] = store_code
    store = MerchantStore(**store_data)
    db.add(store)
    await db.flush()
    return {"id": store.id, "store_code": store_code, "message": "门店创建成功"}


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
        # [2026-05-01 门店地图能力 PRD v1.0] 经纬度 + 省市区
        "lat": float(store.lat) if store.lat is not None else None,
        "lng": float(store.lng) if store.lng is not None else None,
        "longitude": float(store.lng) if store.lng is not None else None,
        "latitude": float(store.lat) if store.lat is not None else None,
        "province": getattr(store, "province", None),
        "city": getattr(store, "city", None),
        "district": getattr(store, "district", None),
        "status": store.status,
        # [2026-05-02 H5 下单流程优化 PRD v1.0]
        "slot_capacity": getattr(store, "slot_capacity", 10) or 10,
        "business_start": getattr(store, "business_start", None),
        "business_end": getattr(store, "business_end", None),
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
    # [2026-04-29] store_code 不可修改
    payload.pop("store_code", None)
    if "category_id" in payload:
        await _validate_category_id(db, payload["category_id"])
    # [2026-05-01 门店地图能力 PRD v1.0] 经纬度规范化
    payload = _normalize_lat_lng(payload)
    for key, value in payload.items():
        setattr(store, key, value)
    store.updated_at = datetime.utcnow()
    return {"message": "门店更新成功"}


@router.get("/accounts")
async def list_accounts(
    keyword: str | None = None,
    role_code: str | None = "boss",  # [2026-04-26] 默认只展示老板账号；显式传 "all" 可关闭过滤
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
    # [2026-04-26] 角色过滤：默认只展示老板（boss）；传 role_code=all 表示不过滤
    rc = (role_code or "").strip().lower()
    if rc and rc != "all":
        normalized = _normalize_role_code(rc) or rc
        items = [it for it in items if (it.role_code or "") == normalized]
    return {"items": items}


@router.get("/accounts/{user_id}/staff", response_model=MerchantStaffListResponse)
async def list_merchant_staff(
    user_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-26] 列出某老板账号所属商家下的所有非老板员工。

    数据范围：
    - 取该 user 的所有 owner 类型 membership 对应的 store_ids 作为"该商家下属门店集合"
    - 在这些门店下查找所有 member_role != owner 的成员（store_manager/finance/verifier/staff）
    - 不包含老板自身
    """
    # 校验 user 存在
    user_res = await db.execute(select(User).where(User.id == user_id))
    target_user = user_res.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 取该 user 名下所有 owner 门店
    owner_ms_res = await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.user_id == user_id,
            MerchantStoreMembership.member_role == MerchantMemberRole.owner,
            MerchantStoreMembership.status == "active",
        )
    )
    owner_memberships = owner_ms_res.scalars().all()
    store_ids = sorted({m.store_id for m in owner_memberships})

    # 取商家名称（取首个 owner 门店名作为标识）
    merchant_name: Optional[str] = None
    if store_ids:
        store_res = await db.execute(
            select(MerchantStore).where(MerchantStore.id.in_(store_ids))
        )
        store_list = store_res.scalars().all()
        if store_list:
            merchant_name = store_list[0].store_name

    if not store_ids:
        return MerchantStaffListResponse(items=[], total=0, merchant_name=merchant_name)

    # 找该商家下所有非老板员工 membership
    staff_ms_res = await db.execute(
        select(MerchantStoreMembership).where(
            MerchantStoreMembership.store_id.in_(store_ids),
            MerchantStoreMembership.user_id != user_id,
            MerchantStoreMembership.status == "active",
            MerchantStoreMembership.member_role != MerchantMemberRole.owner,
        )
    )
    staff_memberships = staff_ms_res.scalars().all()

    # 按 user_id 聚合（同一个员工可能在多个门店有 membership）
    user_to_memberships: dict[int, list[MerchantStoreMembership]] = {}
    for m in staff_memberships:
        user_to_memberships.setdefault(m.user_id, []).append(m)

    if not user_to_memberships:
        return MerchantStaffListResponse(items=[], total=0, merchant_name=merchant_name)

    # 一次性加载相关用户、门店名称
    related_user_ids = list(user_to_memberships.keys())
    users_res = await db.execute(select(User).where(User.id.in_(related_user_ids)))
    user_map = {u.id: u for u in users_res.scalars().all()}

    store_name_res = await db.execute(
        select(MerchantStore.id, MerchantStore.store_name).where(
            MerchantStore.id.in_(store_ids)
        )
    )
    store_name_map = {sid: sname for sid, sname in store_name_res.all()}

    items: list[MerchantStaffItemResponse] = []
    for uid, ms_list in user_to_memberships.items():
        u = user_map.get(uid)
        if not u:
            continue
        # 主 role：优先 store_manager > finance > verifier > staff > 取第一条
        role_priority = {
            MerchantMemberRole.store_manager: 0,
            MerchantMemberRole.finance: 1,
            MerchantMemberRole.verifier: 2,
            MerchantMemberRole.staff: 3,
        }
        sorted_ms = sorted(
            ms_list,
            key=lambda x: role_priority.get(x.member_role, 99),
        )
        primary = sorted_ms[0]
        rc = _normalize_role_code(getattr(primary, "role_code", None))
        if not rc:
            rc = MEMBER_ROLE_TO_ROLE_CODE.get(primary.member_role, "clerk")
        rn = ROLE_NAME_MAP.get(rc, rc)
        store_names = sorted({
            store_name_map.get(m.store_id, "")
            for m in ms_list
            if store_name_map.get(m.store_id)
        })
        # 名称：优先 user.nickname；否则脱敏手机号
        display_name = u.nickname
        if not display_name and u.phone:
            display_name = u.phone[:3] + "****" + u.phone[-4:] if len(u.phone) >= 7 else u.phone

        items.append(
            MerchantStaffItemResponse(
                id=u.id,
                phone=u.phone or "",
                name=display_name,
                role_code=rc,
                role_name=rn,
                status=u.status or "active",
                status_text="正常" if (u.status or "active") == "active" else "禁用",
                created_at=u.created_at,
                last_login_at=getattr(u, "last_login_at", None),
                store_names=list(store_names),
            )
        )

    # 按角色优先级 + 创建时间排序（4 角色统一后无 verifier/staff）
    role_sort = {"store_manager": 0, "finance": 1, "clerk": 2}
    items.sort(key=lambda it: (role_sort.get(it.role_code or "", 99), -(it.id or 0)))

    return MerchantStaffListResponse(
        items=items,
        total=len(items),
        merchant_name=merchant_name,
    )


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
