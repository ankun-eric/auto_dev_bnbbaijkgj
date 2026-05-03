/**
 * 履约方式中英文映射统一字典（全端共用同一份口径）。
 *
 * 后端枚举值 → 中文标签：
 *   on_site   → 上门服务
 *   to_store  → 到店服务
 *   delivery  → 快递配送
 *   in_store  → 到店核销
 *   virtual   → 线上服务
 *
 * 兜底：未登记的新枚举值统一显示"其他服务"，避免回显英文原文。
 */

export const FULFILLMENT_LABEL_MAP: Record<string, string> = {
  on_site: '上门服务',
  to_store: '到店服务',
  delivery: '快递配送',
  in_store: '到店核销',
  virtual: '线上服务',
};

/** 把后端履约方式枚举值转换为中文标签。 */
export function fulfillmentLabel(type: string | null | undefined): string {
  if (!type) return '其他服务';
  const label = FULFILLMENT_LABEL_MAP[type];
  if (label === undefined) {
    if (typeof console !== 'undefined') {
      console.warn('[fulfillmentLabel] 未登记的履约方式枚举:', type);
    }
    return '其他服务';
  }
  return label;
}

/** 履约方式下拉选项（管理后台筛选 / 编辑表单用）。 */
export const FULFILLMENT_OPTIONS = Object.keys(FULFILLMENT_LABEL_MAP).map((value) => ({
  value,
  label: FULFILLMENT_LABEL_MAP[value],
}));
