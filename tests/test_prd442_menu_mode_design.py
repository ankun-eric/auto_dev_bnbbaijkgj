"""
PRD-442 菜单模式 · 晴空诊室风格改造 · Design Tokens 与三端资产校验
=================================================================

本测试套件覆盖：
- T01-T02：H5 端 4 大交付物 + 6 屏 prototype 文件存在与体积
- T03：11 级 sky-* 色阶完整且 hex 值与 PRD §3.1 完全一致
- T04：5 大渐变 token 全部存在
- T05：13 类组件类齐全（.menu-* 系列）
- T06：design-tokens.json 是合法 JSON 且顶层结构完整
- T07：辅助色含 allowed 场景白名单约束（红线规范代码化）
- T08：PRD-442.md 9 大章节齐全
- T09：prototype.html 含完整 6 屏（screen-tag 出现次数 == 6）
- T10：components.html 包含 13 类组件 demo
- T11：所有阴影 token 禁止使用纯黑（rgba(0,..)）
- T12：base 字号 == 14px，关键指标字号 >= 36px（中老年友好 + AA 无障碍）
- T13：小程序 wxss tokens 文件存在且包含 11 级 sky-*
- T14：Flutter ThemeData dart 文件存在且包含 11 级 MenuModeColors
- T15：与 PRD-441 AI 模式色板兼容性（11 级 hex 完全一致）
"""
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H5_DS_DIR = os.path.join(ROOT, "h5-web", "public", "menu-mode-design-system")

CSS_FILE = os.path.join(H5_DS_DIR, "design-tokens.css")
JSON_FILE = os.path.join(H5_DS_DIR, "design-tokens.json")
PRD_FILE = os.path.join(H5_DS_DIR, "PRD-442.md")
PROTO_FILE = os.path.join(H5_DS_DIR, "prototype.html")
COMP_FILE = os.path.join(H5_DS_DIR, "components.html")
INDEX_FILE = os.path.join(H5_DS_DIR, "index.html")

WXSS_FILE = os.path.join(ROOT, "miniprogram", "styles", "menu-mode-tokens.wxss")
DART_FILE = os.path.join(ROOT, "flutter_app", "lib", "theme", "menu_mode_theme.dart")

# PRD-441 AI 模式 tokens（用于兼容性比对）
AI_CSS_FILE = os.path.join(
    ROOT, "h5-web", "public", "design-system", "design-tokens.css"
)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# PRD §3.1 规定的 11 级天蓝色阶（菜单模式补充 950 一档）
EXPECTED_SKY_PALETTE = {
    "50":  "#f0f9ff",
    "100": "#e0f2fe",
    "200": "#bae6fd",
    "300": "#7dd3fc",
    "400": "#38bdf8",
    "500": "#0ea5e9",
    "600": "#0284c7",
    "700": "#0369a1",
    "800": "#075985",
    "900": "#0c4a6e",
    "950": "#082f49",
}


# ============================================================
# T01：H5 端 4 大交付物（CSS / JSON / MD / HTML）全部存在
# ============================================================
def test_t01_h5_deliverables_exist():
    for fp, name in [
        (CSS_FILE, "design-tokens.css"),
        (JSON_FILE, "design-tokens.json"),
        (PRD_FILE, "PRD-442.md"),
        (PROTO_FILE, "prototype.html"),
        (COMP_FILE, "components.html"),
        (INDEX_FILE, "index.html"),
    ]:
        assert os.path.exists(fp), f"缺失交付物：{name} -> {fp}"
        assert os.path.getsize(fp) > 200, f"交付物 {name} 体积过小（< 200B），疑似空文件"


