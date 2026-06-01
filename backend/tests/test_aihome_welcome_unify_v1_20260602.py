"""[PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] AI 首页欢迎区统一优化 - 验收测试（三端同步）

需求要点：
  1. 标准模式欢迎区改为「关怀模式欢迎区风格」（同结构/版式/字号 28 大问候 + 欢迎语 + 大头像 + 切换胶囊），
     但做瘦身——去掉「今日用药提醒」白卡片。
  2. 两个模式仅靠背景底色区分：
       - 标准模式 = 蓝绿渐变（照搬现关怀色值 #1976D2 → #43A047）
       - 关怀模式 = 暖橙色（新色 #FF8A3D → #FB6E2E）
  3. 范围：H5 + 小程序 + App 三端同步，表现一致。
  4. 首页其它模块（轮播图/功能宫格/推荐问/聊天区/顶栏等）一律不动。

本 PRD 为纯前端三端 UI 改造，后端 0 改动。测试为源码静态断言（非 UI）。
"""
from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_STD = os.path.join(_ROOT, "h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx")
H5_CARE = os.path.join(_ROOT, "h5-web", "src", "app", "care-ai-home", "page.tsx")

MP_STD_WXML = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxml")
MP_STD_JS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.js")
MP_STD_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxss")
MP_CARE_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxss")

APP_STD = os.path.join(_ROOT, "flutter_app", "lib", "screens", "ai", "ai_home_screen.dart")
APP_CARE = os.path.join(_ROOT, "flutter_app", "lib", "screens", "ai", "ai_home_screen_care.dart")

# 色值
BLUE_GREEN_START = "#1976D2"
BLUE_GREEN_END = "#43A047"
WARM_ORANGE_START = "FF8A3D"
WARM_ORANGE_END = "FB6E2E"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------- 后端回归：无业务改动，模式偏好接口仍可用 ----------------


