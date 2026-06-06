"""[PRD-TIZHI-OPTIM-V1 2026-06-01] 体质测评优化 — 回归测试。

覆盖 4 个优化点 + 品牌视觉统一：
  优化点1：结果卡片主体质一行完整、兼夹体质换行（H5/小程序/Flutter 源码静态断言）。
  优化点2：详情页「专属膳食套餐 / 门店服务」改为后台可运营配置，按体质匹配；
           无内容则整块隐藏（后端接口行为 + admin CRUD 闭环）。
  优化点3：右上角返回直达 AI 首页，旧列表页弃用（H5/小程序源码静态断言）。
  优化点4：分享标题动态带体质 + 固定封面 + 海报 3 条体质匹配建议（接口字段 + 源码断言）。
  品牌：天蓝主色、无「小白健康」、时长「约 3 分钟完成」。
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.models.models import (
    ConstitutionContentConfig,
    TCMDiagnosis,
    User,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel_path: str) -> str:
    p = os.path.join(REPO_ROOT, rel_path)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


async def _create_diagnosis(db_session, constitution_type: str = "特禀质") -> int:
    user = (await db_session.execute(
        select(User).where(User.phone == "13900000001")
    )).scalar_one()
    d = TCMDiagnosis(
        user_id=user.id,
        constitution_type=constitution_type,
        created_at=datetime.now(),
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    return d.id


# ═══════════════════════════════════════════════════════════════
# 优化点 1：结果卡片主/兼分行（前端源码静态断言）
# ═══════════════════════════════════════════════════════════════


def test_h5_result_card_main_type_no_wrap():
    src = _read("h5-web/src/components/ai-chat/UniversalQuestionnaireResultCard.tsx")
    # 主/兼改为纵向排列（column），主体质 nowrap 一行完整
    assert "qn-card-constitution-rows" in src
    assert "flexDirection: 'column'" in src
    assert "qn-card-main-type" in src
    assert "whiteSpace: 'nowrap'" in src
    assert "qn-card-secondary-type" in src


def test_mp_result_card_main_secondary_separate_rows():
    wxml = _read("miniprogram/components/questionnaire-result-card/index.wxml")
    wxss = _read("miniprogram/components/questionnaire-result-card/index.wxss")
    js = _read("miniprogram/components/questionnaire-result-card/index.js")
    # 改为 qn-main-col 纵向布局
    assert "qn-main-col" in wxml
    assert "qn-main-col" in wxss
    assert "white-space: nowrap" in wxss
    # WXML 不能 .join，改用预处理 secondaryText
    assert "secondaryText" in js
    assert "secondaryText" in wxml


def test_flutter_result_card_main_secondary_column():
    src = _read("flutter_app/lib/widgets/ai_chat/questionnaire_result_card.dart")
    # 主在一行（maxLines:1 + ellipsis），兼在下一行 Column
    assert "maxLines: 1" in src
    assert "主：" in src
    assert "crossAxisAlignment: CrossAxisAlignment.start" in src


# ═══════════════════════════════════════════════════════════════
# 优化点 2：后台运营配置 CRUD + 结果页按体质匹配 / 无内容隐藏
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_content_config_crud(client: AsyncClient, admin_headers, db_session):
    # 清空，确保从干净状态测试匹配
    await db_session.execute(delete(ConstitutionContentConfig))
    await db_session.commit()

    # meta
    meta = await client.get("/api/admin/constitution/meta", headers=admin_headers)
    assert meta.status_code == 200, meta.text
    body = meta.json()
    assert "特禀质" in body["constitution_types"]
    assert {"value": "meal", "label": "专属膳食套餐"} in body["sections"]

    # create meal
    r = await client.post(
        "/api/admin/constitution/content-configs",
        headers=admin_headers,
        json={
            "constitution_type": "特禀质",
            "section": "meal",
            "title": "增强免疫餐",
            "subtitle": "益生菌调和体质",
            "tag": "调和抗敏",
            "tag_color": "#0EA5E9",
            "link_type": "none",
            "button_text": "了解详情",
            "sort_order": 0,
            "enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    cfg_id = r.json()["id"]

    # list filter
    lst = await client.get(
        "/api/admin/constitution/content-configs",
        headers=admin_headers,
        params={"constitution_type": "特禀质", "section": "meal"},
    )
    assert lst.status_code == 200
    assert any(it["id"] == cfg_id for it in lst.json()["items"])

    # update -> disable
    up = await client.put(
        f"/api/admin/constitution/content-configs/{cfg_id}",
        headers=admin_headers,
        json={
            "constitution_type": "特禀质",
            "section": "meal",
            "title": "增强免疫餐（改）",
            "link_type": "none",
            "enabled": False,
        },
    )
    assert up.status_code == 200, up.text
    assert up.json()["enabled"] is False

    # delete
    dele = await client.delete(
        f"/api/admin/constitution/content-configs/{cfg_id}", headers=admin_headers
    )
    assert dele.status_code == 200


@pytest.mark.asyncio
async def test_admin_content_config_validates_type_section(client: AsyncClient, admin_headers):
    bad = await client.post(
        "/api/admin/constitution/content-configs",
        headers=admin_headers,
        json={"constitution_type": "外星质", "section": "meal", "title": "x", "link_type": "none"},
    )
    assert bad.status_code == 422
    bad2 = await client.post(
        "/api/admin/constitution/content-configs",
        headers=admin_headers,
        json={"constitution_type": "特禀质", "section": "xxx", "title": "x", "link_type": "none"},
    )
    assert bad2.status_code == 422


@pytest.mark.asyncio
async def test_result_screen4_5_empty_when_no_config(client: AsyncClient, auth_headers, db_session):
    """无配置时：screen4_packages 为空、screen5_store.services 为空（前端整块隐藏）。"""
    await db_session.execute(delete(ConstitutionContentConfig))
    await db_session.commit()
    did = await _create_diagnosis(db_session, "气虚质")

    res = await client.get(f"/api/constitution/result/{did}", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["screen4_packages"] == []
    assert data["screen5_store"]["services"] == []
    # 不应再有占位假文案字段
    assert "non_guangzhou_fallback_text" not in data["screen5_store"]


@pytest.mark.asyncio
async def test_result_screen4_5_matched_by_constitution(client: AsyncClient, auth_headers, admin_headers, db_session):
    """按体质匹配：为「血瘀质」配置 meal + store，结果页对应展示；其他体质看不到。"""
    await db_session.execute(delete(ConstitutionContentConfig))
    await db_session.commit()

    # 给血瘀质配置
    await client.post(
        "/api/admin/constitution/content-configs", headers=admin_headers,
        json={"constitution_type": "血瘀质", "section": "meal", "title": "活血化瘀餐",
              "tag": "活血通络", "link_type": "product", "link_value": "123",
              "button_text": "立即下单", "enabled": True},
    )
    await client.post(
        "/api/admin/constitution/content-configs", headers=admin_headers,
        json={"constitution_type": "血瘀质", "section": "store", "title": "预约艾灸调理",
              "subtitle": "活血通络", "link_type": "order", "link_value": "moxibustion",
              "button_text": "预约", "enabled": True},
    )

    # 血瘀质 diagnosis -> 命中
    did = await _create_diagnosis(db_session, "血瘀质")
    res = await client.get(f"/api/constitution/result/{did}", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    meals = data["screen4_packages"]
    services = data["screen5_store"]["services"]
    assert len(meals) == 1 and meals[0]["title"] == "活血化瘀餐"
    assert meals[0]["link_type"] == "product" and meals[0]["button_text"] == "立即下单"
    assert len(services) == 1 and services[0]["title"] == "预约艾灸调理"

    # 不同体质（平和质）-> 看不到血瘀质的配置
    did2 = await _create_diagnosis(db_session, "平和质")
    res2 = await client.get(f"/api/constitution/result/{did2}", headers=auth_headers)
    data2 = res2.json()
    assert data2["screen4_packages"] == []
    assert data2["screen5_store"]["services"] == []


@pytest.mark.asyncio
async def test_result_hides_disabled_config(client: AsyncClient, auth_headers, admin_headers, db_session):
    """停用的配置不出现在结果页（整块按是否有启用项隐藏）。"""
    await db_session.execute(delete(ConstitutionContentConfig))
    await db_session.commit()
    await client.post(
        "/api/admin/constitution/content-configs", headers=admin_headers,
        json={"constitution_type": "湿热质", "section": "meal", "title": "清热祛湿餐",
              "link_type": "none", "enabled": False},
    )
    did = await _create_diagnosis(db_session, "湿热质")
    res = await client.get(f"/api/constitution/result/{did}", headers=auth_headers)
    assert res.json()["screen4_packages"] == []


# ═══════════════════════════════════════════════════════════════
# 优化点 3：返回 AI 首页 + 旧列表页弃用（源码静态断言）
# ═══════════════════════════════════════════════════════════════


def test_h5_result_back_to_ai_home():
    src = _read("h5-web/src/app/tcm/result/[id]/page.tsx")
    assert "router.push('/ai-home')" in src
    # 不再返回旧列表页 /tcm
    assert "router.push('/tcm')" not in src


def test_mp_result_back_to_ai_home():
    js = _read("miniprogram/pages/tcm-constitution-result/index.js")
    wxml = _read("miniprogram/pages/tcm-constitution-result/index.wxml")
    assert "goAiHome" in js
    assert "/pages/ai/index" in js
    assert "reLaunch" in js  # 弃用旧列表页返回栈
    assert "navbar-back" in wxml


# ═══════════════════════════════════════════════════════════════
# 优化点 4：分享标题带体质 + 固定封面 + 海报 3 条体质匹配建议
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_share_payload_dynamic_title_and_poster_tips(client: AsyncClient, auth_headers, db_session):
    did = await _create_diagnosis(db_session, "特禀质")
    res = await client.get(f"/api/constitution/result/{did}", headers=auth_headers)
    assert res.status_code == 200, res.text
    share = res.json()["screen6_share"]
    assert "特禀质" in share["share_title"]
    assert "快来测测你是什么体质" in share["share_title"]
    assert share["brand"] == "宾尼小康"
    assert share["cover_image"]
    # 海报 3 条体质匹配建议（非空、非写死占位）
    tips = share["poster_tips"]
    assert isinstance(tips, list) and len(tips) == 3
    assert all(isinstance(t, str) and t for t in tips)


def test_mp_native_share_title_with_constitution():
    js = _read("miniprogram/pages/tcm-constitution-result/index.js")
    assert "onShareAppMessage" in js
    assert "share_title" in js
    assert "open-type=\"share\"" in _read("miniprogram/pages/tcm-constitution-result/index.wxml")


def test_h5_share_to_friend_and_poster():
    src = _read("h5-web/src/app/tcm/result/[id]/page.tsx")
    assert "handleShareToFriend" in src
    assert "tcm-share-friend" in src
    assert "tcm-share-poster" in src
    # 海报采用品牌天蓝 + 宾尼小康 + 引导语
    assert "宾尼小康" in src
    assert "长按识别测测你的体质" in src


# ═══════════════════════════════════════════════════════════════
# 品牌视觉统一
# ═══════════════════════════════════════════════════════════════


def test_brand_no_xiaobai_and_blue_and_duration_text():
    h5 = _read("h5-web/src/app/tcm/page.tsx")
    h5_result = _read("h5-web/src/app/tcm/result/[id]/page.tsx")
    mp_tcm = _read("miniprogram/pages/tcm/index.wxml")
    # 无「小白健康」
    for s in (h5, h5_result, mp_tcm):
        assert "小白健康" not in s
    # 时长文案「约 3 分钟完成」
    assert "约 3 分钟完成" in h5
    assert "约 3 分钟" in mp_tcm
    # 结果页返回与海报使用天蓝主色 #0EA5E9
    assert "#0EA5E9" in h5_result


def test_seed_default_content_covers_9_constitutions():
    """种子默认内容覆盖 9 种体质 × (膳食 + 门店) = 18 条。"""
    from app.services.constitution_content_seed import DEFAULT_MEALS, DEFAULT_STORES, BRAND_BLUE
    assert len(DEFAULT_MEALS) == 9
    assert len(DEFAULT_STORES) == 9
    assert "特禀质" in DEFAULT_MEALS and "血瘀质" in DEFAULT_STORES
    assert BRAND_BLUE == "#0EA5E9"
