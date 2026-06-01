"""[PRD-MODE-CAPSULE-V1 2026-05-31] AI 首页「模式切换」改造为右上角下拉胶囊 - 验收测试

本次 PRD 为纯前端（H5 + 微信小程序）UI/交互改造，切换业务逻辑沿用既有
/api/user/mode-preference 接口，后端 0 改动。

本测试覆盖两类断言：
1) 后端回归：模式偏好接口仍可用（切换逻辑沿用现有实现，不改动业务行为）。
2) 前端源码静态断言（非 UI）：
   - H5 AI 首页 page.tsx 含新下拉胶囊关键标记，且已移除原「标准模式徽章 + 关怀模式按钮」两个独立控件。
   - 微信小程序 AI 首页 index.wxml/js 含等价的下拉胶囊与 🎁 邀请入口，与 H5 一致。
"""
from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

# 项目根目录（backend/tests/ 向上两级）
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_AI_HOME = os.path.join(_ROOT, "h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx")
MP_AI_WXML = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxml")
MP_AI_JS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.js")
MP_AI_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxss")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------- 后端回归：模式偏好接口沿用现有逻辑 ----------------


@pytest.mark.asyncio
async def test_mode_preference_api_still_works(client: AsyncClient, auth_headers):
    """切换逻辑沿用现有实现：POST care / standard 仍能正确持久化与读取"""
    r1 = await client.post(
        "/api/user/mode-preference", json={"mode": "care"}, headers=auth_headers
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["mode"] == "care"

    r2 = await client.get("/api/user/mode-preference", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["mode"] == "care"

    r3 = await client.post(
        "/api/user/mode-preference", json={"mode": "standard"}, headers=auth_headers
    )
    assert r3.status_code == 200
    assert r3.json()["mode"] == "standard"


# ---------------- H5 源码静态断言 ----------------


def test_h5_has_mode_capsule_markers():
    """H5 AI 首页含下拉胶囊与下拉面板关键标记"""
    src = _read(H5_AI_HOME)
    assert 'data-testid="ai-home-mode-switcher"' in src
    assert 'data-testid="ai-home-mode-capsule"' in src
    # [PRD-AIHOME-UNIFY-V1] 胶囊移入欢迎区后箭头以内联 ▾ 呈现，下拉结构标记齐全即可
    assert 'data-testid="ai-home-mode-dropdown-panel"' in src
    assert 'data-testid="ai-home-mode-option-standard"' in src
    assert 'data-testid="ai-home-mode-option-care"' in src


def test_h5_removed_old_two_separate_controls():
    """H5 已移除原「标准模式徽章 + 关怀模式绿色按钮」两个独立控件"""
    src = _read(H5_AI_HOME)
    # 原独立徽章 / 按钮的 testid 不应再出现
    assert 'data-testid="ai-home-mode-badge-standard"' not in src
    assert 'data-testid="ai-home-care-mode-btn"' not in src
    assert 'data-testid="ai-home-care-mode-switcher"' not in src


def test_h5_keeps_gift_invite_and_more():
    """[PRD-AIHOME-UNIFY-V1 2026-06-01] 顶栏统一后：🎁 邀请并入 ⊕ 菜单，顶栏保留 ⊕ 更多菜单入口"""
    src = _read(H5_AI_HOME)
    # 统一顶栏后 🎁 邀请好友移入 ⊕ 菜单（不再单列于顶栏），邀请跳转仍保留
    assert "/invite" in src
    assert 'data-testid="ai-home-more-btn"' in src


def test_h5_switch_logic_reused():
    """切换关怀模式仍走 saveModePreference + Toast + 跳转 /care-ai-home"""
    src = _read(H5_AI_HOME)
    assert "saveModePreference" in src
    assert "已切换到关怀模式 ✓" in src
    assert "/care-ai-home" in src


# ---------------- 微信小程序源码静态断言（与 H5 一致） ----------------


def test_mp_has_mode_capsule_markers():
    """小程序 AI 首页含等价下拉胶囊与下拉面板"""
    wxml = _read(MP_AI_WXML)
    assert 'data-testid="ai-home-mode-switcher"' in wxml
    assert 'data-testid="ai-home-mode-capsule"' in wxml
    assert 'data-testid="ai-home-mode-capsule-arrow"' in wxml
    assert 'data-testid="ai-home-mode-dropdown-panel"' in wxml
    assert 'data-testid="ai-home-mode-option-standard"' in wxml
    assert 'data-testid="ai-home-mode-option-care"' in wxml


def test_mp_keeps_gift_invite_and_more():
    """[PRD-AIHOME-UNIFY-V1 2026-06-01] 顶栏统一后：🎁 邀请并入 ⊕ 菜单，顶栏保留 ⊕ 更多菜单入口"""
    wxml = _read(MP_AI_WXML)
    # 🎁 邀请好友移入 ⊕ 菜单
    assert "🎁" in wxml
    assert 'data-testid="ai-home-more-menu-item-邀请好友"' in wxml
    assert 'data-testid="ai-home-more-btn"' in wxml


def test_mp_switch_logic():
    """小程序切换关怀模式：保存偏好接口 + Toast + 跳转 /pages/care-ai-home"""
    js = _read(MP_AI_JS)
    assert "switchToCareMode" in js
    assert "toggleModeDropdown" in js
    assert "/api/user/mode-preference" in js
    assert "已切换到关怀模式 ✓" in js
    assert "/pages/care-ai-home/index" in js
    assert "goInvite" in js
    assert "/pages/invite/index" in js


def test_mp_wxss_has_capsule_styles():
    """小程序样式含胶囊与下拉面板样式（箭头翻转 + 高亮）"""
    wxss = _read(MP_AI_WXSS)
    assert ".mode-capsule" in wxss
    assert ".mode-capsule-arrow-up" in wxss
    assert ".mode-dropdown-panel" in wxss
    assert ".mode-dropdown-item-active" in wxss
