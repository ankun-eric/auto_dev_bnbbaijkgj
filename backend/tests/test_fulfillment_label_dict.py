"""[履约方式中文化 + 履约类型清理 Bug] 公共字典存在性 & 多端一致性回归测试

修复版（2026-05-04）：
1. admin-web / h5-web / miniprogram / flutter_app 各端的履约方式公共字典文件存在
2. 各端字典必须**精确**包含 4 个键：delivery / in_store / on_site / virtual
   - 已彻底删除历史 to_store 僵尸条目（后端 FulfillmentType 枚举从未包含此值）
3. 字典中文标签新口径完全一致：
   - delivery → 快递配送
   - in_store → 到店服务（原"到店核销"，已统一改名）
   - on_site  → 上门服务
   - virtual  → 虚拟商品（原"线上服务"，已统一改名）
4. 字典内键的插入顺序为 delivery / in_store / on_site / virtual
5. admin-web 商品表单页面禁止再手写本地履约下拉数组，必须复用 FULFILLMENT_OPTIONS
6. 旧标签字面量（"到店核销"/"线上服务"）不再出现在 5 份字典文件中
"""
import os
import re

import pytest

REPO_ROOT = os.environ.get("REPO_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

REQUIRED_DIRS = [
    os.path.join(REPO_ROOT, "admin-web"),
    os.path.join(REPO_ROOT, "h5-web"),
    os.path.join(REPO_ROOT, "miniprogram"),
    os.path.join(REPO_ROOT, "flutter_app"),
]


def _all_dirs_exist() -> bool:
    return all(os.path.isdir(p) for p in REQUIRED_DIRS)


pytestmark = pytest.mark.skipif(
    not _all_dirs_exist(),
    reason=(
        "前端各端目录在当前运行环境不可见（典型场景：仅含后端代码的 Docker 容器）。"
        "请在仓库根目录运行此测试，或通过 REPO_ROOT 环境变量指定仓库路径。"
    ),
)


# 修复后的新口径（与后端 FulfillmentType 枚举严格 1:1，且删除 to_store）
EXPECTED_LABELS = {
    "delivery": "快递配送",
    "in_store": "到店服务",
    "on_site": "上门服务",
    "virtual": "虚拟商品",
}

# 期望的字典键插入顺序
EXPECTED_ORDER = ["delivery", "in_store", "on_site", "virtual"]

# 旧的、本次修复后必须消失的标签（防止再次回潮）
DEPRECATED_LABELS = ["到店核销", "线上服务"]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------- 各端文件存在 + 必含 4 键 4 标签 ----------------

def test_admin_web_fulfillment_label_file_exists_and_complete():
    p = os.path.join(REPO_ROOT, "admin-web", "src", "utils", "fulfillmentLabel.ts")
    assert os.path.isfile(p), f"admin-web 公共字典文件未创建: {p}"
    text = _read(p)
    for code, label in EXPECTED_LABELS.items():
        assert code in text, f"admin-web 字典缺少 key: {code}"
        assert label in text, f"admin-web 字典缺少中文标签: {label}"


def test_h5_web_fulfillment_label_file_exists_and_complete():
    p = os.path.join(REPO_ROOT, "h5-web", "src", "utils", "fulfillmentLabel.ts")
    assert os.path.isfile(p), f"h5-web 公共字典文件未创建: {p}"
    text = _read(p)
    for code, label in EXPECTED_LABELS.items():
        assert code in text, f"h5-web 字典缺少 key: {code}"
        assert label in text, f"h5-web 字典缺少中文标签: {label}"


def test_miniprogram_fulfillment_label_file_exists_and_complete():
    p_js = os.path.join(REPO_ROOT, "miniprogram", "utils", "fulfillmentLabel.js")
    p_wxs = os.path.join(REPO_ROOT, "miniprogram", "utils", "fulfillmentLabel.wxs")
    assert os.path.isfile(p_js), f"miniprogram 公共字典 .js 文件未创建: {p_js}"
    assert os.path.isfile(p_wxs), f"miniprogram 公共字典 .wxs 文件未创建: {p_wxs}"
    js_text = _read(p_js)
    wxs_text = _read(p_wxs)
    for code, label in EXPECTED_LABELS.items():
        assert code in js_text, f"miniprogram .js 字典缺少 key: {code}"
        assert label in js_text, f"miniprogram .js 字典缺少中文标签: {label}"
        assert code in wxs_text, f"miniprogram .wxs 字典缺少 key: {code}"
        assert label in wxs_text, f"miniprogram .wxs 字典缺少中文标签: {label}"


def test_flutter_fulfillment_label_file_exists_and_complete():
    p = os.path.join(REPO_ROOT, "flutter_app", "lib", "utils", "fulfillment_label.dart")
    assert os.path.isfile(p), f"flutter 公共字典文件未创建: {p}"
    text = _read(p)
    for code, label in EXPECTED_LABELS.items():
        assert code in text, f"flutter 字典缺少 key: {code}"
        assert label in text, f"flutter 字典缺少中文标签: {label}"


# ---------------- 删除 to_store 僵尸映射的回归 ----------------

def _extract_dict_block(text: str) -> str:
    """从源码文本中提取字典定义块（{...}）以避免 JSDoc/注释里的提及干扰。

    本项目所有 5 份字典文件都长这样：
        const/var/Map MAP = {
            ...
        };
    我们直接抓取第一个由 `{` 开始、`}` 结束的多行块即可（保守地仅抓首个块）。
    """
    m = re.search(r"\{([^{}]*?)\}", text, flags=re.DOTALL)
    return m.group(1) if m else text


@pytest.mark.parametrize("rel_path", [
    "admin-web/src/utils/fulfillmentLabel.ts",
    "h5-web/src/utils/fulfillmentLabel.ts",
    "miniprogram/utils/fulfillmentLabel.js",
    "miniprogram/utils/fulfillmentLabel.wxs",
    "flutter_app/lib/utils/fulfillment_label.dart",
])
def test_dict_does_not_contain_zombie_to_store(rel_path):
    p = os.path.join(REPO_ROOT, rel_path)
    assert os.path.isfile(p), f"字典文件不存在: {p}"
    text = _read(p)
    block = _extract_dict_block(text)
    # 字典定义块内绝不允许再出现 to_store 这个键（注释里的"to_store"提示是允许的）
    assert "to_store" not in block, (
        f"{rel_path} 字典定义块中仍包含 to_store 僵尸映射: {block!r}"
    )


# ---------------- 删除"到店核销" / "线上服务"旧标签 ----------------

@pytest.mark.parametrize("rel_path", [
    "admin-web/src/utils/fulfillmentLabel.ts",
    "h5-web/src/utils/fulfillmentLabel.ts",
    "miniprogram/utils/fulfillmentLabel.js",
    "miniprogram/utils/fulfillmentLabel.wxs",
    "flutter_app/lib/utils/fulfillment_label.dart",
])
def test_dict_files_no_legacy_chinese_labels(rel_path):
    p = os.path.join(REPO_ROOT, rel_path)
    assert os.path.isfile(p), f"字典文件不存在: {p}"
    text = _read(p)
    for legacy in DEPRECATED_LABELS:
        assert legacy not in text, (
            f"{rel_path} 不应再出现旧标签 {legacy}（请改用新口径：到店服务 / 虚拟商品）"
        )


# ---------------- 字典键的插入顺序与下拉一致 ----------------

def _extract_keys_in_order(block: str) -> list:
    """从字典块中抽取键名（顺序）。匹配 'key:' 或 "key": 形式。"""
    keys = []
    for m in re.finditer(r"['\"]?([a-z_]+)['\"]?\s*:", block):
        k = m.group(1)
        if k in {"delivery", "in_store", "on_site", "virtual", "to_store"}:
            keys.append(k)
    return keys


@pytest.mark.parametrize("rel_path", [
    "admin-web/src/utils/fulfillmentLabel.ts",
    "h5-web/src/utils/fulfillmentLabel.ts",
    "miniprogram/utils/fulfillmentLabel.js",
    "miniprogram/utils/fulfillmentLabel.wxs",
    "flutter_app/lib/utils/fulfillment_label.dart",
])
def test_dict_key_order_is_delivery_in_store_on_site_virtual(rel_path):
    p = os.path.join(REPO_ROOT, rel_path)
    text = _read(p)
    block = _extract_dict_block(text)
    keys = _extract_keys_in_order(block)
    assert keys == EXPECTED_ORDER, (
        f"{rel_path} 字典键顺序错误，期望 {EXPECTED_ORDER}，实际 {keys}"
    )


# ---------------- admin-web 商品表单复用 FULFILLMENT_OPTIONS ----------------

def test_admin_web_products_page_reuses_fulfillment_options():
    """admin-web 商品表单页禁止手写本地履约下拉数组，必须复用 FULFILLMENT_OPTIONS。"""
    p = os.path.join(REPO_ROOT, "admin-web", "src", "app", "(admin)",
                     "product-system", "products", "page.tsx")
    assert os.path.isfile(p), f"商品页文件不存在: {p}"
    text = _read(p)
    assert "FULFILLMENT_OPTIONS" in text, (
        "admin-web 商品页未导入或未使用 FULFILLMENT_OPTIONS"
    )
    # 严禁再次出现旧的 5 项手写数组（含两次 'on_site' 重复项）
    occ = text.count("value: 'on_site'")
    assert occ <= 1, (
        f"admin-web 商品页疑似再次散落手写履约下拉数组（'on_site' 出现 {occ} 次）"
    )


# ---------------- 历史已存在的几个回归用例（保留） ----------------

def test_flutter_unified_order_detail_uses_public_label():
    """flutter unified_order_detail_screen.dart 不再保留旧版只覆盖 3 个 case 的 switch。"""
    p = os.path.join(REPO_ROOT, "flutter_app", "lib", "screens", "order",
                     "unified_order_detail_screen.dart")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillment_label.dart" in text, "未 import 公共字典"
    m = re.search(r"String\s+_fulfillmentLabel\([^)]*\)[^{]*\{([^}]*)\}", text)
    if m:
        body = m.group(1)
        assert "return type;" not in body, "_fulfillmentLabel 仍命中 default 回显原始枚举"


def test_admin_orders_page_uses_public_label():
    p = os.path.join(REPO_ROOT, "admin-web", "src", "app", "(admin)",
                     "product-system", "orders", "page.tsx")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel" in text, "admin-web 订单明细页未引入 fulfillmentLabel"


def test_h5_unified_order_uses_public_label():
    p = os.path.join(REPO_ROOT, "h5-web", "src", "app", "unified-order", "[id]", "page.tsx")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel" in text, "h5 订单详情页未引入 fulfillmentLabel"


def test_miniprogram_unified_order_uses_public_label():
    p = os.path.join(REPO_ROOT, "miniprogram", "pages", "unified-order-detail", "index.wxml")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel.wxs" in text, "小程序订单详情页未引入 wxs 公共字典"
    assert "ff.fulfillmentLabel" in text, "小程序订单详情页未调用 ff.fulfillmentLabel"
