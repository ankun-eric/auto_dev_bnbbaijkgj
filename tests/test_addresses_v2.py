"""[2026-05-05 用户地址改造 PRD v1.0] v2 接口与数据迁移自动化测试。

覆盖：
- v2 schema 校验（手机号、详细地址 ≤80）
- 行政区划 JSON 加载与结构
- 版本检查接口语义化版本对比
- 模型新字段
- _to_response 兼容 v1 老数据
- 迁移脚本核心拆分逻辑
- 测试不强依赖数据库，使用 MagicMock 模拟 db。
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ───────────────── 1. v2 schema 校验 ─────────────────


def test_address_v2_create_schema_valid():
    from app.schemas.addresses_v2 import AddressV2Create
    obj = AddressV2Create(
        consignee_name="张三",
        consignee_phone="13800138000",
        province="北京市",
        city="北京市",
        district="朝阳区",
        detail="建国路 88 号",
        is_default=True,
    )
    assert obj.consignee_name == "张三"
    assert obj.is_default is True


def test_address_v2_create_phone_invalid():
    from app.schemas.addresses_v2 import AddressV2Create
    with pytest.raises(Exception):
        AddressV2Create(
            consignee_name="张三",
            consignee_phone="12345",
            province="北京市",
            city="北京市",
            district="朝阳区",
            detail="x",
        )


def test_address_v2_detail_max_length():
    from app.schemas.addresses_v2 import AddressV2Create
    with pytest.raises(Exception):
        AddressV2Create(
            consignee_name="张三",
            consignee_phone="13800138000",
            province="北京市",
            city="北京市",
            district="朝阳区",
            detail="x" * 81,
        )


def test_address_v2_response_compat_v1():
    """v1 老数据：仅有 name/phone/street，应能自动 fallback 到 consignee_*。"""
    from app.api.addresses_v2 import _to_response

    fake = MagicMock()
    fake.id = 1
    fake.user_id = 100
    fake.consignee_name = None
    fake.consignee_phone = None
    fake.name = "李四"
    fake.phone = "13900000000"
    fake.detail = None
    fake.street = "老地址整段"
    fake.province = ""
    fake.province_code = ""
    fake.city = ""
    fake.city_code = ""
    fake.district = ""
    fake.district_code = ""
    fake.longitude = None
    fake.latitude = None
    fake.tag = None
    fake.is_default = False
    fake.created_at = None
    fake.updated_at = None
    resp = _to_response(fake)
    assert resp.consignee_name == "李四"
    assert resp.consignee_phone == "13900000000"
    assert resp.detail == "老地址整段"
    assert resp.needs_region_completion is True


# ───────────────── 2. 行政区划 JSON ─────────────────


def test_regions_json_exists_and_valid():
    p = BACKEND_ROOT / "app" / "data" / "regions.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "version" in data
    assert "provinces" in data
    assert len(data["provinces"]) == 31, "PRD F-01 要求大陆 31 省"


def test_regions_municipality_three_level():
    """直辖市三级展示（北京市 → 北京市 → 朝阳区）。"""
    p = BACKEND_ROOT / "app" / "data" / "regions.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    bj = next((x for x in data["provinces"] if x["name"] == "北京市"), None)
    assert bj is not None
    assert len(bj["cities"]) >= 1
    assert bj["cities"][0]["name"] == "北京市"
    districts = bj["cities"][0]["districts"]
    assert any(d["name"] == "朝阳区" for d in districts)


def test_regions_includes_all_municipalities():
    p = BACKEND_ROOT / "app" / "data" / "regions.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    names = [p["name"] for p in data["provinces"]]
    for required in ["北京市", "天津市", "上海市", "重庆市"]:
        assert required in names


def test_regions_no_hk_mo_tw():
    """PRD：仅大陆 31 省，不含港澳台。"""
    p = BACKEND_ROOT / "app" / "data" / "regions.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    names = [p["name"] for p in data["provinces"]]
    for forbidden in ["香港", "澳门", "台湾"]:
        assert not any(forbidden in n for n in names)


# ───────────────── 3. 版本检查接口语义化对比 ─────────────────


def test_version_compare_lower():
    from app.api.addresses_v2 import _is_lower_version
    assert _is_lower_version("1.0.0", "2.0.0") is True
    assert _is_lower_version("1.9.99", "2.0.0") is True
    assert _is_lower_version("2.0.0", "2.0.0") is False
    assert _is_lower_version("3.0.0", "2.0.0") is False
    assert _is_lower_version("invalid", "2.0.0") is True


# ───────────────── 4. 模型新字段 ─────────────────


def test_user_address_model_has_v2_fields():
    from app.models.models import UserAddress
    cols = {c.name for c in UserAddress.__table__.columns}
    for required in (
        "consignee_name", "consignee_phone",
        "province_code", "city_code", "district_code",
        "detail", "longitude", "latitude", "tag", "is_deleted",
    ):
        assert required in cols, f"模型缺少字段 {required}"


# ───────────────── 5. 迁移脚本拆分逻辑 ─────────────────


def test_migrate_split_simple():
    from scripts.migrate_addresses_v2 import _try_split, _build_region_index, _load_regions

    regions = _load_regions()
    pmap = _build_region_index(regions)
    hit = _try_split("北京市朝阳区建国路 88 号", pmap)
    assert hit.get("province") == "北京市"
    assert hit.get("city") == "北京市"
    assert hit.get("district") == "朝阳区"


def test_migrate_split_no_match():
    from scripts.migrate_addresses_v2 import _try_split, _build_region_index, _load_regions
    regions = _load_regions()
    pmap = _build_region_index(regions)
    hit = _try_split("纯门牌号 5 号", pmap)
    assert hit == {}


# ───────────────── 6. v2 路由注册检查 ─────────────────


def test_v2_router_registered():
    from app.api.addresses_v2 import router
    paths = {r.path for r in router.routes}
    assert "/api/v2/regions" in paths
    assert "/api/v2/user/addresses" in paths
    assert "/api/v2/user/addresses/{address_id}" in paths
    assert "/api/v2/user/addresses/{address_id}/default" in paths
    assert "/api/v2/regions/reverse-geocode" in paths
    assert "/api/v2/app/version-check" in paths


# ───────────────── 7. 老 v1 接口仍存在（兼容） ─────────────────


def test_v1_api_still_exists():
    """v1 接口为兼容老 App / 老前端，本期保留。"""
    from app.api.addresses import router
    paths = {r.path for r in router.routes}
    assert "/api/addresses" in paths


# ───────────────── 8. AddressV2Update 部分字段更新 ─────────────────


def test_address_v2_update_partial():
    from app.schemas.addresses_v2 import AddressV2Update
    upd = AddressV2Update(tag="家")
    payload = upd.model_dump(exclude_unset=True)
    assert payload == {"tag": "家"}


def test_address_v2_update_phone_validation():
    from app.schemas.addresses_v2 import AddressV2Update
    with pytest.raises(Exception):
        AddressV2Update(consignee_phone="abc")


# ───────────────── 9. ReverseGeocodeRequest 校验 ─────────────────


def test_reverse_geocode_request_valid():
    from app.schemas.addresses_v2 import ReverseGeocodeRequest
    obj = ReverseGeocodeRequest(longitude=116.4775, latitude=39.91)
    assert obj.longitude == 116.4775


def test_reverse_geocode_out_of_range():
    from app.schemas.addresses_v2 import ReverseGeocodeRequest
    with pytest.raises(Exception):
        ReverseGeocodeRequest(longitude=200, latitude=0)


# ───────────────── 10. ADDRESS_LIMIT 常量 ─────────────────


def test_address_limit_is_10():
    from app.api.addresses_v2 import ADDRESS_LIMIT
    assert ADDRESS_LIMIT == 10
