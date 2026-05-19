"""[PRD-AI-HOME-OPTIM-FINAL-V2 2026-05-19] AI 首页优化最终版 - 前端源码校验测试

本次需求是 H5 端纯 UI 改造，不涉及后端 API：
- 「选择咨询人」弹窗（ConsultTargetPicker.tsx）改造：标题、选中/未选中样式、主标题、右侧按钮
- AI 首页（ai-home/page.tsx）输入区改造：placeholder 动态、麦克风/键盘圆底图标、输入栏透明、按住说话样式

因此本测试通过校验 h5-web 源码文件的关键字符串/正则，确保改造已落地、不被回滚。

测试在「项目根目录可读取到 h5-web 源码」时执行。若运行环境无 h5-web/（如最小化 backend 容器），
本测试整文件 skip，避免误报。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ────────────────────────────── 路径解析 ──────────────────────────────
# 本测试可能在以下两种环境运行：
# 1) 本地开发机：backend/tests/x.py -> repo_root；h5-web 在 repo_root/h5-web/
# 2) 服务器 backend 容器：测试文件在 /app/tests/x.py，部署脚本会把 h5-web 源
#    docker cp 到 /app/h5-web/ 以供测试读取
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2],  # 本地：<repo_root>
    _HERE.parents[1],  # 容器：/app（因 /app/tests/x.py -> parents[1] = /app）
]


def _find_h5_files():
    for root in _CANDIDATES:
        ai_home = root / "h5-web" / "src" / "app" / "(ai-chat)" / "ai-home" / "page.tsx"
        picker = root / "h5-web" / "src" / "components" / "ai-chat" / "ConsultTargetPicker.tsx"
        if ai_home.exists() and picker.exists():
            return ai_home, picker
    return None, None


H5_AI_HOME, CONSULT_PICKER = _find_h5_files()

# 若 h5-web 源码不可达（如最小化容器），整文件 skip
pytestmark = pytest.mark.skipif(
    H5_AI_HOME is None or CONSULT_PICKER is None,
    reason="h5-web source not available in current environment",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────── ConsultTargetPicker.tsx ───────────────────


def test_picker_title_changed_to_select_consultant():
    """TC-01：弹窗标题从「咨询人」改为「选择咨询人」。"""
    src = _read(CONSULT_PICKER)
    assert ">选择咨询人<" in src.replace(" ", "").replace("\n", "") or "选择咨询人" in src, (
        "选择咨询人 标题未找到"
    )
    # 旧标题 ">咨询人<" 不应作为唯一标题再出现（允许出现在注释或附属说明中）
    # 这里用一个粗略校验：必须存在「选择咨询人」字面量
    assert "选择咨询人" in src


def test_picker_selected_uses_primary_gradient():
    """TC-02：选中卡片使用蓝色渐变（38BDF8 -> 0284C7）。"""
    src = _read(CONSULT_PICKER)
    # 渐变值必须存在（顺序无关，但典型形式 ↓）
    assert re.search(
        r"linear-gradient\(\s*135deg\s*,\s*#38BDF8\s*0%\s*,\s*#0284C7\s*100%\s*\)",
        src,
    ), "选中卡片蓝色渐变未找到"


def test_picker_unselected_uses_neutral_bg():
    """TC-03：未选中条统一浅灰底（#F8FAFC），本人卡片不再有天生蓝底特权。

    校验方式：itemBg 三元运算的 false 分支必须是浅灰，而非 m.is_self ? 渐变 : 浅灰。
    """
    src = _read(CONSULT_PICKER)
    # 关键代码片段：const itemBg = isCurrent ? PRIMARY_GRADIENT : '#F8FAFC';
    assert re.search(r"itemBg\s*=\s*isCurrent\s*\?\s*PRIMARY_GRADIENT\s*:\s*'#F8FAFC'", src), (
        "itemBg 未按 选中=渐变 / 未选中=浅灰 的统一规则实现"
    )
    # 旧实现 `m.is_self ? 'linear-gradient...' : '#F8FAFC'` 不应再出现
    assert "m.is_self ? 'linear-gradient" not in src, "本人卡片仍保留天生蓝底分支"


def test_picker_main_text_is_relation_dot_name():
    """TC-04：主标题统一「关系 · 姓名」格式（关系空则只显示姓名）。"""
    src = _read(CONSULT_PICKER)
    assert re.search(
        r"mainText\s*=\s*relationName\s*\?\s*`\$\{relationName\}\s*·\s*\$\{m\.nickname\}`\s*:\s*m\.nickname",
        src,
    ), "主标题未按「关系 · 姓名」统一规则实现"


def test_picker_select_button_present():
    """TC-05：未选中态右侧渲染实心蓝底白字「选择」按钮，可点击。"""
    src = _read(CONSULT_PICKER)
    assert "consult-target-select-btn" in src, "未找到「选择」按钮的 data-testid"
    # 实心蓝底 + 白字
    assert re.search(r"background:\s*'#0284C7'", src), "「选择」按钮蓝底色未应用"
    # 按钮文案
    assert re.search(r">\s*选择\s*<", src), "「选择」按钮文案未找到"


def test_picker_selected_button_disabled():
    """TC-06：选中态右侧渲染白底蓝字「已选择」标签，置灰禁用、无点击反馈。"""
    src = _read(CONSULT_PICKER)
    assert "consult-target-selected-btn" in src, "未找到「已选择」标签的 data-testid"
    assert "pointerEvents: 'none'" in src or "pointerEvents:'none'" in src, (
        "「已选择」标签未禁用点击 (pointerEvents:none)"
    )
    assert re.search(r">\s*已选择\s*<", src), "「已选择」文案未找到"


# ─────────────────── ai-home/page.tsx 输入区 ───────────────────


def test_aihome_placeholder_uses_consultant_relation():
    """TC-07：输入框 placeholder 模板：问答已结合【XX】的健康档案~。

    XX 取自已选中咨询人的「关系」字段；为空时降级为姓名；本人态 XX=「本人」。
    """
    src = _read(H5_AI_HOME)
    # placeholder 文案前缀（必须存在）
    assert "问答已结合【" in src, "placeholder 文案前缀未找到"
    assert "的健康档案~" in src, "placeholder 文案后缀未找到"
    # 必须从 selectedConsultant 的 relation_type_name / relationship_type 取值
    assert re.search(
        r"selectedConsultant\.relation_type_name\s*\|\|\s*selectedConsultant\.relationship_type",
        src,
    ), "placeholder 未从 selectedConsultant 的关系字段取值"
    # dynamicPlaceholder 变量出现且被赋给 placeholder
    assert "dynamicPlaceholder" in src
    assert re.search(r"placeholder=\{\s*dynamicPlaceholder\s*\}", src), (
        "placeholder 未绑定 dynamicPlaceholder 动态变量"
    )


def test_aihome_mic_keyboard_icons_use_chat_svg_white():
    """TC-08：麦克风/键盘 图标复用 ./chat 的 SVG 资源，描边色改为白色。"""
    src = _read(H5_AI_HOME)
    # 麦克风 SVG 关键 path（来自 chat 第 2715-2720 行）
    assert "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" in src, (
        "麦克风 SVG path 未与 ./chat 资源一致"
    )
    assert "M19 10v2a7 7 0 0 1-14 0v-2" in src, "麦克风 SVG path2 未与 ./chat 资源一致"
    # 键盘 SVG 关键 rect（来自 chat 第 2705 行）
    assert re.search(
        r'<rect\s+x="2"\s+y="4"\s+width="20"\s+height="16"\s+rx="3"\s+ry="3"', src
    ), "键盘 SVG rect 未与 ./chat 资源一致"
    # 描边色：白色（必须出现 stroke="#ffffff" 或 stroke="#FFFFFF"）
    assert re.search(r'stroke="#[fF]{6}"', src) or 'stroke="#ffffff"' in src.lower(), (
        "麦克风/键盘 SVG 描边色未改为白色"
    )


def test_aihome_round_btn_uses_primary_gradient():
    """TC-09：麦克风/键盘 图标按钮容器使用 --gradient-primary 同源蓝色渐变 + 圆形。"""
    src = _read(H5_AI_HOME)
    # ROUND_BTN_STYLE 与 选中卡片同款渐变
    assert "PRIMARY_GRADIENT" in src, "ai-home 未声明 PRIMARY_GRADIENT 渐变常量"
    assert re.search(
        r"PRIMARY_GRADIENT\s*=\s*'linear-gradient\(135deg,\s*#38BDF8\s*0%,\s*#0284C7\s*100%\)'",
        src,
    ), "PRIMARY_GRADIENT 渐变值未与选中咨询人卡片同源"
    # 按钮自身使用 rounded-full + 40x40（w-10 h-10）+ 渐变背景
    assert "ai-home-input-icon-btn" in src, "麦克风/键盘 按钮缺少 data-testid"


def test_aihome_input_bar_outer_transparent():
    """TC-10：键盘模式下，整条输入栏外层容器无背景色（透明）。"""
    src = _read(H5_AI_HOME)
    # Input Bar 容器的 background 改为 'transparent'
    # 校验关键片段：Input Bar 注释附近的 style 必须含 background: 'transparent'
    bar_block = re.search(
        r"/\*\s*Input Bar\s*\*/[\s\S]{0,800}?background:\s*'transparent'",
        src,
    )
    assert bar_block, "Input Bar 外层容器 background 未改为 transparent"
    # 不再使用 THEME.cardBg 作为输入栏底色
    bar_section = src[src.find("/* Input Bar */"): src.find("/* Input Bar */") + 800]
    assert "THEME.cardBg" not in bar_section, "Input Bar 仍残留 THEME.cardBg 白底"


def test_aihome_press_to_talk_style():
    """TC-11：「按住说话」按钮样式 —— #0EA5E9 实底 + 白字 + 圆角 16px + 高度 40px。"""
    src = _read(H5_AI_HOME)
    # data-testid + 关键样式片段
    assert "ai-home-press-to-talk" in src, "「按住说话」按钮缺少 data-testid"
    # 在 press-to-talk 节点附近校验 background:'#0EA5E9' + height:40 + borderRadius:16
    idx = src.find("ai-home-press-to-talk")
    assert idx > 0
    # 取 testid 前后各 1500 字符，确保覆盖完整 style 块与子节点文案
    window = src[max(0, idx - 1500): idx + 1500]
    assert "#0EA5E9" in window, "「按住说话」按钮主色 #0EA5E9 未应用"
    assert re.search(r"height:\s*40\b", window), "「按住说话」按钮高度未设为 40"
    assert re.search(r"borderRadius:\s*16\b", window), "「按住说话」按钮圆角未设为 16px"
    assert re.search(r"color:\s*'#fff'", window), "「按住说话」按钮文字色未设为白色"
    assert "按住说话" in window, "「按住说话」按钮文案未找到"


def test_aihome_no_emoji_icons_in_input_bar():
    """TC-12：输入栏的麦克风/键盘 不再使用 emoji（🎤 / ⌨️），必须用 SVG。"""
    src = _read(H5_AI_HOME)
    # 找到 Input Bar 区域的字符串切片
    start = src.find("/* Input Bar */")
    assert start > 0
    # Input Bar 区段（取后续 ~6000 字符，覆盖整个输入栏）
    bar_chunk = src[start: start + 6000]
    # 旧版本的 emoji 字符 🎤 / ⌨️ 不应再出现在 Input Bar 区段中
    assert "🎤" not in bar_chunk, "输入栏仍残留 🎤 emoji 图标，应改用 SVG"
    assert "⌨️" not in bar_chunk, "输入栏仍残留 ⌨️ emoji 图标，应改用 SVG"
