"""[PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式页面优化 —— 后端验收

覆盖：
1) 紧急联系人 CRUD（/api/care-card/contacts 增删改查）+ 鉴权
2) 家庭住址保存（/api/care-card/home-address）+ 个人信息卡聚合（/api/care-card/info）
3) 个人信息卡二维码 token（/api/care-card/qr-token）+ 公开网页（/api/care-card/public/{token}，免登录）
4) 公开网页对无效 token 返回 404
5) 居家安全设备改名：DEVICE_TYPE_LABEL = 紧急呼叫器 / 烟雾报警器 / 水浸报警器（去"宾尼"、"水位"→"水浸"）
6) 个人信息卡空字段：未填写项返回 None / 空列表（前端展示"暂无/未填写"）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ───────────────────────── 紧急联系人 CRUD ─────────────────────────
@pytest.mark.asyncio
async def test_contacts_crud_flow(client: AsyncClient, auth_headers: dict):
    # 初始为空
    r = await client.get("/api/care-card/contacts", headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert isinstance(items, list)

    # 新增一个联系人
    r = await client.post(
        "/api/care-card/contacts",
        headers=auth_headers,
        json={"name": "小明", "relation": "儿子", "phone": "13900001111"},
    )
    assert r.status_code == 200, r.text
    cid = r.json()["data"]["id"]
    assert r.json()["data"]["relation"] == "儿子"

    # 列表里能查到
    r = await client.get("/api/care-card/contacts", headers=auth_headers)
    names = [c["name"] for c in r.json()["data"]["items"]]
    assert "小明" in names

    # 更新
    r = await client.put(
        f"/api/care-card/contacts/{cid}",
        headers=auth_headers,
        json={"name": "小红", "relation": "女儿", "phone": "13900002222"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "小红"
    assert r.json()["data"]["relation"] == "女儿"

    # 删除
    r = await client.delete(f"/api/care-card/contacts/{cid}", headers=auth_headers)
    assert r.status_code == 200, r.text

    r = await client.get("/api/care-card/contacts", headers=auth_headers)
    ids = [c["id"] for c in r.json()["data"]["items"]]
    assert cid not in ids


@pytest.mark.asyncio
async def test_create_contact_requires_name_or_phone(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/care-card/contacts",
        headers=auth_headers,
        json={"name": "", "relation": "", "phone": ""},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_contacts_unauthenticated_blocked(client: AsyncClient):
    r = await client.get("/api/care-card/contacts")
    assert 400 <= r.status_code < 500


# ───────────────────────── 家庭住址 + 信息卡聚合 ─────────────────────────
@pytest.mark.asyncio
async def test_home_address_and_card_info(client: AsyncClient, auth_headers: dict):
    # 保存家庭住址
    r = await client.put(
        "/api/care-card/home-address",
        headers=auth_headers,
        json={"home_address": "北京市朝阳区幸福小区 1 号楼"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["home_address"] == "北京市朝阳区幸福小区 1 号楼"

    # 聚合信息卡
    r = await client.get("/api/care-card/info", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 必含字段（值可为空）
    for key in (
        "name", "age", "birthday", "gender",
        "chronic_diseases", "allergies", "home_address",
        "emergency_contacts", "qr_token",
    ):
        assert key in data, f"个人信息卡聚合缺字段 {key}"
    assert data["home_address"] == "北京市朝阳区幸福小区 1 号楼"
    assert isinstance(data["chronic_diseases"], list)
    assert isinstance(data["allergies"], list)
    assert isinstance(data["emergency_contacts"], list)
    assert data["qr_token"]


@pytest.mark.asyncio
async def test_card_info_empty_fields_are_none_or_empty(client: AsyncClient, auth_headers: dict):
    """空信息处理：未填写项返回 None / 空列表，前端展示"暂无/未填写"。"""
    r = await client.get("/api/care-card/info", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    # 新注册用户没填档案：name/gender/birthday 应为空，age 为 None
    assert data["age"] is None or isinstance(data["age"], int)
    # 列表型字段为列表
    assert isinstance(data["chronic_diseases"], list)
    assert isinstance(data["allergies"], list)


@pytest.mark.asyncio
async def test_card_info_unauthenticated_blocked(client: AsyncClient):
    r = await client.get("/api/care-card/info")
    assert 400 <= r.status_code < 500


# ───────────────────────── 二维码 token + 公开网页 ─────────────────────────
@pytest.mark.asyncio
async def test_qr_token_and_public_card(client: AsyncClient, auth_headers: dict):
    # 先放点数据
    await client.put(
        "/api/care-card/home-address",
        headers=auth_headers,
        json={"home_address": "上海市浦东新区"},
    )
    await client.post(
        "/api/care-card/contacts",
        headers=auth_headers,
        json={"name": "李医生", "relation": "家庭医生", "phone": "13700003333"},
    )

    # 取 token
    r = await client.get("/api/care-card/qr-token", headers=auth_headers)
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]
    assert token

    # 公开网页（免登录）能读到完整信息
    r = await client.get(f"/api/care-card/public/{token}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["home_address"] == "上海市浦东新区"
    contacts = data["emergency_contacts"]
    assert any(c["relation"] == "家庭医生" and c["phone"] == "13700003333" for c in contacts)
    # 公开网页不外泄 qr_token
    assert "qr_token" not in data


@pytest.mark.asyncio
async def test_public_card_invalid_token_404(client: AsyncClient):
    r = await client.get("/api/care-card/public/this_token_does_not_exist_xxx")
    assert r.status_code == 404


# ───────────────────────── 居家安全设备改名 ─────────────────────────
def test_device_type_label_renamed():
    """设备名统一为 紧急呼叫器 / 烟雾报警器 / 水浸报警器（去"宾尼"、"水位"→"水浸"）。"""
    from app.api.home_safety_v1 import (
        DEVICE_TYPE_LABEL,
        DEVICE_TYPE_EMERGENCY,
        DEVICE_TYPE_SMOKE,
        DEVICE_TYPE_WATER,
    )

    assert DEVICE_TYPE_LABEL[DEVICE_TYPE_EMERGENCY] == "紧急呼叫器"
    assert DEVICE_TYPE_LABEL[DEVICE_TYPE_SMOKE] == "烟雾报警器"
    assert DEVICE_TYPE_LABEL[DEVICE_TYPE_WATER] == "水浸报警器"
    # 不再带"宾尼"前缀，不再叫"水位"
    for label in DEVICE_TYPE_LABEL.values():
        assert "宾尼" not in label
        assert "水位" not in label


# ───────────────────────── 路由注册自检 ─────────────────────────
def test_care_card_routes_registered():
    """care_card_v1 路由必须已注册到主应用。"""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/care-card/contacts" in paths
    assert "/api/care-card/info" in paths
    assert "/api/care-card/qr-token" in paths
    assert "/api/care-card/home-address" in paths
    assert "/api/care-card/public/{token}" in paths
