# -*- coding: utf-8 -*-
"""
[2026-05-05 订单页地址导航按钮 PRD v1.0] 非UI自动化测试

本文件覆盖以下静态/单元层面测试：
1) 后端 OrderResponse schema 新增字段（store_address/store_lat/store_lng/
   shipping_address_text/shipping_address_name/shipping_address_phone）字段类型与
   默认值正确。
2) _build_order_response 在 store / shipping_address / service_address_snapshot
   存在时正确填充新增字段；不存在时不抛异常且返回 None。
3) H5 / 小程序 / Flutter 三端关键文件存在性 + 关键引用正确：
   - h5-web/src/components/AddressNavButton.tsx
   - h5-web/src/components/MapNavSheet.tsx 中 lat/lng 类型已可选
   - miniprogram/utils/map-nav.js 导出 navigateToAddress
   - flutter_app/lib/widgets/address_nav_button.dart 含 AddressNavButton 类
   - flutter_app/lib/utils/map_nav_util.dart 中 showMapNavSheet 接受 double? lat/lng
4) 三端关键页面已 import / require 上述模块（防止漏接线）。
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(ROOT, path), 'r', encoding='utf-8') as f:
        return f.read()


class TestBackendSchemaFields(unittest.TestCase):
    """T-1：后端 OrderResponse 新增字段"""

    def test_new_fields_in_schema(self):
        text = _read('backend/app/schemas/unified_orders.py')
        for field in [
            'store_address: Optional[str] = None',
            'store_lat: Optional[float] = None',
            'store_lng: Optional[float] = None',
            'shipping_address_text: Optional[str] = None',
            'shipping_address_name: Optional[str] = None',
            'shipping_address_phone: Optional[str] = None',
        ]:
            self.assertIn(field, text, f'missing schema field: {field}')

    def test_build_order_response_assigns_store_address(self):
        text = _read('backend/app/api/unified_orders.py')
        self.assertIn('resp.store_address = full_addr', text,
                      'store_address 未在 _build_order_response 中赋值')
        self.assertIn('resp.store_lat = float(store_lat)', text)
        self.assertIn('resp.store_lng = float(store_lng)', text)
        self.assertIn('resp.shipping_address_text = text', text)


class TestH5Frontend(unittest.TestCase):
    """T-2：H5 端关键文件 + 关键引用"""

    def test_address_nav_button_exists(self):
        path = 'h5-web/src/components/AddressNavButton.tsx'
        self.assertTrue(os.path.exists(os.path.join(ROOT, path)),
                        f'缺少组件文件 {path}')
        text = _read(path)
        self.assertIn('export default function AddressNavButton', text)
        self.assertIn('MapNavSheet', text)

    def test_map_nav_sheet_lat_lng_optional(self):
        text = _read('h5-web/src/components/MapNavSheet.tsx')
        self.assertIn('lat?: number | null', text,
                      'MapNavTarget.lat 应改为可选')
        self.assertIn('lng?: number | null', text,
                      'MapNavTarget.lng 应改为可选')
        self.assertIn('hasLatLng', text, '应实现经纬度可用性判断分支')

    def test_checkout_imports_address_nav_button(self):
        text = _read('h5-web/src/app/checkout/page.tsx')
        self.assertIn("from '@/components/AddressNavButton'", text)
        self.assertIn('<AddressNavButton', text)

    def test_unified_order_detail_imports_address_nav_button(self):
        text = _read('h5-web/src/app/unified-order/[id]/page.tsx')
        self.assertIn("from '@/components/AddressNavButton'", text)
        self.assertIn('<AddressNavButton', text)
        # OrderDetail 类型增加新字段
        for fld in ['store_address?:', 'store_lat?:', 'store_lng?:',
                    'shipping_address_text?:', 'shipping_address_name?:',
                    'shipping_address_phone?:']:
            self.assertIn(fld, text, f'OrderDetail 缺字段: {fld}')


class TestMiniProgram(unittest.TestCase):
    """T-3：小程序端关键文件 + 关键引用"""

    def test_map_nav_util_exists(self):
        path = 'miniprogram/utils/map-nav.js'
        self.assertTrue(os.path.exists(os.path.join(ROOT, path)),
                        f'缺少 {path}')
        text = _read(path)
        self.assertIn('navigateToAddress', text)
        self.assertIn('wx.openLocation', text)
        self.assertIn('wx.setClipboardData', text, '需提供降级复制路径')

    def test_checkout_uses_map_nav(self):
        text = _read('miniprogram/pages/checkout/index.js')
        self.assertIn("require('../../utils/map-nav')", text)
        self.assertIn('onStoreNavTap', text)
        self.assertIn('onAddrNavTap', text)
        wxml = _read('miniprogram/pages/checkout/index.wxml')
        self.assertIn('onStoreNavTap', wxml)
        self.assertIn('onAddrNavTap', wxml)
        self.assertIn('nav-btn', wxml)

    def test_unified_order_detail_uses_map_nav(self):
        text = _read('miniprogram/pages/unified-order-detail/index.js')
        self.assertIn("require('../../utils/map-nav')", text)
        self.assertIn('onStoreNavTap', text)
        self.assertIn('onUserAddrNavTap', text)
        wxml = _read('miniprogram/pages/unified-order-detail/index.wxml')
        self.assertIn('nav-btn', wxml)
        self.assertIn('onStoreNavTap', wxml)
        self.assertIn('onUserAddrNavTap', wxml)


class TestFlutterApp(unittest.TestCase):
    """T-4：Flutter App 端关键文件 + 关键引用"""

    def test_address_nav_button_widget_exists(self):
        path = 'flutter_app/lib/widgets/address_nav_button.dart'
        self.assertTrue(os.path.exists(os.path.join(ROOT, path)),
                        f'缺少 {path}')
        text = _read(path)
        self.assertIn('class AddressNavButton', text)
        self.assertIn('MapNavUtil.showMapNavSheet', text)

    def test_map_nav_util_lat_lng_optional(self):
        text = _read('flutter_app/lib/utils/map_nav_util.dart')
        # showMapNavSheet 现在 lat/lng 应为 double?（可选）
        self.assertTrue(
            re.search(r'showMapNavSheet\([^)]*?double\?\s+lat,', text, re.S),
            'showMapNavSheet 的 lat 应改为 double? 可选',
        )
        self.assertTrue(
            re.search(r'showMapNavSheet\([^)]*?double\?\s+lng', text, re.S),
            'showMapNavSheet 的 lng 应改为 double? 可选',
        )
        self.assertIn('buildCandidatesByKeyword', text,
                      '应实现关键词搜索路径规划候选')

    def test_unified_order_model_has_new_fields(self):
        text = _read('flutter_app/lib/models/unified_order.dart')
        for fld in ['storeAddress', 'storeLat', 'storeLng',
                    'shippingAddressText', 'shippingAddressName',
                    'shippingAddressPhone']:
            self.assertIn(fld, text, f'UnifiedOrder model 缺字段: {fld}')
        self.assertIn("json['store_address']", text)
        self.assertIn("json['shipping_address_text']", text)

    def test_checkout_screen_has_nav_button(self):
        text = _read(
            'flutter_app/lib/screens/product/checkout_screen.dart'
        )
        self.assertIn(
            "import '../../widgets/address_nav_button.dart'", text,
        )
        self.assertIn('AddressNavButton(', text)

    def test_order_detail_screen_has_address_section(self):
        text = _read(
            'flutter_app/lib/screens/order/unified_order_detail_screen.dart'
        )
        self.assertIn(
            "import '../../widgets/address_nav_button.dart'", text,
        )
        self.assertIn('_buildAddressSection', text)
        self.assertIn('AddressNavButton(', text)


class TestPRDCompliance(unittest.TestCase):
    """T-5：PRD 关键约束合规检查"""

    def test_h5_navigation_button_uses_brand_color(self):
        """主题色 #52c41a"""
        text = _read('h5-web/src/components/AddressNavButton.tsx')
        self.assertIn('#52c41a', text)

    def test_h5_debounce_500ms(self):
        text = _read('h5-web/src/components/AddressNavButton.tsx')
        self.assertIn('500', text, 'PRD E-09 要求 500ms 防抖')

    def test_miniprogram_debounce_500ms(self):
        text = _read('miniprogram/utils/map-nav.js')
        self.assertIn('500', text, 'PRD E-09 要求 500ms 防抖')

    def test_flutter_debounce_500ms(self):
        text = _read('flutter_app/lib/widgets/address_nav_button.dart')
        self.assertIn('500', text, 'PRD E-09 要求 500ms 防抖')

    def test_h5_keyword_fallback_implemented(self):
        """PRD F-08：无经纬度走文字关键词降级"""
        text = _read('h5-web/src/components/MapNavSheet.tsx')
        # 至少需要包含一种关键词搜索路径规划 URI
        self.assertTrue(
            'amap.com/search' in text or 'iosamap://path' in text,
            'H5 端缺少无经纬度文字关键词降级实现',
        )


if __name__ == '__main__':
    unittest.main()
