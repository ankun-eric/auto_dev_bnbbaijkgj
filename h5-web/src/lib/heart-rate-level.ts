/**
 * [PRD-HEART-RATE-DETAIL-RULE-V1 2026-05-31] 心率详情页展示规则
 *
 * 统一标准（不区分成人/老年人）：
 *   正常范围 60–100 次/分（医院体检最通用标准）
 *
 *  | 心率测量值（次/分） | 状态标签 | 颜色档 |
 *  | < 60               | 偏慢     | 橙     |
 *  | 60 ～ 100（含边界） | 正常     | 蓝     |
 *  | > 100              | 偏快     | 橙     |
 *
 * 边界值 60 和 100 均算「正常」。
 * 无数据（心率为空）时返回 null，由调用方展示「--」并隐藏状态标签。
 */

export type HrColor = 'blue' | 'orange';
export type HrLevel = 'slow' | 'normal' | 'fast';

export interface HrJudgement {
  level: HrLevel;
  color: HrColor;
  /** 简短状态文案，如「正常」「偏快」「偏慢」 */
  label: string;
  /** 胶囊前缀图标，正常为 ✓，异常为 ⚠ */
  icon: string;
}

export interface HrPalette {
  /** 胶囊背景色 */
  capsuleBg: string;
  /** 胶囊文字色 */
  capsuleText: string;
}

const PALETTES: Record<HrColor, HrPalette> = {
  blue: {
    capsuleBg: '#3B82F6',
    capsuleText: '#FFFFFF',
  },
  orange: {
    capsuleBg: '#F97316',
    capsuleText: '#FFFFFF',
  },
};

export function getHrPalette(color: HrColor): HrPalette {
  return PALETTES[color];
}

/** 心率参考范围静态文案（硬编码，不依赖用户年龄） */
export const HR_NORMAL_RANGE_TEXT = '正常范围 60–100 次/分';

/**
 * 心率状态判定。
 * 心率缺失（null / undefined / NaN）时返回 null（视为「无数据」）。
 */
export function judgeHeartRate(value: number | null | undefined): HrJudgement | null {
  if (value == null || Number.isNaN(value)) return null;
  if (value < 60) {
    return { level: 'slow', color: 'orange', label: '偏慢', icon: '⚠' };
  }
  if (value <= 100) {
    return { level: 'normal', color: 'blue', label: '正常', icon: '✓' };
  }
  return { level: 'fast', color: 'orange', label: '偏快', icon: '⚠' };
}
