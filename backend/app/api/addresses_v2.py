"""[2026-05-05 用户地址改造 PRD v1.0] 用户地址 v2 API。

路径：/api/v2/user/addresses, /api/v2/regions, /api/v2/app/version-check
"""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, UserAddress
from app.schemas.addresses_v2 import (
    AddressV2Create,
    AddressV2Response,
    AddressV2Update,
    ReverseGeocodeRequest,
    ReverseGeocodeResponse,
    SetDefaultRequest,
    VersionCheckResponse,
)

logger = logging.getLogger(__name__)

ADDRESS_LIMIT = 10
GEO_TIMEOUT = 2.0  # seconds，PRD F-08 要求 2s 超时不阻断

router = APIRouter(prefix="/api/v2", tags=["地址 v2"])


# ─────────── 行政区划 JSON ───────────

_REGIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "regions.json"
_regions_cache: Optional[dict[str, Any]] = None


def _load_regions() -> dict[str, Any]:
    global _regions_cache
    if _regions_cache is None:
        try:
            with _REGIONS_PATH.open("r", encoding="utf-8") as f:
                _regions_cache = json.load(f)
        except Exception as e:
            logger.error("加载行政区划数据失败: %s", e)
            _regions_cache = {"version": "0", "provinces": []}
    return _regions_cache


@router.get("/regions")
async def get_regions():
    """返回行政区划 JSON（前端默认走静态 JSON，本接口为版本对齐使用）。"""
    return _load_regions()


# ─────────── 高德 geocoding 辅助 ───────────


def _get_amap_server_key() -> str:
    return (
        os.getenv("AMAP_SERVER_KEY")
        or os.getenv("AMAP_KEY")
        or os.getenv("AMAP_WEB_JS_KEY")
        or ""
    ).strip()


async def _amap_geocode(address: str) -> Optional[tuple[float, float]]:
    """正向地理编码：地址字符串 → (lng, lat)。失败/超时返回 None。"""
    key = _get_amap_server_key()
    if not key or not address:
        logger.info("[geocode] 高德 Key 未配置或地址为空，跳过 geocoding")
        return None
    url = "https://restapi.amap.com/v3/geocode/geo"
    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT) as client:
            resp = await client.get(url, params={"key": key, "address": address})
            data = resp.json()
        if data.get("status") != "1" or not data.get("geocodes"):
            logger.info("[geocode] 无结果 address=%s status=%s", address, data.get("status"))
            return None
        loc = data["geocodes"][0].get("location") or ""
        if "," not in loc:
            return None
        lng, lat = loc.split(",", 1)
        return float(lng), float(lat)
    except Exception as e:
        logger.warning("[geocode] 高德调用失败/超时: %s", e)
        return None


async def _amap_regeo(lng: float, lat: float) -> Optional[dict[str, Any]]:
    """逆地理编码 (lng, lat) → 行政区+详细地址。失败/超时返回 None。"""
    key = _get_amap_server_key()
    if not key:
        return None
    url = "https://restapi.amap.com/v3/geocode/regeo"
    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT) as client:
            resp = await client.get(
                url,
                params={"key": key, "location": f"{lng},{lat}", "extensions": "base"},
            )
            data = resp.json()
        if data.get("status") != "1":
            return None
        return data.get("regeocode") or None
    except Exception as e:
        logger.warning("[regeo] 高德调用失败/超时: %s", e)
        return None


# ─────────── 业务工具 ───────────


def _to_response(addr: UserAddress) -> AddressV2Response:
    """模型 → 响应。兼容 v1 老数据（fallback name/phone/street）。"""
    consignee_name = addr.consignee_name or addr.name or ""
    consignee_phone = addr.consignee_phone or addr.phone or ""
    detail = addr.detail or addr.street or ""
    needs_region = not (addr.province and addr.city and addr.district)
    return AddressV2Response(
        id=addr.id,
        user_id=addr.user_id,
        consignee_name=consignee_name,
        consignee_phone=consignee_phone,
        province=addr.province or "",
        province_code=addr.province_code or "",
        city=addr.city or "",
        city_code=addr.city_code or "",
        district=addr.district or "",
        district_code=addr.district_code or "",
        detail=detail,
        longitude=float(addr.longitude) if addr.longitude is not None else None,
        latitude=float(addr.latitude) if addr.latitude is not None else None,
        tag=addr.tag or "",
        is_default=bool(addr.is_default),
        needs_region_completion=needs_region,
        created_at=addr.created_at,
        updated_at=addr.updated_at,
    )


