"""[BUGFIX-AI-HOME-MENU-MASK + AI-HOME-CARE-BACK V1 2026-06-01]

AI 主页两个问题修复（H5 + 微信小程序两端，后端 0 业务改动）：

问题1：右上角「+圈圈」更多菜单弹出后，点旁边空白处收不回去。
  根因：H5 旧实现用 antd-mobile <Popup position="top">，其遮罩/body 只占顶部一小块，
        未铺满整屏，导致只有点菜单正下方一小块才能关菜单。
  修复：MoreMenu.tsx 改为自绘「全屏 fixed 透明遮罩 + 右上角菜单卡」，
        点遮罩任意空白处即关闭，点菜单卡阻止冒泡。
        （小程序两端 more-menu-mask 本就 top/left/right/bottom:0 全屏，无需改，仅核对。）

问题2：关怀模式点左上角「☰」会自动跳回标准模式（BUG）。
  修复：去掉「☰」，换成向左箭头「←」返回图标；点击退出关怀模式、统一退回标准 AI 主页。
        H5：care-ai-home/page.tsx 左上角按钮改 onClick=handleSwitchToStandard。
        小程序：care-ai-home 改 goBackStandard（存 standard 偏好 + 跳 /pages/ai/index）。

本测试为前端源码静态断言（非 UI 自动化），在服务器后端容器内即可运行。
"""
from __future__ import annotations

import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_MOREMENU = os.path.join(_ROOT, "h5-web", "src", "components", "ai-chat", "MoreMenu.tsx")
H5_CARE = os.path.join(_ROOT, "h5-web", "src", "app", "care-ai-home", "page.tsx")

MP_CARE_WXML = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxml")
MP_CARE_JS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.js")
MP_CARE_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxss")
MP_AI_WXML = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxml")
MP_AI_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxss")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============== 问题1：H5 更多菜单遮罩铺满全屏 ==============


def test_h5_moremenu_no_longer_uses_antd_popup():
    """MoreMenu 不再使用 antd-mobile Popup（其遮罩不铺满，是问题1根因）。"""
    src = _read(H5_MOREMENU)
    assert "from 'antd-mobile'" not in src, "应已移除 antd-mobile Popup 依赖"
    assert "<Popup" not in src and "</Popup>" not in src, "不应再有 Popup 标签"


def test_h5_moremenu_fullscreen_transparent_mask():
    """更多菜单改为自绘全屏透明遮罩：fixed + 100vw/100vh + 四边 0，点空白处即关闭。"""
    src = _read(H5_MOREMENU)
    assert 'data-testid="ai-home-more-menu-mask"' in src, "应有全屏遮罩元素"
    assert "100vw" in src and "100vh" in src, "遮罩应铺满整屏（100vw/100vh）"
    # 遮罩 onClick=onClose；菜单卡阻止冒泡，避免点菜单本身误关
    assert "onClick={onClose}" in src, "点遮罩任意空白处应关闭菜单"
    assert "e.stopPropagation()" in src, "点菜单卡本身不应关闭（阻止冒泡）"
    assert "background: 'transparent'" in src, "遮罩为透明罩子（不变暗）"


def test_h5_moremenu_card_still_rendered_topright():
    """菜单卡片仍渲染在右上角，菜单项 testid 不变（不破坏既有交互）。"""
    src = _read(H5_MOREMENU)
    assert 'data-testid="ai-home-more-menu-card"' in src
    assert "justify-end" in src, "菜单卡靠右上角对齐"
    assert "ai-home-more-menu-item-" in src, "菜单项 testid 模板保留"


# ============== 问题1：小程序遮罩全屏核对（本就全屏，仅守护） ==============


def test_mp_care_more_menu_mask_fullscreen():
    """小程序关怀版更多菜单遮罩本就铺满全屏（top/left/right/bottom:0），核对未被破坏。"""
    wxss = _read(MP_CARE_WXSS)
    assert ".more-menu-mask" in wxss
    block = wxss.split(".more-menu-mask", 1)[1].split("}", 1)[0]
    for prop in ("top: 0", "left: 0", "right: 0", "bottom: 0"):
        assert prop in block, f"小程序关怀版遮罩应含 {prop}（全屏）"


def test_mp_standard_more_menu_mask_fullscreen():
    """小程序标准版（ai）更多菜单遮罩本就铺满全屏，核对未被破坏。"""
    wxss = _read(MP_AI_WXSS)
    assert ".more-menu-mask" in wxss
    block = wxss.split(".more-menu-mask", 1)[1].split("}", 1)[0]
    for prop in ("top: 0", "left: 0", "right: 0", "bottom: 0"):
        assert prop in block, f"小程序标准版遮罩应含 {prop}（全屏）"


# ============== 问题2：H5 关怀模式左上角改返回箭头 ==============


def test_h5_care_back_button_replaces_hamburger():
    """H5 关怀版左上角由 ☰ 改为返回箭头，去掉旧 ☰ 与 openDrawer 跳转。"""
    src = _read(H5_CARE)
    assert 'data-testid="care-home-back-btn"' in src
    assert 'data-testid="care-home-back-icon"' in src
    assert 'data-testid="care-home-hamburger-btn"' not in src, "旧 ☰ 应被移除"
    assert "/ai-home?openDrawer=1" not in src, "返回不再走历史抽屉路径"


def test_h5_care_back_exits_to_standard_home():
    """H5 关怀版返回按钮：退出关怀模式、保存 standard 偏好、跳标准 AI 主页 /ai-home。"""
    src = _read(H5_CARE)
    assert "onClick={handleSwitchToStandard}" in src
    assert "saveModePreference('standard')" in src
    assert "router.push('/ai-home')" in src


# ============== 问题2：小程序关怀模式左上角改返回箭头 ==============


def test_mp_care_back_button_replaces_hamburger():
    """小程序关怀版左上角由 ☰ 改为返回箭头，绑定 goBackStandard，移除旧 openHistory。"""
    wxml = _read(MP_CARE_WXML)
    js = _read(MP_CARE_JS)
    assert 'data-testid="care-home-back-btn"' in wxml
    assert 'catchtap="goBackStandard"' in wxml
    assert "openHistory" not in js, "旧 openHistory 应被移除"
    assert 'catchtap="openHistory"' not in wxml


def test_mp_care_back_exits_to_standard_home():
    """小程序关怀版返回：保存 standard 偏好并跳标准 AI 主页 /pages/ai/index（不带 openDrawer）。"""
    js = _read(MP_CARE_JS)
    assert "goBackStandard" in js
    assert "/pages/ai/index" in js
    assert "'app_mode_preference', 'standard'" in js
    assert "/pages/ai/index?openDrawer=1" not in js, "返回不再走历史抽屉路径"


def test_mp_care_back_icon_style_present():
    """小程序返回箭头样式存在（.uni-back / .uni-back-icon）。"""
    wxss = _read(MP_CARE_WXSS)
    assert ".uni-back" in wxss
    assert ".uni-back-icon" in wxss
