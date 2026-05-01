"""[2026-05-01 门店地图能力 PRD v1.0 + 地图配置 PRD v1.0] 地图代理与配置接口。

提供给管理后台/前端使用的地图相关后端代理：
- POST /api/admin/maps/reverse-geocoding  逆地理编码（坐标 → 省/市/区/详细地址）
- GET  /api/admin/maps/poi-search          POI 关键字搜索（关键字 → 候选列表）
- GET  /api/maps/static-map                 获取签名后的高德静态地图 URL（前端 GET 后跳转）
- GET  /api/maps/geo-config                 公开：返回前端可用的地图 JS Key（按端区分）

[2026-05-01 地图配置 PRD v1.0] 新增：
- GET  /api/admin/map-config                获取当前地图配置（含默认值与历史记录）
- PUT  /api/admin/map-config                保存地图配置（即配即生效）
- POST /api/admin/map-config/test           测试连接（逐项检测 Server/Web/H5 三个 Key）
- GET  /api/admin/map-config/test-logs      最近 5 次测试记录

设计要点：
1) Key 读取优先级：数据库 map_config 表 > 环境变量 AMAP_* > 空（前端走 OSM 兜底）
2) 一旦保存过一次配置，全系统优先使用数据库配置（即配即生效，无需重启）
3) Web JS Key / H5 JS Key 必然下发到客户端（这是高德官方设计），通过域名白名单防滥用
4) 单管理员限流 30 次/分钟（简单内存限流，足够日常运维）
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import MapConfig, MapTestLog
from app.schemas.map_config import (
    CopyDomainResponse,
    MapConfigResponse,
    MapConfigUpdate,
    MapTestLogItem,
    MapTestLogsResponse,
    MapTestResponse,
    MapTestSubResult,
)


router = APIRouter(prefix="/api", tags=["地图能力"])

admin_dep = require_role("admin")

ENV_AMAP_SERVER_KEY = os.getenv("AMAP_SERVER_KEY", "").strip()
ENV_AMAP_WEB_JS_KEY = os.getenv("AMAP_WEB_JS_KEY", "").strip()
ENV_AMAP_H5_JS_KEY = os.getenv("AMAP_H5_JS_KEY", "").strip()
ENV_AMAP_SECURITY_CODE = os.getenv("AMAP_SECURITY_JS_CODE", "").strip()


# ──────────── 简单内存限流 ────────────
_RATE_BUCKETS: dict[str, list[float]] = {}


def _check_rate(key: str, limit: int = 30, window: int = 60) -> None:
    now = time.time()
    bucket = _RATE_BUCKETS.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    bucket.append(now)


# ──────────── 配置读取（数据库优先 → 环境变量兜底） ────────────


async def _load_db_config(db: AsyncSession) -> Optional[MapConfig]:
    res = await db.execute(select(MapConfig).order_by(MapConfig.id.asc()).limit(1))
    return res.scalar_one_or_none()


async def get_effective_keys(db: AsyncSession) -> dict[str, Any]:
    """统一的 Key 获取入口：数据库 > 环境变量 > 空。"""
    cfg = await _load_db_config(db)
    if cfg:
        return {
            "server_key": (cfg.server_key or "").strip(),
            "web_js_key": (cfg.web_js_key or "").strip(),
            "h5_js_key": (cfg.h5_js_key or "").strip(),
            "security_js_code": (cfg.security_js_code or "").strip(),
            "default_city": cfg.default_city or "北京",
            "default_center_lng": float(cfg.default_center_lng or 116.397428),
            "default_center_lat": float(cfg.default_center_lat or 39.90923),
            "default_zoom": int(cfg.default_zoom or 12),
            "source": "db",
        }
    return {
        "server_key": ENV_AMAP_SERVER_KEY,
        "web_js_key": ENV_AMAP_WEB_JS_KEY,
        "h5_js_key": ENV_AMAP_H5_JS_KEY,
        "security_js_code": ENV_AMAP_SECURITY_CODE,
        "default_city": "北京",
        "default_center_lng": 116.397428,
        "default_center_lat": 39.90923,
        "default_zoom": 12,
        "source": "env",
    }


# ──────────── Schemas ────────────
class ReverseGeocodingRequest(BaseModel):
    longitude: float = Field(..., description="经度，GCJ-02")
    latitude: float = Field(..., description="纬度，GCJ-02")


class ReverseGeocodingResponse(BaseModel):
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    formatted_address: Optional[str] = None
    ad_code: Optional[str] = None
    provider: str = "amap"


class PoiItem(BaseModel):
    id: Optional[str] = None
    name: str
    address: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    longitude: float
    latitude: float


class PoiSearchResponse(BaseModel):
    items: list[PoiItem]
    provider: str = "amap"


class GeoConfigResponse(BaseModel):
    web_js_key: str = ""
    h5_js_key: str = ""
    has_server_key: bool = False
    provider: str = "amap"
    default_city: str = "北京"
    default_center_lng: float = 116.397428
    default_center_lat: float = 39.90923
    default_zoom: int = 12


# ──────────── 高德 Web 服务（动态读 Key） ────────────
async def _amap_regeo(lng: float, lat: float, server_key: str) -> dict[str, Any] | None:
    if not server_key:
        return None
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": server_key,
        "location": f"{lng:.7f},{lat:.7f}",
        "extensions": "base",
        "output": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if data.get("status") != "1":
                return None
            regeo = data.get("regeocode") or {}
            comp = regeo.get("addressComponent") or {}
            return {
                "province": comp.get("province") or None,
                "city": comp.get("city") or comp.get("province") or None,
                "district": comp.get("district") or None,
                "formatted_address": regeo.get("formatted_address") or None,
                "ad_code": comp.get("adcode") or None,
            }
    except Exception:
        return None


async def _osm_regeo(lng: float, lat: float) -> dict[str, Any] | None:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": f"{lat:.7f}",
        "lon": f"{lng:.7f}",
        "format": "json",
        "accept-language": "zh-CN",
        "zoom": 18,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "bini-health-admin/1.0"}
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            addr = data.get("address") or {}
            province = addr.get("state") or addr.get("region")
            city = addr.get("city") or addr.get("town") or addr.get("county")
            district = addr.get("city_district") or addr.get("suburb") or addr.get("district")
            return {
                "province": province,
                "city": city,
                "district": district,
                "formatted_address": data.get("display_name"),
                "ad_code": None,
            }
    except Exception:
        return None


async def _amap_poi_search(keyword: str, city: Optional[str], server_key: str) -> list[dict[str, Any]] | None:
    if not server_key:
        return None
    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": server_key,
        "keywords": keyword,
        "city": city or "",
        "output": "JSON",
        "offset": 10,
        "page": 1,
        "extensions": "base",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if data.get("status") != "1":
                return None
            items: list[dict[str, Any]] = []
            for poi in data.get("pois") or []:
                loc = (poi.get("location") or "").split(",")
                if len(loc) != 2:
                    continue
                try:
                    lng_v = float(loc[0])
                    lat_v = float(loc[1])
                except ValueError:
                    continue
                items.append({
                    "id": poi.get("id"),
                    "name": poi.get("name") or "",
                    "address": poi.get("address") or "",
                    "province": poi.get("pname") or None,
                    "city": poi.get("cityname") or None,
                    "district": poi.get("adname") or None,
                    "longitude": lng_v,
                    "latitude": lat_v,
                })
            return items
    except Exception:
        return None


async def _osm_poi_search(keyword: str, city: Optional[str]) -> list[dict[str, Any]]:
    q = keyword if not city else f"{keyword},{city}"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "addressdetails": 1,
        "limit": 10,
        "accept-language": "zh-CN",
    }
    headers = {"User-Agent": "bini-health-admin/1.0"}
    items: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(url, params=params)
            data = resp.json() or []
            for r in data:
                try:
                    lat_v = float(r.get("lat"))
                    lng_v = float(r.get("lon"))
                except (TypeError, ValueError):
                    continue
                addr = r.get("address") or {}
                items.append({
                    "id": str(r.get("place_id") or ""),
                    "name": r.get("name") or r.get("display_name", "").split(",")[0],
                    "address": r.get("display_name"),
                    "province": addr.get("state") or addr.get("region"),
                    "city": addr.get("city") or addr.get("town") or addr.get("county"),
                    "district": addr.get("city_district") or addr.get("suburb"),
                    "longitude": lng_v,
                    "latitude": lat_v,
                })
    except Exception:
        pass
    return items


# ──────────── 路由：地图代理 ────────────
@router.post("/admin/maps/reverse-geocoding", response_model=ReverseGeocodingResponse)
async def reverse_geocoding(
    data: ReverseGeocodingRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ReverseGeocodingResponse:
    if data.latitude < -90 or data.latitude > 90:
        raise HTTPException(status_code=400, detail="纬度必须在 -90 到 90 之间")
    if data.longitude < -180 or data.longitude > 180:
        raise HTTPException(status_code=400, detail="经度必须在 -180 到 180 之间")
    _check_rate(f"regeo:{getattr(current_user, 'id', 0)}")

    keys = await get_effective_keys(db)
    res = await _amap_regeo(data.longitude, data.latitude, keys["server_key"])
    provider = "amap"
    if res is None:
        res = await _osm_regeo(data.longitude, data.latitude)
        provider = "osm"
    if res is None:
        raise HTTPException(status_code=502, detail="逆地理编码服务暂不可用，请稍后再试")
    return ReverseGeocodingResponse(**res, provider=provider)


@router.get("/admin/maps/poi-search", response_model=PoiSearchResponse)
async def poi_search(
    keyword: str = Query(..., min_length=1, max_length=50),
    city: Optional[str] = Query(None),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
) -> PoiSearchResponse:
    _check_rate(f"poi:{getattr(current_user, 'id', 0)}")
    keys = await get_effective_keys(db)
    items = await _amap_poi_search(keyword, city, keys["server_key"])
    provider = "amap"
    if items is None:
        items = await _osm_poi_search(keyword, city)
        provider = "osm"
    return PoiSearchResponse(items=[PoiItem(**it) for it in items], provider=provider)


@router.get("/maps/geo-config", response_model=GeoConfigResponse)
async def geo_config(db: AsyncSession = Depends(get_db)) -> GeoConfigResponse:
    """公开接口：前端按需读取 JS Key 与默认地图参数。无 Key 时前端走 OSM 兜底渲染。"""
    keys = await get_effective_keys(db)
    return GeoConfigResponse(
        web_js_key=keys["web_js_key"],
        h5_js_key=keys["h5_js_key"],
        has_server_key=bool(keys["server_key"]),
        provider="amap",
        default_city=keys["default_city"],
        default_center_lng=keys["default_center_lng"],
        default_center_lat=keys["default_center_lat"],
        default_zoom=keys["default_zoom"],
    )


@router.get("/maps/static-map")
async def static_map_url(
    lat: float = Query(...),
    lng: float = Query(...),
    zoom: int = Query(16, ge=3, le=18),
    width: int = Query(200, ge=50, le=1024),
    height: int = Query(150, ge=50, le=1024),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """返回静态地图 URL（带签名）。无高德 Key 时返回 OSM 静态拼接图 URL。"""
    keys = await get_effective_keys(db)
    server_key = keys["server_key"]
    if server_key:
        url = (
            "https://restapi.amap.com/v3/staticmap"
            f"?location={lng:.6f},{lat:.6f}&zoom={zoom}&size={width}*{height}"
            f"&markers=mid,,A:{lng:.6f},{lat:.6f}&key={quote(server_key)}"
        )
        return {"url": url, "provider": "amap"}
    url = (
        f"https://staticmap.openstreetmap.de/staticmap.php"
        f"?center={lat:.6f},{lng:.6f}&zoom={zoom}&size={width}x{height}"
        f"&markers={lat:.6f},{lng:.6f},red-pushpin"
    )
    return {"url": url, "provider": "osm"}


# ──────────── 路由：地图配置（PRD §3） ────────────


def _to_response(cfg: Optional[MapConfig]) -> MapConfigResponse:
    """将 ORM 转响应；若不存在则返回默认值占位（has_record=False）。"""
    if cfg is None:
        # 数据库无记录 → 用环境变量回填只读值，前端可看到当前正在生效的 Key
        return MapConfigResponse(
            id=None,
            provider="amap",
            server_key=ENV_AMAP_SERVER_KEY,
            web_js_key=ENV_AMAP_WEB_JS_KEY,
            h5_js_key=ENV_AMAP_H5_JS_KEY,
            security_js_code=ENV_AMAP_SECURITY_CODE,
            default_city="北京",
            default_center_lng=116.397428,
            default_center_lat=39.90923,
            default_zoom=12,
            has_record=False,
            updated_at=None,
            updated_by=None,
        )
    return MapConfigResponse(
        id=cfg.id,
        provider=cfg.provider or "amap",
        server_key=cfg.server_key or "",
        web_js_key=cfg.web_js_key or "",
        h5_js_key=cfg.h5_js_key or "",
        security_js_code=cfg.security_js_code or "",
        default_city=cfg.default_city or "北京",
        default_center_lng=float(cfg.default_center_lng or 116.397428),
        default_center_lat=float(cfg.default_center_lat or 39.90923),
        default_zoom=int(cfg.default_zoom or 12),
        has_record=True,
        updated_at=cfg.updated_at,
        updated_by=cfg.updated_by,
    )


@router.get("/admin/map-config", response_model=MapConfigResponse)
async def get_map_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MapConfigResponse:
    cfg = await _load_db_config(db)
    return _to_response(cfg)


@router.put("/admin/map-config", response_model=MapConfigResponse)
async def update_map_config(
    payload: MapConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MapConfigResponse:
    # 必填校验：3 个 Key 不能全空（至少 server_key 必须有，否则保存无意义）
    if not (payload.server_key or "").strip():
        raise HTTPException(status_code=400, detail="Server Key 为必填项")
    if not (payload.web_js_key or "").strip():
        raise HTTPException(status_code=400, detail="Web JS Key 为必填项")
    if not (payload.h5_js_key or "").strip():
        raise HTTPException(status_code=400, detail="H5 JS Key 为必填项")

    cfg = await _load_db_config(db)
    if cfg is None:
        cfg = MapConfig()
        db.add(cfg)
    cfg.provider = payload.provider or "amap"
    cfg.server_key = payload.server_key.strip()
    cfg.web_js_key = payload.web_js_key.strip()
    cfg.h5_js_key = payload.h5_js_key.strip()
    cfg.security_js_code = (payload.security_js_code or "").strip()
    cfg.default_city = (payload.default_city or "北京").strip() or "北京"
    cfg.default_center_lng = payload.default_center_lng
    cfg.default_center_lat = payload.default_center_lat
    cfg.default_zoom = payload.default_zoom
    cfg.updated_by = getattr(current_user, "id", None)
    await db.commit()
    await db.refresh(cfg)
    return _to_response(cfg)


# ──────────── 测试连接 ────────────


async def _test_server_key(server_key: str) -> MapTestSubResult:
    """通过调用一次"地理编码"接口验证 Server Key。"""
    if not server_key:
        return MapTestSubResult(status="fail", detail="未配置 Server Key")
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {"key": server_key, "address": "北京天安门", "output": "JSON"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if str(data.get("status")) == "1":
                return MapTestSubResult(status="ok", detail="正常（地理编码）")
            info = data.get("info") or "未知错误"
            infocode = data.get("infocode") or ""
            return MapTestSubResult(
                status="fail",
                detail=f"失败：{info}（错误码 {infocode}）",
            )
    except asyncio.TimeoutError:
        return MapTestSubResult(status="fail", detail="失败：超时")
    except Exception as e:
        return MapTestSubResult(status="fail", detail=f"失败：{type(e).__name__} - {str(e)[:120]}")


async def _test_js_key(js_key: str, key_label: str) -> MapTestSubResult:
    """模拟加载一次 Web/H5 JS API 脚本验证 Key。

    高德官方 maps.js 端点：https://webapi.amap.com/maps?v=2.0&key=xxx
    脚本响应 200 即视为脚本加载成功；高德对无效 Key 也返回 200 但内容为错误信息，
    因此进一步检查响应体是否包含 "INVALID_USER_KEY" 等错误关键字。
    """
    if not js_key:
        return MapTestSubResult(status="fail", detail=f"未配置 {key_label}")
    url = "https://webapi.amap.com/maps"
    params = {"v": "2.0", "key": js_key}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return MapTestSubResult(
                    status="fail",
                    detail=f"失败：HTTP {resp.status_code}",
                )
            text = resp.text or ""
            error_markers = [
                "INVALID_USER_KEY",
                "USER_KEY_PLAT_NOMATCH",
                "USERKEY_PLAT_NOMATCH",
                "INVALID_USER_DOMAIN",
                "INVALID_USER_SCODE",
                "DAILY_QUERY_OVER_LIMIT",
                "SERVICE_NOT_AVAILABLE",
                '"status":"0"',
            ]
            for marker in error_markers:
                if marker in text:
                    return MapTestSubResult(
                        status="fail",
                        detail=f"失败：{marker}",
                    )
            return MapTestSubResult(status="ok", detail="正常（脚本加载）")
    except asyncio.TimeoutError:
        return MapTestSubResult(status="fail", detail="失败：超时")
    except Exception as e:
        return MapTestSubResult(status="fail", detail=f"失败：{type(e).__name__} - {str(e)[:120]}")


@router.post("/admin/map-config/test", response_model=MapTestResponse)
async def test_map_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MapTestResponse:
    """逐项测试当前生效的 3 个 Key。

    使用当前数据库 / 环境变量中 *实际生效* 的 Key 进行测试，
    确保「测试连接」反映的是系统当前真实状态。
    总超时 10 秒按单 Key 控制；并发执行三项测试以加快响应。
    """
    keys = await get_effective_keys(db)
    server_t, web_t, h5_t = await asyncio.gather(
        _test_server_key(keys["server_key"]),
        _test_js_key(keys["web_js_key"], "Web JS Key"),
        _test_js_key(keys["h5_js_key"], "H5 JS Key"),
    )
    overall = (
        server_t.status == "ok"
        and web_t.status == "ok"
        and h5_t.status == "ok"
    )

    op_name = getattr(current_user, "nickname", None) or getattr(current_user, "phone", None) or "管理员"
    log = MapTestLog(
        operator_id=getattr(current_user, "id", None),
        operator_name=op_name,
        server_status=server_t.status,
        server_detail=server_t.detail[:500],
        web_status=web_t.status,
        web_detail=web_t.detail[:500],
        h5_status=h5_t.status,
        h5_detail=h5_t.detail[:500],
        overall_pass=overall,
    )
    db.add(log)
    await db.commit()

    return MapTestResponse(
        server=server_t,
        web=web_t,
        h5=h5_t,
        overall_pass=overall,
        tested_at=datetime.utcnow(),
    )


@router.get("/admin/map-config/test-logs", response_model=MapTestLogsResponse)
async def list_test_logs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(5, ge=1, le=20),
) -> MapTestLogsResponse:
    res = await db.execute(
        select(MapTestLog).order_by(desc(MapTestLog.created_at)).limit(limit)
    )
    rows = res.scalars().all()
    return MapTestLogsResponse(items=[MapTestLogItem.model_validate(r) for r in rows])


@router.get("/admin/map-config/copy-domain", response_model=CopyDomainResponse)
async def copy_domain_helper(request: Request) -> CopyDomainResponse:
    """便捷接口：返回当前管理后台/H5 端的源域名，用于「复制当前域名」按钮。

    - 优先返回 `Origin` 头（浏览器端发起请求时一定带），其次 `Host` 头拼协议。
    - H5 域名通常与管理后台同域不同前缀，仅当部署不同时由前端覆盖。
    """
    headers = request.headers
    origin = headers.get("origin", "").strip()
    if not origin:
        host = headers.get("host", "").strip()
        scheme = headers.get("x-forwarded-proto", "https").strip() or "https"
        if host:
            origin = f"{scheme}://{host}"
    return CopyDomainResponse(
        web_admin_origin=origin,
        h5_origin=origin,
    )
