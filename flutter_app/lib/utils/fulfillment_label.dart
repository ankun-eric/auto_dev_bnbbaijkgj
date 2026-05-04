/// 履约方式中英文映射统一字典（全端共用同一份口径）。
///
/// 后端枚举值 → 中文标签（与 FulfillmentType 枚举严格 1:1 对应）：
///   delivery  → 快递配送（科技蓝角标）
///   in_store  → 到店服务（暖橙角标）
///   on_site   → 上门服务（生机绿角标 #10B981）
///   virtual   → 虚拟商品（尊贵紫角标）
///
/// 注意：
/// - 字典内部使用 Map 字面量保留键的插入顺序，
///   按 delivery / in_store / on_site / virtual 顺序排列。
/// - 历史 to_store 映射为僵尸条目（后端从未包含此枚举），已彻底删除。
///
/// 兜底：未登记的新枚举值统一返回 "其他服务"。
library;

const Map<String, String> kFulfillmentLabelMap = {
  'delivery': '快递配送',
  'in_store': '到店服务',
  'on_site': '上门服务',
  'virtual': '虚拟商品',
};

/// 把后端履约方式枚举值转换为中文标签。
///
/// 字典中未登记的枚举值（含 null/空字符串）统一返回 "其他服务"。
String fulfillmentLabel(String? type) {
  if (type == null || type.isEmpty) return '其他服务';
  final label = kFulfillmentLabelMap[type];
  if (label == null) {
    print('[fulfillmentLabel] 未登记的履约方式枚举: $type');
    return '其他服务';
  }
  return label;
}
