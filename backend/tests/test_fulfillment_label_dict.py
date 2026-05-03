"""[履约方式中文化 Bug] 公共字典存在性 & 多端一致性回归测试

覆盖：
1. admin-web / h5-web / miniprogram / flutter_app 各端的履约方式公共字典文件存在
2. 各端字典必须包含 on_site / to_store / delivery / in_store / virtual 全部 5 个键
3. 字典中文标签口径完全一致：
   on_site → 上门服务，to_store → 到店服务，delivery → 快递配送，
   in_store → 到店核销，virtual → 线上服务
4. Flutter APP 中 `_fulfillmentLabel` 局部 switch 已被替换为公共字典调用，避免命中 default 回显英文
"""
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


EXPECTED_LABELS = {
    "on_site": "上门服务",
    "to_store": "到店服务",
    "delivery": "快递配送",
    "in_store": "到店核销",
    "virtual": "线上服务",
}


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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


def test_flutter_unified_order_detail_uses_public_label():
    """flutter unified_order_detail_screen.dart 不再保留旧版只覆盖 3 个 case 的 switch。"""
    p = os.path.join(REPO_ROOT, "flutter_app", "lib", "screens", "order",
                     "unified_order_detail_screen.dart")
    assert os.path.isfile(p)
    text = _read(p)
    # 必须 import 公共字典
    assert "fulfillment_label.dart" in text, "未 import 公共字典"
    # 旧版直接 return type 的 default 分支不允许再出现：寻找老的失误 default 文本
    # 旧实现内特征："case 'delivery':\n        return '快递配送';" 后跟 default: return type
    # 我们核心规则：函数体不应再含 `return type;` 字面量
    # 仅检查 _fulfillmentLabel 函数体范围
    m = re.search(r"String\s+_fulfillmentLabel\([^)]*\)[^{]*\{([^}]*)\}", text)
    if m:
        body = m.group(1)
        # 旧版的 default 直接 return type
        assert "return type;" not in body, "_fulfillmentLabel 仍命中 default 回显原始枚举"


def test_admin_orders_page_uses_public_label():
    """admin-web 订单明细页履约方式列必须改用公共字典。"""
    p = os.path.join(REPO_ROOT, "admin-web", "src", "app", "(admin)",
                     "product-system", "orders", "page.tsx")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel" in text, "admin-web 订单明细页未引入 fulfillmentLabel"


def test_h5_unified_order_uses_public_label():
    """h5 订单详情页必须使用公共字典展示履约方式。"""
    p = os.path.join(REPO_ROOT, "h5-web", "src", "app", "unified-order", "[id]", "page.tsx")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel" in text, "h5 订单详情页未引入 fulfillmentLabel"


def test_miniprogram_unified_order_uses_public_label():
    """小程序订单详情页 wxml 必须引入 wxs 公共字典。"""
    p = os.path.join(REPO_ROOT, "miniprogram", "pages", "unified-order-detail", "index.wxml")
    assert os.path.isfile(p)
    text = _read(p)
    assert "fulfillmentLabel.wxs" in text, "小程序订单详情页未引入 wxs 公共字典"
    assert "ff.fulfillmentLabel" in text, "小程序订单详情页未调用 ff.fulfillmentLabel"