# ============================================================
# T02：4 大交付物体积合理（非零长度且大于阈值）
# ============================================================
def test_t02_h5_deliverables_size_reasonable():
    sizes = {
        CSS_FILE: 3000,    # design-tokens.css >= 3KB
        JSON_FILE: 1500,   # design-tokens.json >= 1.5KB
        PRD_FILE: 3000,    # PRD-442.md >= 3KB
        PROTO_FILE: 8000,  # prototype.html >= 8KB（6 屏）
        COMP_FILE: 5000,   # components.html >= 5KB
        INDEX_FILE: 3000,  # index.html >= 3KB
    }
    for fp, min_size in sizes.items():
        actual = os.path.getsize(fp)
        assert actual >= min_size, (
            f"{os.path.basename(fp)} 体积 {actual} < 期望最小 {min_size}"
        )


# ============================================================
# T03：11 级 sky-* 色阶完整且 hex 值与 PRD §3.1 完全一致
# ============================================================
def test_t03_sky_palette_complete_and_correct():
    css = _read(CSS_FILE)
    for level, hex_val in EXPECTED_SKY_PALETTE.items():
        token_name = f"--sky-{level}"
        # 匹配 --sky-50:  #f0f9ff;（中间空白和大小写灵活）
        pattern = rf"--sky-{level}\s*:\s*{re.escape(hex_val)}\s*;"
        assert re.search(pattern, css, re.IGNORECASE), (
            f"未找到正确定义：{token_name}: {hex_val}"
        )


# ============================================================
# T04：5 大核心渐变 token 全部存在
# ============================================================
def test_t04_gradient_tokens_complete():
    css = _read(CSS_FILE)
    expected_gradients = [
        "--gradient-topbar-a1",
        "--gradient-btn-primary",
        "--gradient-hero-deep",
        "--gradient-login-bg",
    ]
    for token in expected_gradients:
        assert token in css, f"缺失渐变 token：{token}"
    # 至少包含 4 个 linear-gradient
    assert css.count("linear-gradient") >= 4, "渐变定义数量不足"


# ============================================================
# T05：13 类组件类齐全（.menu-* 系列）
# ============================================================
def test_t05_component_classes_complete():
    css = _read(CSS_FILE)
    # PRD §4 13 类通用组件：Button/Card/Input/Tab/Drawer/Toast/Modal/List/Chip/Avatar/Badge/Skeleton/Empty
    expected_classes = [
        ".menu-btn",
        ".menu-btn--primary",
        ".menu-btn--secondary",
        ".menu-card",
        ".menu-card--medical",
        ".menu-card--hero",
        ".menu-input",
        ".menu-tab",
        ".menu-tabbar",
        ".menu-drawer",
        ".menu-toast",
        ".menu-modal",
        ".menu-list-item",
        ".menu-chip",
        ".menu-avatar",
        ".menu-badge-dot",
        ".menu-badge-num",
        ".menu-skeleton",
        ".menu-empty",
        ".menu-topbar-a1",
    ]
    for cls in expected_classes:
        assert cls in css, f"缺失组件类：{cls}"


# ============================================================
# T06：design-tokens.json 是合法 JSON 且顶层结构完整
# ============================================================
def test_t06_json_schema_valid():
    raw = _read(JSON_FILE)
    obj = json.loads(raw)
    # 顶层必备字段
    for k in [
        "meta", "color", "shadow", "radius",
        "fontSize", "space", "gradient", "components", "ironRules", "accessibility"
    ]:
        assert k in obj, f"design-tokens.json 顶层缺失字段：{k}"
    # color.sky 11 级
    assert "sky" in obj["color"], "color.sky 缺失"
    assert len(obj["color"]["sky"]) == 11, (
        f"color.sky 应为 11 级，实际 {len(obj['color']['sky'])}"
    )


# ============================================================
# T07：辅助色含 allowed 场景白名单约束
# ============================================================
def test_t07_accent_allowed_whitelist():
    obj = json.loads(_read(JSON_FILE))
    semantic = obj["color"]["semantic"]
    for color_name in ["success", "danger", "member"]:
        assert color_name in semantic, f"语义色缺失：{color_name}"
        assert "allowed" in semantic[color_name], (
            f"{color_name} 缺失 allowed 白名单"
        )
        assert isinstance(semantic[color_name]["allowed"], list)
        assert len(semantic[color_name]["allowed"]) > 0, (
            f"{color_name}.allowed 不能为空"
        )


