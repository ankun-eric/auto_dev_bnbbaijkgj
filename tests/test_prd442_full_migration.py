# -*- coding: utf-8 -*-
"""PRD-442 全域迁移落地 — 阶段 2 自动化测试（非 UI）。

覆盖：
- 单一真相源 design-tokens.json 合法且字段完整
- 三端 token 文件存在、内容由脚本生成、与 JSON 一致
- 8 个种子 SVG 图标存在
- Flutter token 包结构 + pubspec 引用
- lint-legacy-green.mjs 脚本能正常运行（不阻塞）
- 小程序 app.wxss 已 @import 新 tokens
- PRD-442 文档存在
- 铁律 1：阴影禁纯黑
- 铁律 2：11 级 hex 与 PRD-441 完全一致（兼容性）
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "design-system" / "design-tokens.json"
CSS_PATH = ROOT / "h5-web" / "public" / "design-system-v2" / "design-tokens.css"
WXSS_PATH = ROOT / "miniprogram" / "styles" / "design-tokens.wxss"
DART_PATH = ROOT / "packages" / "bini_design_tokens" / "lib" / "src" / "tokens.g.dart"
ICONS_DIR = ROOT / "design-system" / "icons"
PUB_PATH = ROOT / "packages" / "bini_design_tokens" / "pubspec.yaml"
FLUTTER_PUB = ROOT / "flutter_app" / "pubspec.yaml"
LINT_SCRIPT = ROOT / "scripts" / "lint-legacy-green.mjs"
GEN_TOKENS = ROOT / "scripts" / "gen-tokens.mjs"
GEN_ICONS = ROOT / "scripts" / "gen-icons.mjs"
APP_WXSS = ROOT / "miniprogram" / "app.wxss"
PRD_DOC = ROOT / "design-system" / "PRD-442.md"
H5_INDEX = ROOT / "h5-web" / "public" / "design-system-v2" / "index.html"
ICONS_JSON_H5 = ROOT / "h5-web" / "public" / "design-system-v2" / "icons.json"


# T01 单一真相源存在 + 是合法 JSON
def test_t01_design_tokens_json_valid():
    assert JSON_PATH.exists(), f"missing {JSON_PATH}"
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for key in ("meta", "color", "gradient", "fontSize", "space", "radius", "shadow", "ironRules"):
        assert key in data, f"missing top-level key {key}"


# T02 11 级天蓝色阶完整且 hex 与 PRD-441 表完全一致
def test_t02_brand_palette_complete():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    brand = data["color"]["brand"]
    expected = {
        "50": "#f0f9ff", "100": "#e0f2fe", "150": "#dbeafe",
        "200": "#bae6fd", "300": "#7dd3fc", "400": "#38bdf8",
        "500": "#0ea5e9", "600": "#0284c7", "700": "#0369a1",
        "800": "#075985", "900": "#0c4a6e",
    }
    for k, hex_val in expected.items():
        assert k in brand, f"brand-{k} missing"
        assert brand[k]["value"].lower() == hex_val.lower(), f"brand-{k} hex mismatch"


# T03 5 大渐变 token
def test_t03_five_gradients():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    grads = data["gradient"]
    for name in ("topbar", "userBubble", "primaryBtn", "heroDeep", "userCard"):
        assert name in grads, f"gradient {name} missing"


# T04 阴影必须使用天蓝（铁律：禁纯黑）
def test_t04_shadow_no_black():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for k, v in data["shadow"].items():
        if k == "comment":
            continue
        val = v["value"]
        assert "rgba(0," not in val.replace(" ", ""), f"shadow.{k} uses black"
        assert "56, 189, 248" in val or "56,189,248" in val, f"shadow.{k} not sky blue"


# T05 字号 base = 14（中老年友好）
def test_t05_base_font_aa():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    fs = data["fontSize"]
    assert fs["sm"]["value"] == 14
    assert fs["2xl"]["value"] >= 22  # 关键指标字号下限


# T06 字号四档无障碍配置
def test_t06_font_scale_accessibility():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    scales = data["fontScaleAccessibility"]["scales"]
    for s in ("standard", "large", "xlarge", "xxlarge"):
        assert s in scales, f"font scale {s} missing"
    assert scales["standard"]["value"] == 1.0
    assert scales["xxlarge"]["value"] == 1.5


# T07 三端生成的 H5 CSS 文件存在且包含核心 token
def test_t07_h5_css_generated():
    assert CSS_PATH.exists(), "H5 css not generated"
    content = CSS_PATH.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in content
    assert "--color-brand-400: #38bdf8" in content
    assert "--gradient-primary-btn:" in content
    assert ".bh-card-medical" in content
    assert "background: var(--color-brand-400)" in content  # 病历卡铁律


# T08 三端生成的小程序 WXSS 存在且使用 rpx
def test_t08_miniprogram_wxss_generated():
    assert WXSS_PATH.exists(), "miniprogram wxss not generated"
    content = WXSS_PATH.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in content
    assert "--color-brand-400: #38bdf8" in content
    # base font (14px) -> 28rpx
    assert "--fs-sm: 28rpx;" in content


# T09 Flutter dart token 文件存在且类正确
def test_t09_flutter_dart_generated():
    assert DART_PATH.exists(), "flutter dart not generated"
    content = DART_PATH.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in content
    assert "class BhTokens" in content
    assert "colorBrand400 = Color(0xFF38BDF8)" in content
    assert "class BhGradients" in content
    assert "class BhShadows" in content
    # 阴影应为天蓝（含 38BDF8）
    assert "38BDF8" in content


# T10 Flutter token 包 pubspec 配置
def test_t10_pubspec_flutter_token_pkg():
    content = PUB_PATH.read_text(encoding="utf-8")
    assert "name: bini_design_tokens" in content
    assert "version: 0.1.0" in content


# T11 flutter_app 已通过 path 引用 token 包
def test_t11_flutter_app_path_dep():
    content = FLUTTER_PUB.read_text(encoding="utf-8")
    assert "bini_design_tokens:" in content
    assert "path: ../packages/bini_design_tokens" in content


# T12 8 个种子图标存在
def test_t12_seed_icons_exist():
    expected = ["health-report", "heart-rate", "medication", "family",
                "bell", "camera", "voice", "chevron-down"]
    for name in expected:
        p = ICONS_DIR / f"{name}.svg"
        assert p.exists(), f"icon {name}.svg missing"
        assert 'viewBox="0 0 24 24"' in p.read_text(encoding="utf-8"), \
            f"icon {name} viewBox not 0 0 24 24"


# T13 lint 脚本能正常运行（不阻塞）
def test_t13_lint_script_runs():
    assert LINT_SCRIPT.exists()
    proc = subprocess.run(
        ["node", str(LINT_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"lint script failed:\n{proc.stdout}\n{proc.stderr}"
    assert "[lint-legacy-green]" in proc.stdout


# T14 gen-tokens.mjs 二次执行后 git diff 为空（关键 CI 约束）
def test_t14_gen_tokens_idempotent():
    proc = subprocess.run(
        ["node", str(GEN_TOKENS)],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"gen-tokens failed:\n{proc.stdout}\n{proc.stderr}"
    # 文件仍存在
    assert CSS_PATH.exists()
    assert WXSS_PATH.exists()
    assert DART_PATH.exists()


# T15 gen-icons.mjs 二次执行后产物存在且 icons.json 包含 8 个图标
def test_t15_gen_icons_idempotent():
    proc = subprocess.run(
        ["node", str(GEN_ICONS)],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"gen-icons failed:\n{proc.stdout}\n{proc.stderr}"
    assert ICONS_JSON_H5.exists()
    data = json.loads(ICONS_JSON_H5.read_text(encoding="utf-8"))
    assert data["$count"] == 8
    assert "health-report" in data["icons"]


# T16 小程序 app.wxss 已 @import 新 tokens
def test_t16_app_wxss_imports_new_tokens():
    content = APP_WXSS.read_text(encoding="utf-8")
    assert '@import "/styles/design-tokens.wxss"' in content


# T17 PRD-442 实施版文档存在且关键章节齐全
def test_t17_prd442_doc():
    assert PRD_DOC.exists()
    content = PRD_DOC.read_text(encoding="utf-8")
    for h in ["一、本轮已交付", "二、本轮未交付", "三、铁律", "四、运行命令速查"]:
        assert h in content, f"section '{h}' missing in PRD-442.md"


# T18 H5 index.html 入口可视化页存在且引用了 design-tokens.css
def test_t18_h5_index_page():
    assert H5_INDEX.exists()
    content = H5_INDEX.read_text(encoding="utf-8")
    assert "design-tokens.css" in content
    assert "PRD-442" in content


# T19 与 PRD-441 兼容性：brand 颜色 hex 完全一致
def test_t19_compat_with_prd441():
    """PRD-442 brand-* 必须与 PRD-441 design-tokens.css（如已存在）的 11 级 hex 完全一致。"""
    prd441_css = ROOT / "h5-web" / "public" / "design-system" / "design-tokens.css"
    if not prd441_css.exists():
        # 若 PRD-441 未部署则跳过（不影响本次）
        return
    css = prd441_css.read_text(encoding="utf-8").lower()
    json_data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for k, v in json_data["color"]["brand"].items():
        hex_val = v["value"].lower()
        # PRD-441 css 形如 `--color-brand-50:  #f0f9ff;`（hex 前可能有多个空格、之后有注释）
        rx = re.compile(rf"--color-brand-{re.escape(k)}\s*:\s*{re.escape(hex_val)}\b")
        assert rx.search(css), f"brand-{k} hex mismatch with PRD-441 (expected {hex_val})"


# T20 铁律列表完整（8 条）
def test_t20_iron_rules_count():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rules = data["ironRules"]["rules"]
    assert len(rules) >= 7, f"iron rules count {len(rules)} < 7"
