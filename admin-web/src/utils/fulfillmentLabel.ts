/**
 * 履约方式中英文映射统一字典（全端共用同一份口径）。
 *
 * 后端枚举值 → 中文标签（与 FulfillmentType 枚举严格 1:1 对应）：
 *   delivery  → 快递配送（科技蓝角标）
 *   in_store  → 到店服务（暖橙角标）
 *   on_site   → 上门服务（生机绿角标 #10B981）
 *   virtual   → 虚拟商品（尊贵紫角标）
 *
 * 注意：
 * - 字典内部使用对象字面量保留键的插入顺序，下拉默认按
 *   delivery / in_store / on_site / virtual 顺序展示。
 * - 历史 to_store 映射为僵尸条目（后端从未包含此枚举），已彻底删除。
 *
 * 兜底：未登记的新枚举值统一显示"其他服务"，避免回显英文原文。
 */

export const FULFILLMENT_LABEL_MAP: Record<string, string> = {
  delivery: '快递配送',
  in_store: '到店服务',
  on_site: '上门服务',
  virtual: '虚拟商品',
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
