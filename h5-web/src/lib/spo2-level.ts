/**
 * [PRD-SPO2-CARD-V1 2026-06-02] 血氧（SpO₂）档位判定
 *
 * 采用常见血氧饱和度临床标准（方案 A）：
 *
 *  | 血氧值（%）   | 状态文案     | 颜色档 |
 *  | >= 95        | 正常         | 蓝     |
 *  | 90 ～ 94     | 偏低         | 橙（偏高色，黄）|
 *  | < 90         | 偏低明显     | 红（偏高明显色，橙）|
 *
 * 颜色档对标血压色系：
 *   - 正常 → 蓝（blue，正常色）
 *   - 偏低 → 黄（yellow，对标血压「偏高」预警色）
 *   - 偏低明显 → 橙（orange，对标血压「偏高明显」严重色）
 *
 * 无数据（血氧为空 / NaN）时返回 null，由调用方展示「—」并隐藏状态标签。
 */

import { getBpPalette, type BpColor, type BpPalette } from './bp-level';

export type Spo2Color = BpColor; // 'blue' | 'yellow' | 'orange'
export type Spo2Level = 'normal' | 'low' | 'severe_low';

export interface Spo2Judgement {
  level: Spo2Level;
  color: Spo2Color;
  /** 简短状态文案，如「正常」「偏低」「偏低明显」 */
  label: string;
  /** 胶囊前缀图标，正常为 ✓，异常为 ⚠ */
  icon: string;
}

/** 血氧调色板复用血压色系，保持视觉一致 */
export function getSpo2Palette(color: Spo2Color): BpPalette {
  return getBpPalette(color);
}

/** 血氧参考范围静态文案 */
export const SPO2_NORMAL_RANGE_TEXT = '正常范围 ≥ 95%';

/**
 * 血氧档位判定。
 * 血氧缺失（null / undefined / NaN / <=0）时返回 null（视为「无数据」）。
 */
export function judgeSpo2(value: number | null | undefined): Spo2Judgement | null {
  if (value == null || Number.isNaN(value) || value <= 0) return null;
  if (value >= 95) {
    return { level: 'normal', color: 'blue', label: '正常', icon: '✓' };
  }
  if (value >= 90) {
    return { level: 'low', color: 'yellow', label: '偏低', icon: '⚠' };
  }
  return { level: 'severe_low', color: 'orange', label: '偏低明显', icon: '⚠' };
}
