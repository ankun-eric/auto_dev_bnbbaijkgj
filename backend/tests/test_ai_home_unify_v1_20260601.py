"""[PRD-AIHOME-UNIFY-V1 2026-06-01] AI 首页优化（标准版 / 关怀版三件套统一）- 验收测试

本次 PRD 为纯前端（H5 + 微信小程序，两个版本）UI/交互改造，后端 0 改动：
  需求1：第一行（顶栏）两版统一，照标准版样式：
         ☰(带红点) → 档案/咨询/服务 三 Tab(当前停咨询·蓝下划线) → 🔔(带橙点) → ⊕加号圈
  需求2：右上角「⊕ 加号圈」菜单合并为统一 8 项，两版一致，顺序：
         💬发起新对话 / 🔀切换模式 / 👑会员中心 / 🎁邀请好友 / 📷扫一扫 / 🔤字体大小 / 📤立即分享 / ❓帮助与反馈
  需求3：欢迎区右上角新增「模式切换」胶囊（方案1：胶囊带文字），与 ⊕菜单切换模式并存

测试覆盖：
1) 后端回归：模式偏好接口仍可用（切换逻辑沿用现有实现，不改动业务行为）。
2) 前端源码静态断言（非 UI）：H5 标准版/关怀版、小程序标准版/关怀版四个页面均含三件套关键标记。
"""
from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_STD = os.path.join(_ROOT, "h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx")
H5_CARE = os.path.join(_ROOT, "h5-web", "src", "app", "care-ai-home", "page.tsx")
H5_MOREMENU = os.path.join(_ROOT, "h5-web", "src", "components", "ai-chat", "MoreMenu.tsx")

MP_STD_WXML = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxml")
MP_STD_JS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.js")
MP_STD_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxss")
MP_CARE_WXML = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxml")
MP_CARE_JS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.js")
MP_CARE_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxss")

# ⊕ 菜单统一 8 项
EIGHT_ITEMS = ["发起新对话", "切换模式", "会员中心", "邀请好友", "扫一扫", "字体大小", "立即分享", "帮助与反馈"]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------- 后端回归：模式偏好接口沿用现有逻辑 ----------------