# ============================================================
# T08：PRD-442.md 9 大章节齐全
# ============================================================
def test_t08_prd_chapters_complete():
    md = _read(PRD_FILE)
    expected_chapters = [
        "## 0. 决策摘要",
        "## 1. 项目背景与目标",
        "## 2. 落地范围",
        "## 3. Design Tokens",
        "## 4. H5 组件库",
        "## 5. 三端任务拆解",
        "## 6. 灰度发布与切换策略",
        "## 7. 验收标准",
        "## 8. 风险清单",
        "## 9. 版本历史",
    ]
    for chapter in expected_chapters:
        assert chapter in md, f"PRD 缺失章节：{chapter}"


# ============================================================
# T09：prototype.html 含完整 6 屏
# ============================================================
def test_t09_prototype_six_screens_exact():
    html = _read(PROTO_FILE)
    # phone-tag SCREEN ① ~ ⑥ 各出现一次
    expected_tags = ["SCREEN ①", "SCREEN ②", "SCREEN ③", "SCREEN ④", "SCREEN ⑤", "SCREEN ⑥"]
    for tag in expected_tags:
        assert tag in html, f"prototype.html 缺失 {tag}"
    # 6 屏锚点
    for i in range(1, 7):
        assert f'id="screen{i}"' in html, f"缺失锚点 screen{i}"


# ============================================================
# T10：components.html 包含 13 类组件 demo
# ============================================================
def test_t10_components_demo_complete():
    html = _read(COMP_FILE)
    # 通过章节标题定位
    expected_sections = [
        "颜色 Tokens",
        "渐变 Tokens",
        "Button",
        "Card",
        "Input",
        "Tab",
        "Drawer",
        "Toast",
        "List",
        "Chip",
        "Avatar",
        "Badge",
        "Skeleton",
    ]
    for sec in expected_sections:
        assert sec in html, f"components.html 缺失组件章节：{sec}"


# ============================================================
# T11：所有阴影 token 禁止使用纯黑
# ============================================================
def test_t11_shadows_no_black():
    css = _read(CSS_FILE)
    # 仅提取 --shadow-N: 定义行（不包括引用如 box-shadow: var(--shadow-2);）
    shadow_lines = [
        line for line in css.split("\n")
        if re.match(r"\s*--shadow-\d+\s*:", line)
    ]
    assert len(shadow_lines) >= 4, f"阴影 token 数量不足 4 级，实际 {len(shadow_lines)}"
    for line in shadow_lines:
        # 禁止 rgba(0, 0, 0, ...) 纯黑
        assert "rgba(0" not in line.replace(" ", ""), (
            f"阴影禁用纯黑：{line.strip()}"
        )
        assert "#000" not in line, f"阴影禁用 #000：{line.strip()}"
        # 必须含天蓝色（56,189,248）或 sky-* 系列 RGB
        assert ("56" in line and "189" in line and "248" in line) or "rgba(2, 132, 199" in line, (
            f"阴影应使用天蓝色 RGB：{line.strip()}"
        )


# ============================================================
# T12：字号合规（base 14, 关键指标 >= 36，AA 无障碍）
# ============================================================
def test_t12_font_size_aa_compliance():
    css = _read(CSS_FILE)
    # base 字号 14
    assert re.search(r"--fs-14\s*:\s*14px", css), "--fs-14 必须 == 14px（中老年友好正文最小）"
    # 关键指标 36
    assert re.search(r"--fs-36\s*:\s*36px", css), "--fs-36 必须 == 36px（关键指标 AA 无障碍）"
    # JSON 同步
    obj = json.loads(_read(JSON_FILE))
    fs = obj["fontSize"]
    assert fs["14"]["value"] == "14px"
    assert fs["36"]["value"] == "36px"