async def _clear_other_defaults(db: AsyncSession, user_id: int, exclude_id: Optional[int] = None) -> None:
    stmt = select(UserAddress).where(
        UserAddress.user_id == user_id,
        UserAddress.is_default == True,  # noqa: E712
    )
    if exclude_id is not None:
        stmt = stmt.where(UserAddress.id != exclude_id)
    res = await db.execute(stmt)
    for a in res.scalars().all():
        a.is_default = False


async def _maybe_promote_new_default(db: AsyncSession, user_id: int) -> None:
    """删除默认地址后，由最近创建的另一条自动顶替为默认。"""
    res = await db.execute(
        select(UserAddress)
        .where(
            UserAddress.user_id == user_id,
            UserAddress.is_deleted == False,  # noqa: E712
            UserAddress.is_default == True,  # noqa: E712
        )
    )
    if res.scalar_one_or_none():
        return  # 仍存在默认
    res2 = await db.execute(
        select(UserAddress)
        .where(
            UserAddress.user_id == user_id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
        .order_by(UserAddress.created_at.desc())
        .limit(1)
    )
    candidate = res2.scalar_one_or_none()
    if candidate:
        candidate.is_default = True


# ─────────── CRUD 接口 ───────────


@router.get("/user/addresses")
async def list_addresses_v2(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(UserAddress)
        .where(
            UserAddress.user_id == current_user.id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
        .order_by(UserAddress.is_default.desc(), UserAddress.updated_at.desc(), UserAddress.created_at.desc())
    )
    items = [_to_response(a) for a in res.scalars().all()]
    return {"items": items, "total": len(items), "limit": ADDRESS_LIMIT}


@router.post("/user/addresses", status_code=201)
async def create_address_v2(
    data: AddressV2Create,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cnt_res = await db.execute(
        select(func.count(UserAddress.id)).where(
            UserAddress.user_id == current_user.id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
    )
    cnt = cnt_res.scalar() or 0
    if cnt >= ADDRESS_LIMIT:
        raise HTTPException(
            status_code=409,
            detail={"code": "ADDRESS_LIMIT_EXCEEDED", "message": f"地址已达上限（{ADDRESS_LIMIT} 条），请删除后再添加"},
        )

    # 兜底 geocoding（PRD F-08）
    longitude = data.longitude
    latitude = data.latitude
    if longitude is None or latitude is None:
        full = f"{data.province}{data.city}{data.district}{data.detail}"
        coords = await _amap_geocode(full)
        if coords:
            longitude, latitude = coords

    is_default = data.is_default
    if cnt == 0:
        is_default = True  # 首条强制默认
    if is_default:
        await _clear_other_defaults(db, current_user.id)

    addr = UserAddress(
        user_id=current_user.id,
        consignee_name=data.consignee_name,
        consignee_phone=data.consignee_phone,
        # 同步写旧字段，保证 v1 接口兼容（unified_orders 等下游引用）
        name=data.consignee_name,
        phone=data.consignee_phone,
        street=data.detail,
        province=data.province,
        province_code=data.province_code,
        city=data.city,
        city_code=data.city_code,
        district=data.district,
        district_code=data.district_code,
        detail=data.detail,
        longitude=Decimal(str(longitude)) if longitude is not None else None,
        latitude=Decimal(str(latitude)) if latitude is not None else None,
        tag=data.tag or "",
        is_default=is_default,
        is_deleted=False,
    )
    db.add(addr)
    await db.flush()
    await db.refresh(addr)
    await db.commit()
    return _to_response(addr)


@router.put("/user/addresses/{address_id}")
async def update_address_v2(
    address_id: int,
    data: AddressV2Update,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
    )
    addr = res.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")

    payload = data.model_dump(exclude_unset=True)
    if payload.get("is_default"):
        await _clear_other_defaults(db, current_user.id, exclude_id=address_id)

    for key, value in payload.items():
        if key == "longitude" and value is not None:
            value = Decimal(str(value))
        if key == "latitude" and value is not None:
            value = Decimal(str(value))
        setattr(addr, key, value)
        # 同步旧字段
        if key == "consignee_name":
            addr.name = value
        elif key == "consignee_phone":
            addr.phone = value
        elif key == "detail":
            addr.street = value

    # 兜底 geocoding（若仍为空且省市县/详细地址已齐全）
    if (addr.longitude is None or addr.latitude is None) and addr.province and addr.city and addr.district and addr.detail:
        full = f"{addr.province}{addr.city}{addr.district}{addr.detail}"
        coords = await _amap_geocode(full)
        if coords:
            addr.longitude = Decimal(str(coords[0]))
            addr.latitude = Decimal(str(coords[1]))

    await db.flush()
    await db.refresh(addr)
    await db.commit()
    return _to_response(addr)


@router.delete("/user/addresses/{address_id}")
async def delete_address_v2(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
    )
    addr = res.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")

    addr.is_deleted = True
    addr.is_default = False
    await db.flush()
    await _maybe_promote_new_default(db, current_user.id)
    await db.commit()
    return {"message": "地址已删除"}


@router.patch("/user/addresses/{address_id}/default")
async def set_default_address_v2(
    address_id: int,
    payload: SetDefaultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id,
            UserAddress.is_deleted == False,  # noqa: E712
        )
    )
    addr = res.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")

    if payload.is_default:
        await _clear_other_defaults(db, current_user.id, exclude_id=address_id)
        addr.is_default = True
    else:
        addr.is_default = False
    await db.flush()
    await db.refresh(addr)
    await db.commit()
    return _to_response(addr)


# ─────────── 逆地理编码 / 版本检查 ───────────


@router.post("/regions/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode(
    payload: ReverseGeocodeRequest,
    current_user: User = Depends(get_current_user),
):
    """根据 lng/lat 拆出省/市/县/详细地址（用于小程序 chooseLocation / App 当前位置回填）。"""
    regeo = await _amap_regeo(payload.longitude, payload.latitude)
    if not regeo:
        return ReverseGeocodeResponse()
    addr_comp = (regeo.get("addressComponent") or {}) if isinstance(regeo, dict) else {}
    province = addr_comp.get("province") or ""
    city = addr_comp.get("city") or ""
    district = addr_comp.get("district") or ""
    # 直辖市的 city 字段返回 [] 空数组，需用 province 兜底
    if isinstance(province, list):
        province = ""
    if isinstance(city, list) or not city:
        city = province or ""
    if isinstance(district, list):
        district = ""
    formatted = regeo.get("formatted_address") or ""
    if isinstance(formatted, list):
        formatted = ""
    # 详细地址 = formatted 减去 province/city/district 前缀
    detail_text = formatted
    for prefix in (province, city, district):
        if prefix and detail_text.startswith(prefix):
            detail_text = detail_text[len(prefix):]
    return ReverseGeocodeResponse(
        province=province,
        city=city,
        district=district,
        detail=detail_text,
        formatted_address=formatted,
        provider="amap",
    )


@router.get("/app/version-check", response_model=VersionCheckResponse)
async def version_check(
    platform: str = Query("android", pattern="^(android|ios)$"),
    current_version: str = Query("", alias="currentVersion"),
):
    """老版 App 强制升级检测。本期 v2 已上线，min_version = 2.0.0。"""
    min_version = "2.0.0"
    latest = "2.0.0"
    if platform == "ios":
        download = "https://apps.apple.com/cn/app/bini-health/id000000000"
    else:
        download = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/bini_health_latest.apk"
    force = bool(current_version) and _is_lower_version(current_version, min_version)
    return VersionCheckResponse(
        minVersion=min_version,
        latestVersion=latest,
        forceUpgrade=force,
        downloadUrl=download,
        upgradeMessage="请升级到最新版本以使用完整服务",
    )


def _is_lower_version(a: str, b: str) -> bool:
    """简单语义化版本对比 a < b。非法版本号视为低版本（强制升级）。"""
    def _parts(v: str) -> list[int]:
        try:
            return [int(x) for x in v.split(".")[:3]]
        except Exception:
            return [0, 0, 0]
    pa = _parts(a)
    pb = _parts(b)
    while len(pa) < 3:
        pa.append(0)
    while len(pb) < 3:
        pb.append(0)
    return pa < pb
