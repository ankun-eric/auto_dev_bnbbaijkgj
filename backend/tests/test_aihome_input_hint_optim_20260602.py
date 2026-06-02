"""[PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02] AI 主页输入区优化 - 前端源码校验测试

本次需求为纯前端 UI 优化，不涉及后端 API，覆盖两端（H5 / 小程序）：

需求1（把「问答已结合健康档案」挪进输入框做占位文字）：
- 删除输入框上方独立的小灰字「问答已结合【XX】健康档案」
- 改为输入框内的灰色占位提示文字（placeholder），替换原「发消息或按住说话…」
- 咨询人名字规则不变（本人 / 家人姓名）

需求2（占位文字过长的处理，姓名截断 + 省略号）：
- 当咨询人姓名较长时只取前几个字，超出部分用省略号，保证「健康档案」可见

需求3（语音浮层文案修改）：
- 按住说话弹出的语音浮层文案改为「语音输入中…」

测试通过校验各端源码文件的关键字符串/正则，确保改造已落地、不被回滚。
若运行环境无对应端源码（如最小化 backend 容器），对应用例 skip，避免误报。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2],  # 本地：<repo_root>
    _HERE.parents[1],  # 容器：/app
]


def _find(rel_parts):
    for root in _CANDIDATES:
        p = root.joinpath(*rel_parts)
        if p.exists():
            return p
    return None


H5_AI_HOME = _find(["h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx"])
MP_CHAT_WXML = _find(["miniprogram", "pages", "chat", "index.wxml"])
MP_CHAT_JS = _find(["miniprogram", "pages", "chat", "index.js"])
MP_CHAT_WXSS = _find(["miniprogram", "pages", "chat", "index.wxss"])


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────── H5 需求1：占位文字 ───────────────────────────

@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_placeholder_carries_health_archive():
    """需求1：H5 输入框 placeholder 承载「问答已结合【XX】健康档案」。"""
    src = _read(H5_AI_HOME)
    m = re.search(r"const\s+dynamicPlaceholder\s*=\s*`([^`]*)`", src)
    assert m, "未找到 dynamicPlaceholder 定义"
    ph = m.group(1)
    assert "问答已结合【" in ph, "placeholder 未承载「问答已结合【XX】」"
    assert "】健康档案" in ph, "placeholder 未承载「健康档案」"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_independent_hint_removed():
    """需求1：H5 删除输入框上方独立灰字提示元素（ai-home-input-hint 不再渲染）。"""
    src = _read(H5_AI_HOME)
    assert "data-testid=\"ai-home-input-hint\"" not in src, "输入框上方独立提示元素未删除"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_old_short_placeholder_removed():
    """需求1：H5 原通用短提示「发消息或按住说话…」不再作为 placeholder 文案。"""
    src = _read(H5_AI_HOME)
    m = re.search(r"const\s+dynamicPlaceholder\s*=\s*`([^`]*)`", src)
    assert m, "未找到 dynamicPlaceholder 定义"
    assert "发消息或按住说话" not in m.group(1), "placeholder 仍为旧短提示文案"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_name_truncation_with_ellipsis():
    """需求2：H5 占位文字姓名过长时截断 + 省略号。"""
    src = _read(H5_AI_HOME)
    # 存在基于长度的截断逻辑（slice + 省略号）
    assert re.search(r"\.slice\(0,\s*MAX_NAME_LEN\)", src), "未找到姓名截断逻辑"
    assert "…" in src, "未找到省略号"


# ─────────────────────────── H5 需求3：语音浮层文案 ───────────────────────────

@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_voice_overlay_text_updated():
    """需求3：H5 语音浮层文案改为「语音输入中…」，不再用「正在录音…」。"""
    src = _read(H5_AI_HOME)
    assert "语音输入中…" in src, "H5 语音浮层未改为「语音输入中…」"
    assert "正在录音" not in src, "H5 仍残留「正在录音」文案"


# ─────────────────────────── 小程序 需求1+2：占位文字 ───────────────────────────

@pytest.mark.skipif(MP_CHAT_WXML is None, reason="miniprogram source not available")
def test_mp_placeholder_carries_health_archive():
    """需求1：小程序输入框 placeholder 承载「问答已结合【XX】健康档案」。"""
    src = _read(MP_CHAT_WXML)
    assert "问答已结合【" in src, "小程序未承载「问答已结合【XX】」"
    assert "】健康档案" in src, "小程序未承载「健康档案」"
    # placeholder 由 WXS 拼接（不再是「发信息...」硬编码）
    assert "buildPlaceholder" in src, "小程序 placeholder 未改为 WXS 拼接"
    assert 'placeholder="发信息..."' not in src, "小程序仍为旧 placeholder「发信息...」"


@pytest.mark.skipif(MP_CHAT_WXML is None, reason="miniprogram source not available")
def test_mp_name_truncation_with_ellipsis():
    """需求2：小程序占位文字姓名过长时截断 + 省略号（WXS substring + …）。"""
    src = _read(MP_CHAT_WXML)
    assert re.search(r"substring\(0,\s*MAX\)", src), "小程序未找到姓名截断逻辑"
    assert "+ '…'" in src or "+'…'" in src, "小程序未找到省略号拼接"


# ─────────────────────────── 小程序 需求3：语音浮层文案 ───────────────────────────

@pytest.mark.skipif(MP_CHAT_WXML is None, reason="miniprogram source not available")
def test_mp_voice_overlay_text_updated():
    """需求3：小程序语音浮层文案为「语音输入中…」。"""
    src = _read(MP_CHAT_WXML)
    assert "语音输入中…" in src, "小程序语音浮层未含「语音输入中…」"


@pytest.mark.skipif(MP_CHAT_WXSS is None, reason="miniprogram source not available")
def test_mp_voice_overlay_title_style_exists():
    """需求3：小程序语音浮层标题样式 .record-title 存在。"""
    src = _read(MP_CHAT_WXSS)
    assert ".record-title" in src, "小程序未定义语音浮层标题样式"


# ─────────────────────────── 不回归：保留既有按压/声波体验 ───────────────────────────

@pytest.mark.skipif(MP_CHAT_WXSS is None, reason="miniprogram source not available")
def test_mp_overlay_skyblue_and_press_scale_kept():
    """不回归：小程序录音浮层天蓝半透明、声波白色、按下缩小保持不变。"""
    src = _read(MP_CHAT_WXSS)
    assert re.search(r"rgba\(14,\s*165,\s*233", src), "小程序录音浮层背景非天蓝半透明"
    assert re.search(r"\.record-wave-bar\s*\{[^}]*background:\s*#ffffff", src, re.I), "声波未保持白色"
    assert re.search(r"\.hold-talk-active\s*\{[^}]*scale\(0\.97\)", src), "按住按钮缺少缩小反馈"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_press_to_talk_kept():
    """不回归：H5「按住说话」↔「松开发送」交互保持不变。"""
    src = _read(H5_AI_HOME)
    assert "按住说话" in src and "松开发送" in src, "H5 按住说话交互被破坏"
