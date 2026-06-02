"""[BUGFIX-AIHOME-SCROLL-HINT-V1 2026-06-02] AI 标准版首页底部「下拉箭头」缺失修复 验收测试

Bug：AI 标准版首页（小程序 `ai` 页面 + H5 `ai-home` 页面）内容超过一屏未滚到底时，
缺少像关怀模式那样的底部居中向下小箭头提示。

修复（B 方案 + 可点击平滑滚到底，两端一致）：
  - 未滚到底（距底 > 阈值 40）显示底部居中、轻微跳动的向下箭头「⌄」；
  - 滚到最底部自动隐藏；
  - 内容不足一屏（不可滚动）不显示；
  - 点击箭头平滑滚动到内容最底部。
  - 本次不改动关怀模式。

测试为前端源码静态断言（非 UI 自动化）：分别校验 H5 与小程序两端的关键标记。
"""
from __future__ import annotations

import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_STD = os.path.join(_ROOT, "h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx")
MP_AI_JS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.js")
MP_AI_WXML = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxml")
MP_AI_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "ai", "index.wxss")

MARK = "BUGFIX-AIHOME-SCROLL-HINT-V1"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ───────────────────────── H5 标准版 ai-home ─────────────────────────

def test_h5_has_scroll_hint_state_and_threshold():
    src = _read(H5_STD)
    assert "showScrollHint" in src, "H5 应新增 showScrollHint 状态"
    assert "setShowScrollHint" in src
    assert "SCROLL_HINT_THRESHOLD" in src, "应定义距底阈值常量"


def test_h5_scroll_hint_distance_to_bottom_logic():
    src = _read(H5_STD)
    # 实时根据当前滚动位置判断距底距离
    assert "scrollHeight - el.scrollTop - el.clientHeight" in src, "应按距底距离判断显隐"
    # 内容不足一屏（不可滚动）不显示
    assert "scrollHeight - el.clientHeight" in src


def test_h5_listens_scroll_event():
    src = _read(H5_STD)
    assert "addEventListener('scroll'" in src, "应监听滚动容器的 scroll 事件"
    assert "updateScrollHint" in src


def test_h5_click_smooth_scroll_to_bottom():
    src = _read(H5_STD)
    assert "handleScrollToBottom" in src
    # 平滑滚到底
    assert "behavior: 'smooth'" in src
    assert "top: el.scrollHeight" in src


def test_h5_arrow_element_and_bounce_animation():
    src = _read(H5_STD)
    assert 'data-testid="ai-home-scroll-hint"' in src, "应有可点击的箭头按钮"
    assert "ai-home-scroll-hint-arrow" in src
    assert "⌄" in src, "箭头字符为 ⌄"
    assert "aiHomeArrowBounce" in src, "应有跳动动画 keyframes"
    assert "onClick={handleScrollToBottom}" in src, "箭头点击触发滚到底"


def test_h5_marked_with_bugfix_tag():
    assert MARK in _read(H5_STD)


# ───────────────────────── 小程序标准版 ai ─────────────────────────

def test_mp_js_has_scroll_hint_data_and_onpagescroll():
    src = _read(MP_AI_JS)
    assert "showScrollHint" in src, "小程序 data 应含 showScrollHint"
    assert "onPageScroll" in src, "应通过 onPageScroll 监听整页滚动"
    assert "_scrollMaxTop" in src, "应记录最大可滚动距离用于判断是否到底"


def test_mp_js_eval_scroll_hint_uses_selector_query():
    src = _read(MP_AI_JS)
    assert "evalScrollHint" in src
    assert "createSelectorQuery" in src
    assert ".ai-page" in src, "应查询 .ai-page 内容高度"
    assert "selectViewport" in src, "应查询视口高度"


def test_mp_js_hide_when_at_bottom():
    src = _read(MP_AI_JS)
    # 到底时隐藏
    assert "atBottom" in src
    assert "this._scrollMaxTop" in src


def test_mp_js_click_smooth_scroll_to_bottom():
    src = _read(MP_AI_JS)
    assert "onTapScrollHint" in src
    assert "wx.pageScrollTo" in src, "点击应用 pageScrollTo 平滑滚到底"
    assert "duration: 300" in src


def test_mp_wxml_has_arrow_view():
    src = _read(MP_AI_WXML)
    assert 'wx:if="{{showScrollHint}}"' in src, "箭头视图应受 showScrollHint 控制"
    assert 'bindtap="onTapScrollHint"' in src, "箭头应可点击"
    assert 'data-testid="ai-home-scroll-hint"' in src
    assert "scroll-hint-arrow" in src
    assert "⌄" in src


def test_mp_wxss_has_arrow_style_and_animation():
    src = _read(MP_AI_WXSS)
    assert ".scroll-hint" in src
    assert ".scroll-hint-arrow" in src
    assert "ai-arrow-bounce" in src, "应有跳动动画"
    assert "@keyframes ai-arrow-bounce" in src
    # 底部居中
    assert "left: 50%" in src
    assert "transform: translateX(-50%)" in src


def test_mp_marked_with_bugfix_tag():
    assert MARK in _read(MP_AI_JS)
    assert MARK in _read(MP_AI_WXML)
    assert MARK in _read(MP_AI_WXSS)


# ───────────────────────── 不动关怀模式（回归保护） ─────────────────────────

def test_care_mode_untouched_no_bugfix_mark():
    """本次不动关怀模式：关怀页面不应被打上本次 BUGFIX 标记。"""
    care_js = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.js")
    src = _read(care_js)
    assert MARK not in src, "本次不应改动关怀模式小程序代码"
