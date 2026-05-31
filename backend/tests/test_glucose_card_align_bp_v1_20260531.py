"""[PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31] 血糖卡片对齐血压布局 · 源码级结构测试。

本功能为 H5 纯前端布局改动（无后端变更），因此以源码级断言验证 BloodGlucosePage 是否满足
优化方案 v1.0 的验收标准（见需求文档第六节）：

1. 主卡片下方新增并排两个大按钮：手工录入(bg-action-manual) + 绑定设备(bg-action-bind)
2. 去掉导航栏右上角文字「+ 录入」(bg-nav-add 不再存在)
3. 新增"绑定设备"入口，行为对齐血压：提示「即将上线」+ 埋点 health_archive.bg.bind_device.click，不跳转
4. 模块顺序对齐血压：主卡 → 双大按钮 → 目标范围 → 趋势图 → AI本次 → AI趋势 → 历史
5. 完整保留 AI 解读本次(bg-ai-single) / AI 解读趋势(bg-ai-trend)
6. 保留目标范围卡(bg-target-card)、测量类型标签(bg-period-capsule)、趋势三条线、日/周/月三档(BG_RANGE_OPTS)
"""
from __future__ import annotations

import os
import re

import pytest

# backend/tests -> backend -> repo root -> h5-web/src/app/health-metric/[type]/page.tsx
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_PAGE = os.path.join(_ROOT, "h5-web", "src", "app", "health-metric", "[type]", "page.tsx")


def _read_page() -> str:
    with open(_PAGE, "r", encoding="utf-8") as f:
        return f.read()


def _bg_component(src: str) -> str:
    """截取 BloodGlucosePage 函数体（到文件末尾的足量片段）。"""
    idx = src.index("function BloodGlucosePage")
    return src[idx:]


@pytest.fixture(scope="module")
def page_src() -> str:
    assert os.path.exists(_PAGE), f"未找到页面文件: {_PAGE}"
    return _read_page()


@pytest.fixture(scope="module")
def bg_src(page_src: str) -> str:
    return _bg_component(page_src)


# ── 改动 1：主卡片下方并排两个大按钮 ───────────────────────────────
def test_action_row_two_buttons_present(bg_src: str):
    assert 'data-testid="bg-action-row"' in bg_src, "缺少并排按钮容器 bg-action-row"
    assert 'data-testid="bg-action-manual"' in bg_src, "缺少手工录入按钮 bg-action-manual"
    assert 'data-testid="bg-action-bind"' in bg_src, "缺少绑定设备按钮 bg-action-bind"
    assert "手工录入" in bg_src
    assert "绑定设备" in bg_src


def test_manual_button_opens_drawer(bg_src: str):
    m = re.search(r'data-testid="bg-action-manual"[\s\S]{0,200}?setDrawerVisible\(true\)', bg_src)
    assert m, "手工录入按钮未绑定打开录入弹窗（setDrawerVisible(true)）"


# ── 改动 2：去掉导航栏右上角「+ 录入」 ─────────────────────────────
def test_nav_add_removed(page_src: str):
    assert "bg-nav-add" not in page_src, "导航栏右上角「+ 录入」(bg-nav-add) 应被移除"


# ── 改动 3：绑定设备 提示 + 埋点 不跳转 ────────────────────────────
def test_bind_device_handler_toast_and_tracking(bg_src: str):
    assert "handleBindDeviceClick" in bg_src, "缺少绑定设备点击处理函数"
    assert "health_archive.bg.bind_device.click" in bg_src, "缺少绑定设备埋点 key"
    assert "即将上线" in bg_src, "绑定设备应提示「即将上线」"


def test_bind_device_no_navigation(bg_src: str):
    m = re.search(r"const handleBindDeviceClick = useCallback\(\(\) => \{([\s\S]*?)\}, \[\]\);", bg_src)
    assert m, "未找到 handleBindDeviceClick 函数体"
    body = m.group(1)
    assert "router.push" not in body, "绑定设备不应跳转（不得调用 router.push）"


# ── 改动 4：模块顺序对齐血压 ──────────────────────────────────────
def test_module_order_aligned_with_bp(bg_src: str):
    anchors = [
        ("bg-status-card", "主卡片"),
        ("bg-action-row", "并排大按钮"),
        ("bg-target-card", "目标范围卡"),
        ("bg-trend-card", "趋势图"),
        ("bg-ai-single", "AI 解读本次"),
        ("bg-ai-trend", "AI 解读趋势"),
        ("bg-history-all-entry", "历史记录"),
    ]
    positions = []
    for testid, name in anchors:
        token = f'data-testid="{testid}"'
        assert token in bg_src, f"缺少模块 {name}（{testid}）"
        positions.append((bg_src.index(token), name))
    ordered = [name for _, name in sorted(positions)]
    expected = [name for _, name in anchors]
    assert ordered == expected, f"模块顺序不符合预期：实际 {ordered}，期望 {expected}"


# ── 保留项：AI 解读本次/趋势完整保留 ──────────────────────────────
def test_ai_buttons_preserved(bg_src: str):
    assert 'data-testid="bg-ai-single"' in bg_src, "AI 解读本次按钮应保留"
    assert 'data-testid="bg-ai-trend"' in bg_src, "AI 解读趋势按钮应保留"
    assert "requestAi('single')" in bg_src
    assert "requestAi('trend')" in bg_src
    assert "/api/glucose-v1/ai-explain-single" in bg_src
    assert "/api/glucose-v1/ai-explain-trend" in bg_src


# ── 保留项：目标范围 / 测量类型 / 趋势三条线 / 三档 ───────────────
def test_glucose_specific_kept(page_src: str, bg_src: str):
    assert 'data-testid="bg-target-card"' in bg_src, "目标范围参考卡应保留"
    assert 'data-testid="bg-period-capsule"' in bg_src, "测量类型标签应保留"
    assert "空腹" in bg_src and "餐后 2h" in bg_src and "睡前" in bg_src, "趋势三条线图例应保留"
    m = re.search(r"const BG_RANGE_OPTS[^=]*=\s*\[([\s\S]*?)\];", page_src)
    assert m, "未找到 BG_RANGE_OPTS 定义"
    keys = re.findall(r"key:\s*'([^']+)'", m.group(1))
    assert len(keys) == 3, f"血糖趋势档位应为三档（日/周/月），实际 {keys}"


# ── 图标：复用 PencilIcon + 新增血糖仪图标 BgMeterIcon ────────────
def test_icons_present(page_src: str, bg_src: str):
    assert "function BgMeterIcon" in page_src, "应新增血糖仪图标组件 BgMeterIcon"
    assert "<PencilIcon" in bg_src, "手工录入按钮应复用 PencilIcon 图标"
    assert "<BgMeterIcon" in bg_src, "绑定设备按钮应使用 BgMeterIcon 图标"
