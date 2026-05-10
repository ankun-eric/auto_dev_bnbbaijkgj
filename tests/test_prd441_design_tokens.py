"""
PRD-441 · AI 对话风格设计 Token 体系 · 非UI自动化测试

校验 4 大交付物在源码层面是否完整、关键 token 是否正确。
"""
import json
import os
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DS_DIR = os.path.join(ROOT, "h5-web", "public", "design-system")


def test_t01_design_system_dir_exists():
    """T01：design-system 目录已创建在 h5-web public 下"""
    assert os.path.isdir(DS_DIR), f"design-system 目录不存在：{DS_DIR}"


def test_t02_four_deliverables_exist():
    """T02：4 大交付物均已落地"""
    expected = [
        "design-tokens.css",
        "design-tokens.json",
        "PRD-441-AI对话风格规范.md",
        "prototype.html",
        "index.html",
    ]
    for f in expected:
        path = os.path.join(DS_DIR, f)
        assert os.path.isfile(path), f"交付物缺失：{f}"
        assert os.path.getsize(path) > 100, f"交付物 {f} 内容过少"


def test_t03_design_tokens_css_brand_palette():
    """T03：design-tokens.css 包含完整的 11 级天蓝色阶"""
    with open(os.path.join(DS_DIR, "design-tokens.css"), encoding="utf-8") as f:
        css = f.read()
    expected_tokens = [
        ("--color-brand-50",  "#f0f9ff"),
        ("--color-brand-100", "#e0f2fe"),
        ("--color-brand-150", "#dbeafe"),
        ("--color-brand-200", "#bae6fd"),
        ("--color-brand-300", "#7dd3fc"),
        ("--color-brand-400", "#38bdf8"),
        ("--color-brand-500", "#0ea5e9"),
        ("--color-brand-600", "#0284c7"),
        ("--color-brand-700", "#0369a1"),
        ("--color-brand-800", "#075985"),
        ("--color-brand-900", "#0c4a6e"),
    ]
    for token, hex_value in expected_tokens:
        assert token in css, f"CSS 缺失 token：{token}"
        assert hex_value in css, f"CSS 缺失颜色值：{hex_value}（{token}）"


def test_t04_design_tokens_css_gradients():
    """T04：5 个核心渐变 token 全部存在"""
    with open(os.path.join(DS_DIR, "design-tokens.css"), encoding="utf-8") as f:
        css = f.read()
    for g in [
        "--gradient-topbar",
        "--gradient-user-bubble",
        "--gradient-primary-btn",
        "--gradient-hero-deep",
        "--gradient-user-card",
    ]:
        assert g in css, f"渐变 token 缺失：{g}"


def test_t05_design_tokens_css_components():
    """T05：基础 + 业务 + 布局组件类齐全"""
    with open(os.path.join(DS_DIR, "design-tokens.css"), encoding="utf-8") as f:
        css = f.read()
    expected_classes = [
        ".bh-btn-primary",
        ".bh-chip", ".bh-chip--active",
        ".bh-badge--normal", ".bh-badge--high", ".bh-badge--critical", ".bh-badge--member",
        ".bh-input",
        ".bh-ai-card",
        ".bh-user-bubble",
        ".bh-thinking",
        ".bh-reminder-card--emergency",
        ".bh-reminder-card--medication",
        ".bh-reminder-card--followup",
        ".bh-metric-card",
        ".bh-topbar-primary",
        ".bh-topbar-secondary",
        ".bh-floating-bell",
        ".bh-drawer-right",
    ]
    for cls in expected_classes:
        assert cls in css, f"组件类缺失：{cls}"


