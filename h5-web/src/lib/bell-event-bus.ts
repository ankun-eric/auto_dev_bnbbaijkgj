/**
 * [PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点 / 今日待办胶囊 全局事件总线
 *
 * 任何会影响铃铛红点的操作完成后，应主动 publish('badge:refresh') 触发所有订阅者
 * （顶部铃铛、AI 首页今日待办胶囊、抽屉内未关闭时）实时同步刷新。
 *
 * 浏览器场景下基于 window 事件实现，跨 hooks / 组件均可订阅。
 *
 * 事件目录：
 *   - badge:refresh         任何会影响红点的操作完成
 *   - medication:checked    用药打卡完成
 *   - order:status_changed  订单支付/预约/核销/收货完成
 */

export type BellBusEvent =
  | 'badge:refresh'
  | 'medication:checked'
  | 'order:status_changed';

const PREFIX = 'bell-bus:';

export function publishBellEvent(name: BellBusEvent, detail?: unknown): void {
  if (typeof window === 'undefined') return;
  try {
    window.dispatchEvent(new CustomEvent(PREFIX + name, { detail }));
    // badge:refresh 是兜底总线：任何子事件都顺带触发一次
    if (name !== 'badge:refresh') {
      window.dispatchEvent(new CustomEvent(PREFIX + 'badge:refresh', { detail }));
    }
  } catch {
    /* ignore */
  }
}

export function subscribeBellEvent(
  name: BellBusEvent,
  handler: (detail: unknown) => void,
): () => void {
  if (typeof window === 'undefined') return () => {};
  const fn = (e: Event) => {
    try {
      handler((e as CustomEvent).detail);
    } catch {
      /* ignore */
    }
  };
  window.addEventListener(PREFIX + name, fn);
  return () => window.removeEventListener(PREFIX + name, fn);
}
