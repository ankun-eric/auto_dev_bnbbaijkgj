"""[PRD-METRIC-HISTORY-ROW-NOACTION-V1 2026-06-02] 健康指标全部历史页「点整行弹菜单」去特殊处理 测试。

本次为纯 H5 端交互调整（小程序指标历史页为 web-view 空壳，直接加载同一 H5 页面，自动继承两端一致）：

需求 —— 去除「点整行弹菜单」特殊处理：
  - 手工录入记录（editable）：点整行不再弹出「修改 / 删除」操作面板，操作入口统一收敛到右侧「⋯」三点按钮。
  - 设备同步记录（只读，!editable）：点整行仍弹只读详情查看，保持原样不动。
  - 右侧「⋯」三点按钮的修改/删除入口、删除二次确认弹窗，全部保留不变。

涉及指标：H5 历史记录页为 血糖 / 血压 / 心率 / 血氧 通用一个页面，故四指标的「点整行弹菜单」统一被去掉。

测试为前端源码静态断言（点整行行为 / 三点入口保留 / 删除确认保留 / 设备同步只读保留 / 小程序 web-view 空壳）。
"""
from __future__ import annotations

import os
import re


def _read_source(*rel_parts):
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "src", "app", *rel_parts),
        os.path.join("/app", "h5-web", "src", "app", *rel_parts),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


def _history_source():
    return _read_source("health-metric", "[type]", "history", "page.tsx")


def _mp_health_metric_wxml():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "miniprogram",
                     "pages", "health-metric", "index.wxml"),
        "/app/miniprogram/pages/health-metric/index.wxml",
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


# ──────────────── 核心需求：点整行不再弹操作面板 ────────────────

def _extract_on_click_row_block(src: str) -> str:
    """提取 列表项渲染中 onClickRow={() => { ... }} 的函数体。"""
    idx = src.find("onClickRow={")
    assert idx != -1, "未找到 onClickRow 绑定"
    # 从 onClickRow={ 之后开始按花括号配平截取箭头函数体
    start = src.find("{", idx + len("onClickRow="))
    assert start != -1
    depth = 0
    i = start
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise AssertionError("onClickRow 函数体花括号不配平")


def test_click_row_does_not_open_action_sheet_for_editable():
    """点整行的处理函数中：手工录入（editable）记录不再调用 setActionItem（即不弹操作面板）。"""
    src = _history_source()
    assert src is not None, "未找到全部历史页源码"
    block = _extract_on_click_row_block(src)
    # onClickRow 内绝不能再出现 setActionItem（旧逻辑：editable 时 setActionItem(item)）
    assert "setActionItem" not in block, \
        "点整行处理逻辑中不应再调用 setActionItem（手工录入记录点整行应无特殊弹菜单）"


def test_click_row_keeps_readonly_for_device_records():
    """点整行的处理函数中：仅对设备同步（!item.editable）记录弹只读详情，保持原样。"""
    src = _history_source()
    assert src is not None
    block = _extract_on_click_row_block(src)
    assert "!item.editable" in block, "点整行逻辑应仅在非可编辑（设备同步）记录时处理"
    assert "setReadOnlyItem" in block, "设备同步记录点整行应仍弹只读详情（setReadOnlyItem）"


def test_click_row_no_editable_branch_opening_panel():
    """确保旧的「if (item.editable) { setActionItem(item) }」分支已被移除。"""
    src = _history_source()
    assert src is not None
    block = _extract_on_click_row_block(src)
    # 去空白后不应再存在 editable 为真即打开面板的写法
    flat = re.sub(r"\s+", "", block)
    assert "if(item.editable){setActionItem" not in flat
    assert "item.editable?setActionItem" not in flat


# ──────────────── 右侧「⋯」三点入口仍是唯一操作入口（保留） ────────────────

def test_more_button_still_opens_action_sheet():
    """右侧「⋯」三点按钮仍通过 onClickMore → setActionItem 打开操作面板。"""
    src = _history_source()
    assert src is not None
    assert "metric-row-more-" in src, "应保留右侧「⋯」三点入口"
    assert "⋯" in src
    # onClickMore 绑定到 setActionItem（操作入口仍在这里）
    assert "onClickMore={() => setActionItem(item)}" in src, \
        "「⋯」按钮应仍是打开操作面板（setActionItem）的入口"


def test_more_button_stop_propagation():
    """「⋯」按钮点击 stopPropagation，避免冒泡触发整行点击。"""
    src = _history_source()
    assert src is not None
    assert "e.stopPropagation()" in src and "onClickMore()" in src


def test_action_sheet_edit_delete_retained():
    """操作面板（修改 / 删除）整套保留不变。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-history-action-sheet"' in src
    assert 'data-testid="metric-history-action-edit"' in src
    assert 'data-testid="metric-history-action-delete"' in src


def test_delete_confirm_retained():
    """删除前二次确认弹窗保留不变。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-delete-confirm"' in src
    assert 'data-testid="metric-delete-confirm-btn"' in src
    assert "无法恢复" in src


def test_readonly_popup_retained():
    """设备同步记录的只读详情弹窗保留不变。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-readonly-popup"' in src
    assert "数据已锁定" in src or "重新测量" in src


# ──────────────── 行样式：手工录入去掉手型指针，设备同步保留 ────────────────

def test_row_cursor_conditional_on_editable():
    """整行 cursor 改为按 editable 区分：手工录入 default（无手型），设备同步 pointer。"""
    src = _history_source()
    assert src is not None
    flat = re.sub(r"\s+", "", src)
    assert "cursor:item.editable?'default':'pointer'" in flat, \
        "整行 cursor 应为 item.editable ? 'default' : 'pointer'"


# ──────────────── 任务标识与四指标通用范围 ────────────────

def test_prd_marker_present():
    """源码中应带本次任务标识注释，便于追溯。"""
    src = _history_source()
    assert src is not None
    assert "PRD-METRIC-HISTORY-ROW-NOACTION-V1" in src


def test_page_is_shared_across_four_metrics():
    """历史页为四指标通用一页（blood_pressure / blood_glucose / heart_rate / spo2）。"""
    src = _history_source()
    assert src is not None
    for t in ("blood_pressure", "blood_glucose", "heart_rate", "spo2"):
        assert t in src, f"历史页应通用覆盖指标 {t}"


# ──────────────── 小程序：web-view 空壳，加载 H5，两端一致 ────────────────

def test_mp_health_metric_is_webview_shell():
    """小程序指标历史页 = web-view 加载 H5，改 H5 一处即两端一致。"""
    src = _mp_health_metric_wxml()
    assert src is not None, "未找到小程序 health-metric 页"
    assert "<web-view" in src and "webUrl" in src
