"""[PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02] AI 首页输入区优化 - 前端源码校验测试

本次需求为纯前端 UI 优化，不涉及后端 API，覆盖三端（H5 / 小程序 / Flutter）：

事件1（输入框上方提示文字）：
- 文案精简去掉「的」：问答已结合【XX】健康档案
- 字号缩小，独立元素显示在输入框上方，单行不被发送按钮挤断

事件2（按住说话按压效果，5 项）：
- ① 按下变色 + 轻微下沉缩小
- ② 天蓝半透明录音浮层 + 声波动画
- ③ 文字「按住说话」↔「松开发送」
- ④ 按下瞬间震动反馈
- ⑤ 上滑取消

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
MP_CHAT_JS = _find(["miniprogram", "pages", "chat", "index.js"])
MP_CHAT_WXSS = _find(["miniprogram", "pages", "chat", "index.wxss"])
FLUTTER_CHAT = _find(["flutter_app", "lib", "screens", "ai", "chat_screen.dart"])


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────── H5 事件1 ───────────────────────────

@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_hint_text_simplified_no_de():
    """事件1：H5 提示文案精简为「问答已结合【XX】健康档案」（去掉「的」）。"""
    src = _read(H5_AI_HOME)
    assert "问答已结合【" in src
    assert "】健康档案" in src
    assert "】的健康档案" not in src, "H5 提示仍残留「的」字"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_hint_is_independent_element_above_input():
    """事件1：H5 提示由独立元素承载（位于输入框上方），而非 textarea placeholder。"""
    src = _read(H5_AI_HOME)
    assert "ai-home-input-hint" in src, "未找到独立提示元素"
    # textarea 的 placeholder 不再承载「问答已结合…健康档案」长文案
    m = re.search(r"const\s+dynamicPlaceholder\s*=\s*`([^`]*)`", src)
    assert m, "未找到 dynamicPlaceholder 定义"
    assert "健康档案" not in m.group(1), "placeholder 仍承载健康档案长文案，应改由上方独立提示承载"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_hint_font_small_single_line():
    """事件1：H5 提示字号缩小为 11px，单行 nowrap 防止被发送按钮挤断。"""
    src = _read(H5_AI_HOME)
    idx = src.find("ai-home-input-hint")
    window = src[max(0, idx - 200): idx + 600]
    assert re.search(r"fontSize:\s*11\b", window), "提示字号未缩小为 11px"
    assert "nowrap" in window, "提示未单行显示"


# ─────────────────────────── H5 事件2 ───────────────────────────

@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_press_feedback_scale_and_color():
    """事件2-①：H5 按住录音时按钮缩小（scale(0.97)）并变色。"""
    src = _read(H5_AI_HOME)
    idx = src.find("ai-home-press-to-talk")
    window = src[max(0, idx - 2000): idx + 500]
    assert "scale(0.97)" in window, "按住说话按钮缺少按下缩小反馈"
    assert "#0284C7" in window, "按住录音态未变色加深"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_record_overlay_skyblue_and_wave():
    """事件2-②：H5 录音浮层为天蓝半透明 + 声波动画。"""
    src = _read(H5_AI_HOME)
    assert "ai-home-record-overlay" in src, "未找到录音浮层"
    assert "ai-home-record-wave" in src, "未找到声波动画"
    # 天蓝半透明背景（rgba(14,165,233,...)）
    assert re.search(r"rgba\(14,\s*165,\s*233", src), "录音浮层背景非天蓝半透明"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_text_switch_release_to_send():
    """事件2-③：H5 录音中文字切换为「松开发送」。"""
    src = _read(H5_AI_HOME)
    idx = src.find("ai-home-press-to-talk")
    window = src[max(0, idx - 200): idx + 400]
    assert "松开发送" in window, "录音态文字未切换为松开发送"
    assert "按住说话" in window


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_vibration_on_press():
    """事件2-④：H5 按下瞬间震动（navigator.vibrate）。"""
    src = _read(H5_AI_HOME)
    assert re.search(r"navigator\.vibrate\??\.?\(", src), "H5 缺少按下震动反馈"


@pytest.mark.skipif(H5_AI_HOME is None, reason="h5-web source not available")
def test_h5_swipe_up_cancel():
    """事件2-⑤：H5 上滑取消（handleRecordTouchMove + recordCancelled）。"""
    src = _read(H5_AI_HOME)
    assert "handleRecordTouchMove" in src
    assert "recordCancelled" in src


# ─────────────────────────── 小程序 事件2 ───────────────────────────

@pytest.mark.skipif(MP_CHAT_JS is None, reason="miniprogram source not available")
def test_mp_vibration_on_press():
    """事件2-④：小程序按下震动（wx.vibrateShort）。"""
    src = _read(MP_CHAT_JS)
    assert "wx.vibrateShort" in src, "小程序缺少按下震动反馈"


@pytest.mark.skipif(MP_CHAT_WXSS is None, reason="miniprogram source not available")
def test_mp_overlay_skyblue_and_press_scale():
    """事件2-①②：小程序录音浮层天蓝半透明、声波白色、按下缩小。"""
    src = _read(MP_CHAT_WXSS)
    assert re.search(r"rgba\(14,\s*165,\s*233", src), "小程序录音浮层背景非天蓝半透明"
    # 声波白色
    assert re.search(r"\.record-wave-bar\s*\{[^}]*background:\s*#ffffff", src, re.I), "声波未改为白色"
    # 按下缩小
    assert re.search(r"\.hold-talk-active\s*\{[^}]*scale\(0\.97\)", src), "按住按钮缺少缩小反馈"


# ─────────────────────────── Flutter 事件2 ───────────────────────────

@pytest.mark.skipif(FLUTTER_CHAT is None, reason="flutter source not available")
def test_flutter_vibration_on_press():
    """事件2-④：Flutter 按下震动（HapticFeedback）。"""
    src = _read(FLUTTER_CHAT)
    assert "HapticFeedback" in src, "Flutter 缺少按下震动反馈"


@pytest.mark.skipif(FLUTTER_CHAT is None, reason="flutter source not available")
def test_flutter_press_scale_and_text_switch():
    """事件2-①③：Flutter 按住缩小（AnimatedScale 0.97）+ 文字松开发送。"""
    src = _read(FLUTTER_CHAT)
    assert "AnimatedScale" in src, "Flutter 缺少按下缩小反馈"
    assert "松开发送" in src, "Flutter 录音态文字未切换为松开发送"


@pytest.mark.skipif(FLUTTER_CHAT is None, reason="flutter source not available")
def test_flutter_overlay_skyblue():
    """事件2-②：Flutter 录音浮层天蓝半透明背景。"""
    src = _read(FLUTTER_CHAT)
    assert re.search(r"0xFF0EA5E9\)\.withOpacity\(0\.78\)", src), "Flutter 录音浮层背景非天蓝半透明"