@pytest.mark.asyncio
async def test_mode_preference_api_still_works(client: AsyncClient, auth_headers):
    """欢迎区改造为纯前端，后端模式偏好接口零改动仍正常"""
    r1 = await client.post("/api/user/mode-preference", json={"mode": "care"}, headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["mode"] == "care"

    r2 = await client.post("/api/user/mode-preference", json={"mode": "standard"}, headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["mode"] == "standard"


# ---------------- H5 标准模式：关怀风格 + 蓝绿渐变 + 瘦身 ----------------


def test_h5_std_welcome_blue_green_gradient():
    """H5 标准模式欢迎区背景为蓝绿渐变（照搬现关怀色值）"""
    src = _read(H5_STD)
    assert f"linear-gradient(135deg, {BLUE_GREEN_START} 0%, {BLUE_GREEN_END} 100%)" in src


def test_h5_std_welcome_care_style_structure():
    """H5 标准模式欢迎区照搬关怀风格：大问候 + 欢迎语 + 大头像 + 切换胶囊"""
    src = _read(H5_STD)
    # 欢迎区容器
    assert 'data-testid="ai-home-greeting"' in src
    # 大问候 28 + 欢迎语
    assert 'data-testid="ai-home-welcome-greeting"' in src
    assert 'data-testid="ai-home-welcome-text"' in src
    assert "fontSize: 28" in src
    # 84 大头像（白圈）+ 头像
    assert 'data-testid="ai-home-welcome-avatar-wrap"' in src
    assert 'testId="ai-home-welcome-avatar"' in src
    assert "width: 84" in src
    # 模式胶囊 + 头像同列对齐
    assert 'data-testid="ai-home-mode-logo-column"' in src
    assert 'data-testid="ai-home-mode-capsule"' in src


def test_h5_std_welcome_slimmed_no_med_card():
    """H5 标准模式欢迎区瘦身：不含「今日用药提醒」白卡片"""
    src = _read(H5_STD)
    # 标准模式欢迎区不引入关怀模式的今日提醒卡 testid
    assert 'data-testid="ai-home-med-reminder"' not in src
    assert 'data-testid="care-home-med-reminder"' not in src


# ---------------- H5 关怀模式：暖橙背景，其余不动 ----------------


def test_h5_care_welcome_warm_orange():
    """H5 关怀模式欢迎区背景改为暖橙渐变"""
    src = _read(H5_CARE)
    assert f"linear-gradient(135deg, #{WARM_ORANGE_START} 0%, #{WARM_ORANGE_END} 100%)" in src
    # 关怀模式不再使用旧蓝绿渐变作为欢迎区背景
    assert f"background: 'linear-gradient(135deg, {BLUE_GREEN_START} 0%, {BLUE_GREEN_END} 100%)'" not in src


def test_h5_care_welcome_keeps_med_card():
    """H5 关怀模式保持现状：今日用药提醒卡仍在"""
    src = _read(H5_CARE)
    assert 'data-testid="care-home-med-reminder"' in src
    assert 'data-testid="care-home-welcome"' in src


# ---------------- 小程序标准模式：关怀风格 + 蓝绿渐变 + 瘦身 ----------------


def test_mp_std_welcome_blue_green_gradient():
    """小程序标准模式欢迎区背景为蓝绿渐变"""
    wxss = _read(MP_STD_WXSS)
    assert f"linear-gradient(135deg, {BLUE_GREEN_START} 0%, {BLUE_GREEN_END} 100%)" in wxss


def test_mp_std_welcome_care_style_structure():
    """小程序标准模式欢迎区照搬关怀风格：问候 + 欢迎语 + 机器人 LOGO + 胶囊"""
    wxml = _read(MP_STD_WXML)
    assert 'data-testid="ai-home-welcome-greeting"' in wxml
    assert 'data-testid="ai-home-welcome-text"' in wxml
    assert 'data-testid="ai-home-welcome-avatar"' in wxml
    assert "robot-logo" in wxml
    assert 'data-testid="ai-home-mode-capsule"' in wxml
    # JS 提供问候语 + LOGO 数据
    js = _read(MP_STD_JS)
    assert "greetingText" in js
    assert "logoUrl" in js
    assert "getGreeting" in js


def test_mp_std_welcome_slimmed_no_med_card():
    """小程序标准模式欢迎区瘦身：不含今日用药提醒卡"""
    wxml = _read(MP_STD_WXML)
    assert 'data-testid="ai-home-med-reminder"' not in wxml
    assert "med-reminder" not in wxml


# ---------------- 小程序关怀模式：暖橙背景 ----------------


def test_mp_care_welcome_warm_orange():
    """小程序关怀模式欢迎区背景改为暖橙渐变"""
    wxss = _read(MP_CARE_WXSS)
    assert f"linear-gradient(135deg, #{WARM_ORANGE_START} 0%, #{WARM_ORANGE_END} 100%)" in wxss
    assert f"linear-gradient(135deg, {BLUE_GREEN_START} 0%, {BLUE_GREEN_END} 100%)" not in wxss


# ---------------- App（Flutter）标准模式：蓝绿渐变 + 关怀风格 ----------------


def test_app_std_welcome_blue_green_gradient():
    """App 标准模式欢迎区背景为蓝绿渐变 + 大问候 + 欢迎语"""
    src = _read(APP_STD)
    assert "Color(0xFF1976D2)" in src
    assert "Color(0xFF43A047)" in src
    assert "_greeting()" in src
    assert "我是小康，聊聊健康问题吧~" in src
    # 旧的绿青渐变欢迎卡已不再用于欢迎区主标题块
    assert "小康AI健康顾问" not in src


# ---------------- App（Flutter）关怀模式：暖橙背景 ----------------


def test_app_care_welcome_warm_orange():
    """App 关怀模式欢迎区背景改为暖橙渐变"""
    src = _read(APP_CARE)
    assert "Color(0xFFFF8A3D)" in src
    assert "Color(0xFFFB6E2E)" in src


# ---------------- 三端一致性：标准蓝绿、关怀暖橙 ----------------


def test_three_ends_standard_blue_green_consistent():
    """三端标准模式欢迎区底色一致为蓝绿（#1976D2 / #43A047）"""
    assert BLUE_GREEN_START in _read(H5_STD) and BLUE_GREEN_END in _read(H5_STD)
    assert BLUE_GREEN_START in _read(MP_STD_WXSS) and BLUE_GREEN_END in _read(MP_STD_WXSS)
    assert "0xFF1976D2" in _read(APP_STD) and "0xFF43A047" in _read(APP_STD)


def test_three_ends_care_warm_orange_consistent():
    """三端关怀模式欢迎区底色一致为暖橙（FF8A3D / FB6E2E）"""
    assert WARM_ORANGE_START in _read(H5_CARE) and WARM_ORANGE_END in _read(H5_CARE)
    assert WARM_ORANGE_START in _read(MP_CARE_WXSS) and WARM_ORANGE_END in _read(MP_CARE_WXSS)
    assert "0xFFFF8A3D" in _read(APP_CARE) and "0xFFFB6E2E" in _read(APP_CARE)