def test_t06_design_tokens_json_schema():
    """T06：design-tokens.json 是合法 JSON 且结构完整"""
    with open(os.path.join(DS_DIR, "design-tokens.json"), encoding="utf-8") as f:
        data = json.load(f)

    # 顶层 key 必须存在
    for key in ["meta", "color", "gradient", "fontSize", "space", "radius", "shadow", "duration", "easing"]:
        assert key in data, f"JSON 顶层缺失：{key}"

    # 11 级 brand
    brand = data["color"]["brand"]
    for level in ["50", "100", "150", "200", "300", "400", "500", "600", "700", "800", "900"]:
        assert level in brand, f"brand 缺少等级：{level}"
        assert "value" in brand[level]

    # 主品牌 400 必须为 #38bdf8
    assert brand["400"]["value"].lower() == "#38bdf8"
    assert brand["600"]["value"].lower() == "#0284c7"

    # 9 个字号
    assert len(data["fontSize"]) >= 9


def test_t07_design_tokens_json_accent_constraints():
    """T07：辅助色含 allowed 场景白名单（红线规范）"""
    with open(os.path.join(DS_DIR, "design-tokens.json"), encoding="utf-8") as f:
        data = json.load(f)
    accent = data["color"]["accent"]
    for k in ["warm-orange", "red", "green", "yellow"]:
        assert k in accent
        assert "allowed" in accent[k] and len(accent[k]["allowed"]) >= 1


def test_t08_prd_md_chapters():
    """T08：PRD Markdown 9 大章节齐全"""
    path = os.path.join(DS_DIR, "PRD-441-AI对话风格规范.md")
    with open(path, encoding="utf-8") as f:
        md = f.read()
    chapters = [
        "## 一、文档定位与范围",
        "## 二、设计哲学",
        "## 三、设计 Token 体系",
        "## 四、组件库",
        "## 五、页面规范",
        "## 六、交互规范",
        "## 七、辅助色控量",
        "## 八、开发交付",
        "## 九、版本历史",
    ]
    for ch in chapters:
        assert ch in md, f"PRD 缺章节：{ch}"


def test_t09_prototype_html_29_screens():
    """T09：prototype.html 包含 29 屏完整内容（用 screen-num 计数）"""
    with open(os.path.join(DS_DIR, "prototype.html"), encoding="utf-8") as f:
        html = f.read()
    # 数 screen-num 的出现次数（每屏一次，外加导航 anchor 不带 screen-num）
    count = html.count('class="screen-num"')
    assert count == 29, f"屏幕数应为 29，实际 {count}"

    # 5 大分组锚点
    for group in ["group1", "group2", "group3", "group4", "group5"]:
        assert f'id="{group}"' in html, f"缺分组锚点：{group}"

    # 引入 design-tokens.css
    assert 'href="./design-tokens.css"' in html


def test_t10_index_html_links():
    """T10：index.html 含 4 大交付物链接"""
    with open(os.path.join(DS_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()
    for ref in [
        "./prototype.html",
        "./PRD-441-AI对话风格规范.md",
        "./design-tokens.css",
        "./design-tokens.json",
    ]:
        assert ref in html, f"index.html 缺链接：{ref}"


def test_t11_no_pure_black_shadow():
    """T11：阴影统一使用天蓝（rgba 56,189,248 或 2,132,199），不允许纯黑 rgba(0,0,0)"""
    with open(os.path.join(DS_DIR, "design-tokens.css"), encoding="utf-8") as f:
        css = f.read()

    # 提取所有 --shadow-* 行
    import re
    shadow_lines = re.findall(r"--shadow-[\w-]+:\s*[^;]+;", css)
    assert len(shadow_lines) >= 4, "至少 4 个 shadow token"
    for line in shadow_lines:
        assert "rgba(0" not in line and "rgba(0," not in line, f"阴影禁止使用纯黑：{line}"


def test_t12_min_font_size_aa():
    """T12：base 字号 >= 14px，关键指标字号 >= 22px（中老年友好）"""
    with open(os.path.join(DS_DIR, "design-tokens.json"), encoding="utf-8") as f:
        data = json.load(f)
    fs = data["fontSize"]
    assert fs["base"]["value"] == "14px"
    assert int(fs["3xl"]["value"].replace("px", "")) >= 22


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
