// 履约方式中英文映射统一字典（全端共用同一份口径）。
//
// 后端枚举值 → 中文标签：
//   on_site   → 上门服务
//   to_store  → 到店服务
//   delivery  → 快递配送
//   in_store  → 到店核销
//   virtual   → 线上服务
//
// 兜底：未登记的新枚举值统一显示"其他服务"，避免回显英文原文。

const FULFILLMENT_LABEL_MAP = {
  on_site: '上门服务',
  to_store: '到店服务',
  delivery: '快递配送',
  in_store: '到店核销',
  virtual: '线上服务',
};

function fulfillmentLabel(type) {
  if (!type) return '其他服务';
  const label = FULFILLMENT_LABEL_MAP[type];
  if (label === undefined) {
    try { console.warn('[fulfillmentLabel] 未登记的履约方式枚举:', type); } catch (e) {}
    return '其他服务';
  }
  return label;
}

module.exports = {
  FULFILLMENT_LABEL_MAP,
  fulfillmentLabel,
};
