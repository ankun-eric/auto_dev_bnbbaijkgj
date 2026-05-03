/// 履约方式中英文映射统一字典（全端共用同一份口径）。
///
/// 后端枚举值 → 中文标签：
///   on_site   → 上门服务
///   to_store  → 到店服务
///   delivery  → 快递配送
///   in_store  → 到店核销
///   virtual   → 线上服务
///
/// 兜底：未登记的新枚举值统一显示"其他服务"，避免回显英文原文。
library;

const Map<String, String> kFulfillmentLabelMap = {
  'on_site': '上门服务',
  'to_store': '到店服务',
  'delivery': '快递配送',
  'in_store': '到店核销',
  'virtual': '线上服务',
};

/// 把后端履约方式枚举值转换为中文标签。
///
/// 字典中未登记的枚举值（含 null/空字符串）统一返回 "其他服务"。
String fulfillmentLabel(String? type) {
  if (type == null || type.isEmpty) return '其他服务';
  final label = kFulfillmentLabelMap[type];
  if (label == null) {
    // 控制台告警：未登记的枚举值
    // ignore: avoid_print
    print('[fulfillmentLabel] 未登记的履约方式枚举: $type');
    return '其他服务';
  }
  return label;
}
