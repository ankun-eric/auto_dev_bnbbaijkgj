"""[PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」页面 V2 接口。

提供面向 H5 健康档案「我的设备」页面（/devices）的全套接口：

- GET  /api/devices/catalog          支持设备目录（按品牌分组：宾尼/华为/小米/苹果/其他）
- GET  /api/devices/my               当前用户已绑定设备列表
- POST /api/devices/bind             绑定设备
- POST /api/devices/unbind           解绑（软删除）
- PATCH /api/devices/binding/{id}    编辑别名 / 使用人

数据模型：
- DeviceCatalog（品牌目录，启动时按 SEED_CATALOG 幂等 seed）
- DeviceUserBinding（用户绑定关系，支持软删除 + 同 SN 多账户共享）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.devices_v2 import DeviceCatalog, DeviceUserBinding
from app.models.models import FamilyMember, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["My Devices V2"])


# ──────────────────────────────────────────────────────────
# 品牌目录种子数据（按 PRD「3.3 区域二」对齐）
# ──────────────────────────────────────────────────────────

BRAND_ORDER = ["binni", "huawei", "xiaomi", "apple", "other"]
BRAND_NAMES = {
    "binni": "宾尼",
    "huawei": "华为",
    "xiaomi": "小米",
    "apple": "苹果",
    "other": "其他",
}

SEED_CATALOG: List[Dict[str, Any]] = [
    # 宾尼自有 7 项（全部已接通、唯一类 4 / 可多绑 3）
    {"brand_code": "binni", "category_code": "smartwatch", "device_name": "宾尼智能手表", "icon": "⌚", "is_active": True, "is_unique": True, "sort_order": 1},
    {"brand_code": "binni", "category_code": "sleep_pad", "device_name": "宾尼睡眠检测垫", "icon": "🛏", "is_active": True, "is_unique": True, "sort_order": 2},
    {"brand_code": "binni", "category_code": "bp_meter", "device_name": "宾尼血压计", "icon": "💓", "is_active": True, "is_unique": True, "sort_order": 3},
    {"brand_code": "binni", "category_code": "glucose_meter", "device_name": "宾尼血糖仪", "icon": "🩸", "is_active": True, "is_unique": True, "sort_order": 4},
    {"brand_code": "binni", "category_code": "smoke_alarm", "device_name": "宾尼烟雾报警器", "icon": "🚨", "is_active": True, "is_unique": False, "sort_order": 5},
    {"brand_code": "binni", "category_code": "water_alarm", "device_name": "宾尼水位报警器", "icon": "💧", "is_active": True, "is_unique": False, "sort_order": 6},
    {"brand_code": "binni", "category_code": "sos_caller", "device_name": "宾尼紧急呼叫器", "icon": "🆘", "is_active": True, "is_unique": False, "sort_order": 7},
    # 华为：手环已接通、其他敬请期待
    {"brand_code": "huawei", "category_code": "band", "device_name": "华为手环", "icon": "⌚", "is_active": True, "is_unique": True, "sort_order": 1},
    {"brand_code": "huawei", "category_code": "smartwatch", "device_name": "华为手表 GT", "icon": "⌚", "is_active": False, "is_unique": True, "sort_order": 2},
    {"brand_code": "huawei", "category_code": "fat_scale", "device_name": "华为体脂秤", "icon": "⚖️", "is_active": False, "is_unique": True, "sort_order": 3},
    # 小米：全部敬请期待
    {"brand_code": "xiaomi", "category_code": "band", "device_name": "小米手环", "icon": "⌚", "is_active": False, "is_unique": True, "sort_order": 1},
    {"brand_code": "xiaomi", "category_code": "scale", "device_name": "小米体重秤", "icon": "⚖️", "is_active": False, "is_unique": True, "sort_order": 2},
    # 苹果：敬请期待
    {"brand_code": "apple", "category_code": "smartwatch", "device_name": "Apple Watch", "icon": "⌚", "is_active": False, "is_unique": True, "sort_order": 1},
    # 其他：全部敬请期待
    {"brand_code": "other", "category_code": "glucose_meter", "device_name": "三诺血糖仪", "icon": "🩸", "is_active": False, "is_unique": True, "sort_order": 1},
    {"brand_code": "other", "category_code": "bp_meter", "device_name": "鱼跃血压计", "icon": "💓", "is_active": False, "is_unique": True, "sort_order": 2},
    {"brand_code": "other", "category_code": "bp_meter_omron", "device_name": "欧姆龙血压计", "icon": "💓", "is_active": False, "is_unique": True, "sort_order": 3},
    {"brand_code": "other", "category_code": "spo2_meter", "device_name": "鱼跃血氧仪", "icon": "🫁", "is_active": False, "is_unique": True, "sort_order": 4},
]


async def seed_device_catalog(db: AsyncSession) -> Dict[str, int]:
    """幂等 seed 品牌设备目录。

    匹配键：(brand_code, device_name)。已存在的记录会同步更新其他字段
    （icon / is_active / is_unique / sort_order / category_code），
    使 seed 数据能够随版本更新。
    """
    res = await db.execute(select(DeviceCatalog))
    existing = list(res.scalars().all())
    idx: Dict[tuple, DeviceCatalog] = {(d.brand_code, d.device_name): d for d in existing}

    inserted = 0
    updated = 0
    for item in SEED_CATALOG:
        key = (item["brand_code"], item["device_name"])
        row = idx.get(key)
        if row is None:
            row = DeviceCatalog(
                brand_code=item["brand_code"],
                brand_name=BRAND_NAMES.get(item["brand_code"], item["brand_code"]),
                category_code=item["category_code"],
                device_name=item["device_name"],
                icon=item["icon"],
                is_active=bool(item["is_active"]),
                is_unique=bool(item["is_unique"]),
                sort_order=int(item["sort_order"]),
            )
            db.add(row)
            inserted += 1
        else:
            changed = False
            if row.icon != item["icon"]:
                row.icon = item["icon"]
                changed = True
            if row.is_active != bool(item["is_active"]):
                row.is_active = bool(item["is_active"])
                changed = True
            if row.is_unique != bool(item["is_unique"]):
                row.is_unique = bool(item["is_unique"])
                changed = True
            if row.sort_order != int(item["sort_order"]):
                row.sort_order = int(item["sort_order"])
                changed = True
            if row.category_code != item["category_code"]:
                row.category_code = item["category_code"]
                changed = True
            if row.brand_name != BRAND_NAMES.get(item["brand_code"], item["brand_code"]):
                row.brand_name = BRAND_NAMES.get(item["brand_code"], item["brand_code"])
                changed = True
            if changed:
                updated += 1
    await db.flush()
    return {"inserted": inserted, "updated": updated, "total": len(SEED_CATALOG)}


# ──────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────


def _mask_sn(sn: Optional[str]) -> str:
    """SN 脱敏：前 3 + 中间 *** + 后 4，过短时全打码。"""
    if not sn:
        return ""
    s = str(sn).strip()
    if len(s) <= 7:
        return "*" * len(s)
    return f"{s[:3]}{'*' * 4}{s[-4:]}"


async def _resolve_member(db: AsyncSession, user: User, member_id: int) -> Optional[Dict[str, Any]]:
    """通过 member_id 解析使用人显示信息。

    约定：当 member_id <= 0 或者命中本人 family_member.id 时返回"本人"，
    否则查询 family_members 表。
    """
    if member_id is None:
        return None
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == int(member_id),
            FamilyMember.user_id == user.id,
            FamilyMember.status == "bound",
        )
    )
    m = res.scalar_one_or_none()
    if m is None:
        return None
    return {
        "member_id": m.id,
        "member_nickname": m.nickname or ("本人" if m.is_self else m.relationship_type or "家人"),
        "member_relation": m.relationship_type or ("本人" if m.is_self else "家人"),
        "is_self": bool(m.is_self),
    }


def _binding_to_dict(b: DeviceUserBinding, catalog: DeviceCatalog, member_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": b.id,
        "catalog_id": b.catalog_id,
        "brand_code": catalog.brand_code,
        "brand_name": catalog.brand_name,
        "category_code": catalog.category_code,
        "device_name": catalog.device_name,
        "icon": catalog.icon,
        "icon_url": catalog.icon_url,
        "scene_group_id": catalog.scene_group_id,
        "jump_url": catalog.jump_url,
        "is_unique": bool(catalog.is_unique),
        "sn": b.sn,
        "sn_masked": _mask_sn(b.sn),
        "alias": b.alias,
        "member_id": b.member_id,
        "member_nickname": (member_info or {}).get("member_nickname"),
        "member_relation": (member_info or {}).get("member_relation"),
        "member_is_self": (member_info or {}).get("is_self", False),
        "bound_at": b.bound_at.strftime("%Y-%m-%d %H:%M") if b.bound_at else None,
        "is_active": bool(b.is_active),
    }


# ──────────────────────────────────────────────────────────
# GET /catalog
# ──────────────────────────────────────────────────────────


@router.get("/catalog")
async def get_catalog(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按品牌分组返回支持设备目录。

    同时返回当前用户对每条 catalog 的「已绑定数量」，前端用来判断按钮态：
    - is_unique=True 且 bound_count>=1 → 显示「已绑定」灰按钮
    - is_unique=False 且 bound_count>=1 → 显示「继续绑定」描边按钮
    - is_unique=False 且 bound_count==0 / is_unique=True 且 bound_count==0 → 显示「绑定」实心按钮
    - is_active=False → 显示「敬请期待」灰按钮（不可点击）
    """
    res = await db.execute(select(DeviceCatalog).order_by(DeviceCatalog.brand_code, DeviceCatalog.sort_order, DeviceCatalog.id))
    catalogs = list(res.scalars().all())

    bind_res = await db.execute(
        select(DeviceUserBinding).where(
            DeviceUserBinding.user_id == current_user.id,
            DeviceUserBinding.is_active == True,  # noqa: E712
        )
    )
    bind_counts: Dict[int, int] = {}
    for b in bind_res.scalars().all():
        bind_counts[b.catalog_id] = bind_counts.get(b.catalog_id, 0) + 1

    by_brand: Dict[str, List[Dict[str, Any]]] = {b: [] for b in BRAND_ORDER}
    for c in catalogs:
        cnt = bind_counts.get(c.id, 0)
        by_brand.setdefault(c.brand_code, []).append({
            "id": c.id,
            "brand_code": c.brand_code,
            "brand_name": c.brand_name,
            "category_code": c.category_code,
            "device_name": c.device_name,
            "icon": c.icon,
            "icon_url": c.icon_url,
            "scene_group_id": c.scene_group_id,
            "jump_url": c.jump_url,
            "is_active": bool(c.is_active),
            "is_unique": bool(c.is_unique),
            "sort_order": c.sort_order,
            "bound_count": cnt,
        })

    groups = []
    for brand_code in BRAND_ORDER:
        items = by_brand.get(brand_code, [])
        if not items:
            continue
        groups.append({
            "brand_code": brand_code,
            "brand_name": BRAND_NAMES.get(brand_code, brand_code),
            "items": items,
        })
    return {"groups": groups, "total": sum(len(g["items"]) for g in groups)}