@pytest.mark.asyncio
async def test_mode_preference_api_still_works(client: AsyncClient, auth_headers):
    """切换逻辑沿用现有实现：POST care / standard 仍能正确持久化与读取"""
    r1 = await client.post("/api/user/mode-preference", json={"mode": "care"}, headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["mode"] == "care"

    r2 = await client.get("/api/user/mode-preference", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["mode"] == "care"

    r3 = await client.post("/api/user/mode-preference", json={"mode": "standard"}, headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["mode"] == "standard"


# ---------------- 需求1：顶栏两版统一 ----------------


def test_h5_std_topbar_unified():
    """H5 标准版顶栏：☰红点 / 三 Tab / 🔔铃铛 / ⊕加号圈（testid 为模板字符串，按前缀 + 标签校验）"""
    src = _read(H5_STD)
    assert 'data-testid="ai-home-top-tabs"' in src
    assert "ai-home-top-tab-" in src
    for label in ("档案", "咨询", "服务"):
        assert label in src
    assert 'data-testid="ai-home-topbar-bell"' in src
    assert 'data-testid="ai-home-more-icon-plus-circle"' in src


def test_h5_care_topbar_unified():
    """H5 关怀版顶栏与标准版统一：三 Tab + 铃铛 + ⊕，移除旧顶栏胶囊"""
    src = _read(H5_CARE)
    assert 'data-testid="care-home-top-tabs"' in src
    assert "care-home-top-tab-" in src
    for label in ("档案", "咨询", "服务"):
        assert label in src
    assert 'data-testid="care-home-topbar-bell"' in src
    assert 'data-testid="care-home-more-icon-plus-circle"' in src
    # 旧顶栏「宾尼小康 模式切换」胶囊（带可见文本）已移除
    assert ">宾尼小康 模式切换<" not in src


def test_mp_std_topbar_unified():
    """小程序标准版顶栏：☰红点 / 三 Tab / 🔔铃铛 / ⊕加号圈"""
    wxml = _read(MP_STD_WXML)
    assert 'data-testid="ai-home-top-tabs"' in wxml
    for k in ("profile", "consult", "service"):
        assert f'data-testid="ai-home-top-tab-{k}"' in wxml  # 小程序为静态 testid
    assert 'data-testid="ai-home-topbar-bell"' in wxml
    assert 'data-testid="ai-home-more-icon-plus-circle"' in wxml


def test_mp_care_topbar_unified():
    """小程序关怀版顶栏与标准版统一，且移除旧「宾尼小康 模式切换」胶囊"""
    wxml = _read(MP_CARE_WXML)
    assert 'data-testid="care-home-top-tabs"' in wxml
    for k in ("profile", "consult", "service"):
        assert f'data-testid="care-home-top-tab-{k}"' in wxml
    assert 'data-testid="care-home-topbar-bell"' in wxml
    assert 'data-testid="care-home-more-icon-plus-circle"' in wxml
    # 旧顶栏「宾尼小康 模式切换」胶囊（带可见文本）已移除
    assert ">宾尼小康 模式切换<" not in wxml


def test_mp_topbar_has_tab_handlers():
    """小程序两版顶栏 Tab/铃铛绑定处理函数，且档案/服务有跳转目标"""
    for js in (_read(MP_STD_JS), _read(MP_CARE_JS)):
        assert "onTopTab" in js
        assert "openBell" in js
        assert "/pages/health-profile/index" in js
        assert "/pages/services/index" in js


# ---------------- 需求2：⊕ 菜单合并为统一 8 项 ----------------


def test_h5_moremenu_v2_eight_items():
    """MoreMenu 组件 ai-home-v2 变体含统一 8 项"""
    src = _read(H5_MOREMENU)
    assert "ai-home-v2" in src
    for label in EIGHT_ITEMS:
        assert label in src, f"MoreMenu 缺少菜单项: {label}"


def test_h5_both_use_v2_menu():
    """H5 标准版 / 关怀版均使用 menuVariant='ai-home-v2' 的统一菜单"""
    assert 'menuVariant="ai-home-v2"' in _read(H5_STD)
    assert 'menuVariant="ai-home-v2"' in _read(H5_CARE)


def test_mp_std_menu_eight_items():
    """小程序标准版 ⊕ 菜单含统一 8 项"""
    wxml = _read(MP_STD_WXML)
    for label in EIGHT_ITEMS:
        assert f'data-testid="ai-home-more-menu-item-{label}"' in wxml, f"标准版小程序缺少菜单项: {label}"


def test_mp_care_menu_eight_items():
    """小程序关怀版 ⊕ 菜单含统一 8 项"""
    wxml = _read(MP_CARE_WXML)
    for label in EIGHT_ITEMS:
        assert f'data-testid="care-home-more-menu-item-{label}"' in wxml, f"关怀版小程序缺少菜单项: {label}"


def test_mp_menu_handlers_present():
    """小程序两版菜单项绑定处理函数齐全"""
    for js in (_read(MP_STD_JS), _read(MP_CARE_JS)):
        for fn in ("onTapNewChat", "onTapSwitchMode", "onTapMemberCenter", "onTapInvite",
                   "onTapScan", "onTapFontSize", "onTapShare", "onTapHelpFeedback"):
            assert fn in js, f"小程序缺少菜单处理函数: {fn}"


# ---------------- 需求3：欢迎区右上角模式切换胶囊 ----------------


def test_h5_welcome_mode_capsule():
    """H5 两版欢迎区均含模式切换胶囊 + 下拉面板"""
    for src in (_read(H5_STD), _read(H5_CARE)):
        # 标准版用 ai-home-*，关怀版用 care-home-*，统一检查关键文案与下拉结构
        assert "mode-capsule" in src
        assert "mode-dropdown-panel" in src
        assert "mode-option-standard" in src
        assert "mode-option-care" in src


def test_mp_std_welcome_mode_capsule():
    """小程序标准版欢迎区含模式切换胶囊（标准版 ▾）+ 下拉（当前打勾）"""
    wxml = _read(MP_STD_WXML)
    assert 'data-testid="ai-home-mode-switcher"' in wxml
    assert 'data-testid="ai-home-mode-capsule"' in wxml
    assert 'data-testid="ai-home-mode-dropdown-panel"' in wxml
    assert 'data-testid="ai-home-mode-option-standard"' in wxml
    assert 'data-testid="ai-home-mode-option-care"' in wxml


def test_mp_care_welcome_mode_capsule():
    """小程序关怀版欢迎区含模式切换胶囊（关怀版 ▾）+ 下拉（当前打勾）"""
    wxml = _read(MP_CARE_WXML)
    assert 'data-testid="care-home-mode-switcher"' in wxml
    assert 'data-testid="care-home-mode-capsule"' in wxml
    assert 'data-testid="care-home-mode-dropdown-panel"' in wxml
    assert 'data-testid="care-home-mode-option-standard"' in wxml
    assert 'data-testid="care-home-mode-option-care"' in wxml


def test_mp_switch_logic_reused():
    """小程序切换逻辑沿用：标准版→关怀模式、关怀版→标准模式 + 模式偏好接口"""
    std_js = _read(MP_STD_JS)
    assert "switchToCareMode" in std_js
    assert "/api/user/mode-preference" in std_js
    assert "/pages/care-ai-home/index" in std_js

    care_js = _read(MP_CARE_JS)
    assert "switchToStandard" in care_js
    assert "/pages/ai/index" in care_js


def test_mp_wxss_unified_topbar_styles():
    """小程序两版样式含统一顶栏与胶囊样式"""
    for wxss in (_read(MP_STD_WXSS), _read(MP_CARE_WXSS)):
        assert ".uni-tabs" in wxss
        assert ".uni-plus-circle" in wxss
        assert ".uni-bell" in wxss
        assert ".mode-capsule" in wxss
        assert ".mode-dropdown-panel" in wxss