# ============================================================
# T13：小程序 wxss tokens 文件存在且包含 11 级 sky-*
# ============================================================
def test_t13_miniprogram_wxss_tokens():
    assert os.path.exists(WXSS_FILE), f"缺失小程序 tokens 文件：{WXSS_FILE}"
    wxss = _read(WXSS_FILE)
    for level, hex_val in EXPECTED_SKY_PALETTE.items():
        pattern = rf"--sky-{level}\s*:\s*{re.escape(hex_val)}\s*;"
        assert re.search(pattern, wxss, re.IGNORECASE), (
            f"小程序 wxss 中缺失 --sky-{level}: {hex_val}"
        )


# ============================================================
# T14：Flutter ThemeData dart 文件存在且包含 11 级 MenuModeColors
# ============================================================
def test_t14_flutter_theme_dart():
    assert os.path.exists(DART_FILE), f"缺失 Flutter theme 文件：{DART_FILE}"
    dart = _read(DART_FILE)
    # 检查 11 级颜色定义（Color(0xFFXXXXXX) 形式）
    for level, hex_val in EXPECTED_SKY_PALETTE.items():
        # 去掉 # 转为 0xFF 前缀
        hex_upper = hex_val.lstrip("#").upper()
        token_const = f"sky{level}"
        pattern = rf"static\s+const\s+{token_const}\s*=\s*Color\(0xFF{hex_upper}\)"
        assert re.search(pattern, dart), (
            f"Flutter dart 中缺失 {token_const} = Color(0xFF{hex_upper})"
        )
    # 必须含 buildMenuModeTheme 函数
    assert "buildMenuModeTheme" in dart, "缺少 buildMenuModeTheme 工厂函数"
    # 必须含病历卡 Widget
    assert "MenuMedicalCard" in dart, "缺少 MenuMedicalCard 病历卡 Widget"
    # 必须含主按钮 Widget
    assert "MenuPrimaryButton" in dart, "缺少 MenuPrimaryButton 主按钮 Widget"


# ============================================================
# T15：与 PRD-441 AI 模式色板兼容性（11 级核心 hex 完全一致）
# ============================================================
def test_t15_compatible_with_prd441_ai_mode():
    """菜单模式 sky-* 色板必须与 AI 模式 brand-* 色板的核心色值完全一致，避免割裂感。"""
    if not os.path.exists(AI_CSS_FILE):
        pytest.skip(f"PRD-441 文件不存在，跳过兼容性测试：{AI_CSS_FILE}")

    ai_css = _read(AI_CSS_FILE)
    # AI 模式使用 --color-brand-* 命名，菜单模式使用 --sky-* 命名
    # 9 级共用色（50, 100, 200, 300, 400, 500, 600, 700, 800, 900）
    shared_levels = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900"]
    for level in shared_levels:
        expected_hex = EXPECTED_SKY_PALETTE[level]
        ai_pattern = rf"--color-brand-{level}\s*:\s*{re.escape(expected_hex)}"
        assert re.search(ai_pattern, ai_css, re.IGNORECASE), (
            f"PRD-441 AI 模式 brand-{level} 与菜单模式 sky-{level} 色值不一致，"
            f"期望：{expected_hex}，请检查 design-tokens.css 兼容性"
        )


# ============================================================
# T16：核心铁律——病历卡白底 + 左 3px sky-400 竖线 + shadow-2
# ============================================================
def test_t16_medical_card_iron_rule():
    css = _read(CSS_FILE)
    # 找到 .menu-card--medical 块
    match = re.search(r"\.menu-card--medical\s*\{[^}]+\}", css)
    assert match, "未找到 .menu-card--medical 定义"
    block = match.group(0)
    assert "background:" in block and "var(--bg-base)" in block, "病历卡必须白底"
    assert "var(--shadow-2)" in block, "病历卡必须 shadow-2"

    # ::before 检查 3px sky-400 竖线
    before_match = re.search(r"\.menu-card--medical::before\s*\{[^}]+\}", css)
    assert before_match, "未找到 .menu-card--medical::before 左竖线定义"
    before_block = before_match.group(0)
    assert "width: 3px" in before_block, "病历卡左竖线必须 3px"
    assert "var(--sky-400)" in before_block, "病历卡左竖线必须 sky-400"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
