"""[PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式优化（最终定稿）—— 后端验收

覆盖：
1) 需求7：普通用户可用的逆地理编码接口已注册（/api/maps/reverse-geocoding，非 admin）
   - 参数越界校验返回 400
2) 需求8.3：静态位置分享 token 接口
   - POST /api/care-card/share-location 鉴权 + 返回 token
   - GET  /api/care-card/share-location/{token} 免登录返回「静态位置 + 精简信息卡」
   - 无效 token 返回 404
   - 公开数据不外泄 qr_token
3) 路由注册自检：新增端点已挂载到主应用
4) 前端源码静态断言：小程序关怀首页文案/胶囊/悬浮SOS、H5 SOS 页扩散圈/进度环/绿色定位条/坐标转地址、
   联系人维护必填校验、分享静态位置、用药提醒跳转、健康记录本人Tab 数据对齐
"""
from __future__ import annotations

import os
import re

import pytest
from httpx import AsyncClient


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel_path: str) -> str:
    """读取仓库内文件（后端容器内若无前端源码则返回空串，断言自动跳过）。"""
    p = os.path.join(REPO_ROOT, *rel_path.split("/"))
    if not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ───────────────────────── 需求7：逆地理编码（普通用户） ─────────────────────────
@pytest.mark.asyncio
async def test_reverse_geocoding_user_route_registered():
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/maps/reverse-geocoding" in paths


@pytest.mark.asyncio
async def test_reverse_geocoding_user_validates_bounds(client: AsyncClient):
    # 越界纬度 → 400（无需登录即可触发参数校验）
    r = await client.post(
        "/api/maps/reverse-geocoding",
        json={"latitude": 999, "longitude": 116.4},
    )
    assert r.status_code == 400, r.text


# ───────────────────────── 需求8.3：静态位置分享 ─────────────────────────
@pytest.mark.asyncio
async def test_share_location_flow(client: AsyncClient, auth_headers: dict):
    # 先放一些个人信息卡数据，确保分享出去的精简信息卡有内容
    await client.put(
        "/api/care-card/home-address",
        headers=auth_headers,
        json={"home_address": "北京市海淀区中关村大街 1 号"},
    )
    await client.post(
        "/api/care-card/contacts",
        headers=auth_headers,
        json={"name": "小强", "relation": "儿子", "phone": "13800001234"},
    )

    # 生成静态位置分享 token
    r = await client.post(
        "/api/care-card/share-location",
        headers=auth_headers,
        json={"latitude": 39.98, "longitude": 116.31, "address": "北京市海淀区中关村大街 1 号"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]
    assert token

    # 对方免登录读取：静态位置 + 精简信息卡
    r = await client.get(f"/api/care-card/share-location/{token}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["location"]["address"] == "北京市海淀区中关村大街 1 号"
    assert abs(data["location"]["latitude"] - 39.98) < 1e-6
    assert abs(data["location"]["longitude"] - 116.31) < 1e-6
    card = data["card"]
    assert card["home_address"] == "北京市海淀区中关村大街 1 号"
    assert any(c["phone"] == "13800001234" for c in card["emergency_contacts"])
    # 精简信息卡不外泄 qr_token
    assert "qr_token" not in card


@pytest.mark.asyncio
async def test_share_location_requires_auth(client: AsyncClient):
    r = await client.post(
        "/api/care-card/share-location",
        json={"latitude": 39.98, "longitude": 116.31, "address": "x"},
    )
    assert 400 <= r.status_code < 500


@pytest.mark.asyncio
async def test_share_location_invalid_token_404(client: AsyncClient):
    r = await client.get("/api/care-card/share-location/not_exist_token_xyz")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_share_location_routes_registered():
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/care-card/share-location" in paths
    assert "/api/care-card/share-location/{token}" in paths


# ───────────────────────── 前端源码静态断言 ─────────────────────────
def test_mp_care_home_topbar_and_texts():
    """需求1/2/3/6/9：小程序关怀首页 顶栏照搬标准模式 + 文案 + 悬浮SOS。"""
    wxml = _read("miniprogram/pages/care-ai-home/index.wxml")
    js = _read("miniprogram/pages/care-ai-home/index.js")
    if not wxml or not js:
        pytest.skip("后端容器内无小程序源码，跳过")
    # 需求2：胶囊文案「宾尼小康 模式切换」
    assert "宾尼小康 模式切换" in wxml
    # 需求3：欢迎语
    assert "我是宾尼小康，聊聊健康问题吧~" in wxml
    # 需求6：居家安全文案
    assert "居家安全" in js
    assert "紧急呼叫、烟雾报警、水浸报警" in js
    assert "居家安全设备" not in js  # 去掉「设备」
    # 需求1：顶栏照搬标准模式（☰历史 + 🎁 + ⋯更多），去掉报错 ⊕
    assert "history-btn" in wxml
    assert "more-menu-card" in wxml
    assert "plus-circle" not in wxml  # 旧的 ⊕ 圆圈加号已移除
    # 需求9：右下角悬浮 SOS + 扩散光圈
    assert "sos-fab" in wxml
    assert "sos-fab-ripple" in wxml


def test_mp_medication_jump_to_med_page():
    """需求4：用药提醒卡片 → 本人独立用药提醒页（不再跳健康档案锚点）。"""
    js = _read("miniprogram/pages/care-ai-home/index.js")
    med_js = _read("miniprogram/pages/care-medication/index.js")
    if not js or not med_js:
        pytest.skip("后端容器内无小程序源码，跳过")
    assert "/pages/care-medication/index" in js
    # 不再跳健康档案锚点 focus=medication
    assert "focus=medication" not in js
    # 中转页 web-view 指向 H5 用药提醒页
    assert "medication-reminder" in med_js


def test_h5_sos_page_features():
    """需求7/10：H5 SOS 页 坐标转地址 + 扩散圈 + 长按进度环 + 绿色定位条 + 联系人列表。"""
    src = _read("h5-web/src/app/care-ai-home/sos/page.tsx")
    if not src:
        pytest.skip("后端容器内无 H5 源码，跳过")
    # 需求7：坐标 → 地址，走 /api/maps/reverse-geocoding
    assert "/api/maps/reverse-geocoding" in src
    # 需求10.1：扩散光圈
    assert "care-sos-ripple" in src
    # 需求10.2：长按 3 秒进度环
    assert "care-sos-progress-ring" in src
    assert "3000" in src
    # 需求10.3：绿色定位条「定位已就绪」「定位中…」，去掉「±X 米」精度
    assert "定位已就绪" in src
    assert "定位中" in src
    assert "± " not in src and "±" not in src
    # 需求8：必填校验 + 分享静态位置
    assert "请先填写家庭住址" in src
    assert "请填写联系人电话" in src
    assert "share-location" in src


def test_h5_today_health_self_tab_alignment():
    """需求5：健康记录页数据对齐健康档案本人 Tab（family/members → profile/member）。"""
    src = _read("h5-web/src/app/care-ai-home/today-health/page.tsx")
    if not src:
        pytest.skip("后端容器内无 H5 源码，跳过")
    assert "/api/family/members" in src
    assert "/api/health/profile/member/" in src
    assert "today-metrics" in src


def test_h5_share_location_view_page_exists():
    """需求8.3：对方查看页（地图 + 精简信息卡）。"""
    src = _read("h5-web/src/app/care-ai-home/share-location/[token]/page.tsx")
    if not src:
        pytest.skip("后端容器内无 H5 源码，跳过")
    assert "care-share-location-page" in src
    assert "care-info-card" in src  # 复用信息卡风格
    assert "static-map" in src      # 地图
    assert "share-location" in src