# ──────────────────────────────────────────────────────────
# GET /my
# ──────────────────────────────────────────────────────────


@router.get("/my")
async def list_my_devices(
    member_id: Optional[int] = Query(None, description="家庭成员 id；为空或 0 时返回全部（本人 Tab），>0 时只返回该成员的设备"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前用户已绑定设备列表（按绑定时间倒序），支持按成员维度筛选。"""
    stmt = select(DeviceUserBinding).where(
        DeviceUserBinding.user_id == current_user.id,
        DeviceUserBinding.is_active == True,  # noqa: E712
    )
    if member_id is not None and member_id > 0:
        stmt = stmt.where(DeviceUserBinding.member_id == member_id)
    stmt = stmt.order_by(DeviceUserBinding.bound_at.desc(), DeviceUserBinding.id.desc())
    res = await db.execute(stmt)
    bindings = list(res.scalars().all())

    # 批量加载 catalog
    catalog_ids = list({b.catalog_id for b in bindings})
    catalog_map: Dict[int, DeviceCatalog] = {}
    if catalog_ids:
        cres = await db.execute(select(DeviceCatalog).where(DeviceCatalog.id.in_(catalog_ids)))
        catalog_map = {c.id: c for c in cres.scalars().all()}

    # 批量加载 family_member
    member_ids = list({b.member_id for b in bindings if b.member_id})
    member_map: Dict[int, FamilyMember] = {}
    if member_ids:
        mres = await db.execute(
            select(FamilyMember).where(
                FamilyMember.id.in_(member_ids),
                FamilyMember.user_id == current_user.id,
            )
        )
        member_map = {m.id: m for m in mres.scalars().all()}

    items = []
    for b in bindings:
        c = catalog_map.get(b.catalog_id)
        if c is None:
            continue
        m = member_map.get(b.member_id) if b.member_id else None
        member_info = None
        if m is not None:
            member_info = {
                "member_id": m.id,
                "member_nickname": m.nickname or ("本人" if m.is_self else (m.relationship_type or "家人")),
                "member_relation": m.relationship_type or ("本人" if m.is_self else "家人"),
                "is_self": bool(m.is_self),
            }
        items.append(_binding_to_dict(b, c, member_info))
    return {"items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────
# POST /bind
# ──────────────────────────────────────────────────────────


class BindBody(BaseModel):
    catalog_id: int = Field(..., gt=0)
    sn: str = Field(..., min_length=1, max_length=128)
    alias: Optional[str] = Field(None, max_length=20)
    member_id: Optional[int] = Field(None, description="家庭成员 id；为空时绑给「本人」")


async def _resolve_self_member_id(db: AsyncSession, user_id: int) -> Optional[int]:
    """返回当前账号的 is_self=True 的 family_member.id；不存在则返回 None。"""
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == user_id,
            FamilyMember.is_self == True,  # noqa: E712
            FamilyMember.status == "bound",
        ).limit(1)
    )
    m = res.scalar_one_or_none()
    return m.id if m else None


@router.post("/bind")
async def bind_device(
    body: BindBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """绑定一台设备。

    校验：
      1. catalog 存在且 is_active=True
      2. is_unique=True 时，当前用户不可重复绑定同一 catalog（应用层校验）
      3. SN 已被他账户绑定 → 允许（家庭共享）
    """
    sn = (body.sn or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="SN 不能为空")

    cres = await db.execute(select(DeviceCatalog).where(DeviceCatalog.id == body.catalog_id))
    catalog = cres.scalar_one_or_none()
    if catalog is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if not catalog.is_active:
        raise HTTPException(status_code=400, detail="该设备暂未接通，敬请期待")

    if catalog.is_unique:
        exists = await db.execute(
            select(DeviceUserBinding).where(
                DeviceUserBinding.user_id == current_user.id,
                DeviceUserBinding.catalog_id == catalog.id,
                DeviceUserBinding.is_active == True,  # noqa: E712
            )
        )
        if exists.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="该设备每位用户仅可绑定 1 台，如需更换请先解绑")

    member_id = body.member_id
    if member_id is None:
        member_id = await _resolve_self_member_id(db, current_user.id)

    # 校验 member 归属
    if member_id is not None:
        mres = await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == member_id,
                FamilyMember.user_id == current_user.id,
                FamilyMember.status == "bound",
            )
        )
        if mres.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="使用人不存在或无权选择")

    binding = DeviceUserBinding(
        user_id=current_user.id,
        catalog_id=catalog.id,
        sn=sn,
        alias=(body.alias or None),
        member_id=member_id,
        bound_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(binding)
    await db.flush()
    logger.info("[devices/bind] user=%s catalog=%s sn_masked=%s member=%s id=%s",
                current_user.id, catalog.id, _mask_sn(sn), member_id, binding.id)

    member_info = await _resolve_member(db, current_user, member_id) if member_id else None
    return {
        "id": binding.id,
        "message": "已绑定",
        "binding": _binding_to_dict(binding, catalog, member_info),
    }


# ──────────────────────────────────────────────────────────
# POST /unbind
# ──────────────────────────────────────────────────────────


class UnbindBody(BaseModel):
    binding_id: int = Field(..., gt=0)


@router.post("/unbind")
async def unbind_device(
    body: UnbindBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解绑一条绑定记录（软删除）。

    历史数据将保留，仅停止后续新数据上传。
    """
    res = await db.execute(
        select(DeviceUserBinding).where(
            DeviceUserBinding.id == body.binding_id,
            DeviceUserBinding.user_id == current_user.id,
        )
    )
    b = res.scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="绑定记录不存在")
    if not b.is_active:
        return {"message": "已经是解绑状态", "id": b.id}
    b.is_active = False
    b.unbound_at = datetime.utcnow()
    await db.flush()
    logger.info("[devices/unbind] user=%s binding=%s catalog=%s", current_user.id, b.id, b.catalog_id)
    return {"message": "已解绑", "id": b.id}


# ──────────────────────────────────────────────────────────
# PATCH /binding/{id}
# ──────────────────────────────────────────────────────────


class EditBindingBody(BaseModel):
    alias: Optional[str] = Field(None, max_length=20)
    member_id: Optional[int] = None


@router.patch("/binding/{binding_id}")
async def edit_binding(
    binding_id: int,
    body: EditBindingBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑绑定记录的别名 / 使用人。SN 和设备品类不可改。"""
    res = await db.execute(
        select(DeviceUserBinding).where(
            DeviceUserBinding.id == binding_id,
            DeviceUserBinding.user_id == current_user.id,
            DeviceUserBinding.is_active == True,  # noqa: E712
        )
    )
    b = res.scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="绑定记录不存在或已解绑")

    data = body.model_dump(exclude_unset=True)
    if "alias" in data:
        alias = (data["alias"] or "").strip() or None
        b.alias = alias
    if "member_id" in data:
        member_id = data["member_id"]
        if member_id is not None:
            mres = await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == member_id,
                    FamilyMember.user_id == current_user.id,
                    FamilyMember.status == "bound",
                )
            )
            if mres.scalar_one_or_none() is None:
                raise HTTPException(status_code=400, detail="使用人不存在或无权选择")
        b.member_id = member_id

    await db.flush()

    cres = await db.execute(select(DeviceCatalog).where(DeviceCatalog.id == b.catalog_id))
    catalog = cres.scalar_one()
    member_info = await _resolve_member(db, current_user, b.member_id) if b.member_id else None
    return {
        "message": "已保存",
        "binding": _binding_to_dict(b, catalog, member_info),
    }

# ──────────────────────────────────────────────────────────
# [PRD-HEALTH-ARCHIVE-CO-MANAGE 2026-06-05] 设备场景分类 API
# ──────────────────────────────────────────────────────────


class SceneGroupOut(BaseModel):
    id: int
    name: str
    sort_order: int
    is_enabled: bool
    device_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SceneGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    sort_order: int = Field(0, ge=0)
    is_enabled: bool = True


class SceneGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    sort_order: Optional[int] = Field(None, ge=0)
    is_enabled: Optional[bool] = None


@router.get("/scene-groups")
async def list_scene_groups(
    include_disabled: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取设备场景分类列表，附带每个分类下的设备绑定数量。"""
    from app.models.models import DeviceSceneGroup
    query = select(DeviceSceneGroup)
    if not include_disabled:
        query = query.where(DeviceSceneGroup.is_enabled == True)  # noqa: E712
    query = query.order_by(DeviceSceneGroup.sort_order, DeviceSceneGroup.id)
    groups_res = await db.execute(query)
    groups = list(groups_res.scalars().all())

    # 统计每个分类下的设备绑定数量
    group_ids = [g.id for g in groups]
    device_counts: dict[int, int] = {}
    if group_ids:
        from app.models.devices_v2 import DeviceCatalog as DC, DeviceUserBinding as DUB
        cat_res = await db.execute(
            select(DC.id, DC.scene_group_id).where(DC.scene_group_id.in_(group_ids))
        )
        catalog_by_group: dict[int, list[int]] = {}
        for cid, sgid in cat_res.all():
            catalog_by_group.setdefault(sgid, []).append(cid)

        if catalog_by_group:
            for sgid, cids in catalog_by_group.items():
                cnt_res = await db.execute(
                    select(func.count(DUB.id)).where(
                        DUB.catalog_id.in_(cids),
                        DUB.is_active == True,  # noqa: E712
                        DUB.user_id == current_user.id,
                    )
                )
                device_counts[sgid] = int(cnt_res.scalar() or 0)

    items = []
    for g in groups:
        items.append(SceneGroupOut(
            id=g.id,
            name=g.name,
            sort_order=g.sort_order,
            is_enabled=bool(g.is_enabled),
            device_count=device_counts.get(g.id, 0),
            created_at=g.created_at.isoformat() if g.created_at else None,
            updated_at=g.updated_at.isoformat() if g.updated_at else None,
        ))
    return {"items": items, "total": len(items)}


@router.get("/scene-groups/{group_id}")
async def get_scene_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个场景分类详情。"""
    from app.models.models import DeviceSceneGroup
    g = await db.get(DeviceSceneGroup, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="场景分类不存在")
    return SceneGroupOut(
        id=g.id,
        name=g.name,
        sort_order=g.sort_order,
        is_enabled=bool(g.is_enabled),
        device_count=0,
        created_at=g.created_at.isoformat() if g.created_at else None,
        updated_at=g.updated_at.isoformat() if g.updated_at else None,
    )


@router.post("/scene-groups")
async def create_scene_group(
    body: SceneGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建场景分类（需管理员权限）。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from app.models.models import DeviceSceneGroup
    g = DeviceSceneGroup(
        name=body.name,
        sort_order=body.sort_order,
        is_enabled=body.is_enabled,
    )
    db.add(g)
    await db.flush()
    return SceneGroupOut(
        id=g.id,
        name=g.name,
        sort_order=g.sort_order,
        is_enabled=bool(g.is_enabled),
        device_count=0,
        created_at=g.created_at.isoformat() if g.created_at else None,
        updated_at=g.updated_at.isoformat() if g.updated_at else None,
    )


@router.put("/scene-groups/{group_id}")
async def update_scene_group(
    group_id: int,
    body: SceneGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑场景分类（需管理员权限）。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from app.models.models import DeviceSceneGroup
    g = await db.get(DeviceSceneGroup, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="场景分类不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(g, k, v)
    await db.flush()
    return SceneGroupOut(
        id=g.id,
        name=g.name,
        sort_order=g.sort_order,
        is_enabled=bool(g.is_enabled),
        device_count=0,
        created_at=g.created_at.isoformat() if g.created_at else None,
        updated_at=g.updated_at.isoformat() if g.updated_at else None,
    )


@router.delete("/scene-groups/{group_id}")
async def delete_scene_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除场景分类（需管理员权限，仅当分类下无设备时可删除）。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    from app.models.models import DeviceSceneGroup
    from app.models.devices_v2 import DeviceCatalog as DC
    g = await db.get(DeviceSceneGroup, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="场景分类不存在")
    # 检查分类下是否有设备
    cat_cnt = (await db.execute(
        select(func.count(DC.id)).where(DC.scene_group_id == group_id)
    )).scalar() or 0
    if cat_cnt > 0:
        raise HTTPException(status_code=400, detail="该分类下还有设备，请先移除设备后再删除")
    await db.delete(g)
    await db.flush()
    return {"message": "已删除"}


# ──────────────────────────────────────────────────────────
# [PRD-HEALTH-ARCHIVE-CO-MANAGE 2026-06-05] 设备目录管理 API（admin）
# ──────────────────────────────────────────────────────────


class CatalogAdminOut(BaseModel):
    id: int
    brand_code: str
    brand_name: str
    category_code: str
    device_name: str
    icon: Optional[str] = None
    icon_url: Optional[str] = None
    scene_group_id: Optional[int] = None
    jump_url: Optional[str] = None
    is_active: bool
    is_unique: bool
    sort_order: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CatalogAdminUpdate(BaseModel):
    brand_code: Optional[str] = Field(None, max_length=32)
    brand_name: Optional[str] = Field(None, max_length=64)
    category_code: Optional[str] = Field(None, max_length=64)
    device_name: Optional[str] = Field(None, max_length=128)
    icon: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = Field(None, max_length=500)
    scene_group_id: Optional[int] = None
    jump_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    is_unique: Optional[bool] = None
    sort_order: Optional[int] = None


class CatalogAdminCreate(BaseModel):
    brand_code: str = Field(..., max_length=32)
    brand_name: str = Field(..., max_length=64)
    category_code: str = Field(..., max_length=64)
    device_name: str = Field(..., max_length=128)
    icon: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = Field(None, max_length=500)
    scene_group_id: Optional[int] = None
    jump_url: Optional[str] = Field(None, max_length=500)
    is_active: bool = False
    is_unique: bool = True
    sort_order: int = 0


@router.get("/admin/catalog")
async def admin_list_catalog(
    scene_group_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F11] 管理后台：设备目录列表。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    query = select(DeviceCatalog)
    if scene_group_id is not None:
        query = query.where(DeviceCatalog.scene_group_id == scene_group_id)
    query = query.order_by(DeviceCatalog.brand_code, DeviceCatalog.sort_order, DeviceCatalog.id)
    res = await db.execute(query)
    items = []
    for c in res.scalars().all():
        items.append(CatalogAdminOut(
            id=c.id,
            brand_code=c.brand_code,
            brand_name=c.brand_name,
            category_code=c.category_code,
            device_name=c.device_name,
            icon=c.icon,
            icon_url=c.icon_url,
            scene_group_id=c.scene_group_id,
            jump_url=c.jump_url,
            is_active=bool(c.is_active),
            is_unique=bool(c.is_unique),
            sort_order=c.sort_order,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        ))
    return {"items": items, "total": len(items)}


@router.post("/admin/catalog")
async def admin_create_catalog(
    body: CatalogAdminCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F11] 管理后台：新增设备目录。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    c = DeviceCatalog(
        brand_code=body.brand_code,
        brand_name=body.brand_name,
        category_code=body.category_code,
        device_name=body.device_name,
        icon=body.icon,
        icon_url=body.icon_url,
        scene_group_id=body.scene_group_id,
        jump_url=body.jump_url,
        is_active=body.is_active,
        is_unique=body.is_unique,
        sort_order=body.sort_order,
    )
    db.add(c)
    await db.flush()
    return CatalogAdminOut(
        id=c.id,
        brand_code=c.brand_code,
        brand_name=c.brand_name,
        category_code=c.category_code,
        device_name=c.device_name,
        icon=c.icon,
        icon_url=c.icon_url,
        scene_group_id=c.scene_group_id,
        jump_url=c.jump_url,
        is_active=bool(c.is_active),
        is_unique=bool(c.is_unique),
        sort_order=c.sort_order,
        created_at=c.created_at.isoformat() if c.created_at else None,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


@router.put("/admin/catalog/{catalog_id}")
async def admin_update_catalog(
    catalog_id: int,
    body: CatalogAdminUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F11] 管理后台：编辑设备目录。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    c = await db.get(DeviceCatalog, catalog_id)
    if not c:
        raise HTTPException(status_code=404, detail="设备不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)
    await db.flush()
    return CatalogAdminOut(
        id=c.id,
        brand_code=c.brand_code,
        brand_name=c.brand_name,
        category_code=c.category_code,
        device_name=c.device_name,
        icon=c.icon,
        icon_url=c.icon_url,
        scene_group_id=c.scene_group_id,
        jump_url=c.jump_url,
        is_active=bool(c.is_active),
        is_unique=bool(c.is_unique),
        sort_order=c.sort_order,
        created_at=c.created_at.isoformat() if c.created_at else None,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


@router.delete("/admin/catalog/{catalog_id}")
async def admin_delete_catalog(
    catalog_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[F11] 管理后台：删除设备目录。"""
    if not getattr(current_user, "is_superuser", False) and getattr(current_user, "role", None) not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    c = await db.get(DeviceCatalog, catalog_id)
    if not c:
        raise HTTPException(status_code=404, detail="设备不存在")
    await db.delete(c)
    await db.flush()
    return {"message": "已删除"}
