/**
 * [PRD-SLEEP-ALIGN-BP-V1 2026-06-02] 睡眠档位判定（地基工程）
 *
 * 第一版仅以「总睡眠时长（小时）」单一维度定档，简单好懂、数据最易拿到，
 * 后续可迭代深睡比例、年龄区分等维度。
 *
 *  | 档位      | 时长区间          | 颜色档 | 胶囊文案 | 卡片状态        |
 *  | 睡眠充足  | 7 ~ 9 小时        | 蓝     | 睡眠充足 | 正常，无竖条    |
 *  | 睡眠偏少  | 6 ~ 7（含6不含7） | 黄     | 睡眠偏少 | 提醒，左侧竖条  |
 *  | 睡眠不足  | < 6 小时          | 橙     | 睡眠不足 | 异常，左侧竖条  |
 *  | 睡眠偏多  | > 9 小时          | 黄     | 睡眠偏多 | 提醒，左侧竖条  |
 *
 * 边界规则：7≤x≤9 充足；6≤x<7 偏少；x<6 不足；x>9 偏多。
 *
 * 颜色档对标血压色系：
 *   - 充足 → 蓝（blue，正常色）
 *   - 偏少 / 偏多 → 黄（yellow，对标血压「偏高」预警色）
 *   - 不足 → 橙（orange，对标血压「偏高明显」严重色）
 *
 * 无数据 / 脏数据（null / NaN / <=0 / >24）时返回 null，
 * 由调用方展示「--」并隐藏状态胶囊与异常竖条。
 */

import { getBpPalette, type BpColor, type BpPalette } from './bp-level';

export type SleepColor = BpColor; // 'blue' | 'yellow' | 'orange'
export type SleepLevel = 'enough' | 'less' | 'insufficient' | 'more';

export interface SleepJudgement {
  level: SleepLevel;
  color: SleepColor;
  /** 简短状态文案，如「睡眠充足」「睡眠偏少」 */
  label: string;
  /** 胶囊完整文案（含括号说明） */
  capsuleLabel: string;
  /** 胶囊前缀图标，正常为 ✓，异常 / 提醒为 ⚠ */
  icon: string;
  /** 是否异常（需要左侧竖条提醒）：除充足外均为 true */
  abnormal: boolean;
}

/** 睡眠调色板复用血压色系，保持视觉一致 */
export function getSleepPalette(color: SleepColor): BpPalette {
  return getBpPalette(color);
}

/** 睡眠参考范围静态文案 */
export const SLEEP_NORMAL_RANGE_TEXT = '理想睡眠 7 ~ 9 小时';

/**
 * 睡眠档位判定（按总时长，单位：小时）。
 * 时长缺失（null / undefined / NaN）或脏数据（<=0 / >24）时返回 null（视为「无数据」）。
 */
export function judgeSleep(durationHours: number | null | undefined): SleepJudgement | null {
  if (durationHours == null || Number.isNaN(durationHours)) return null;
  // 脏数据：<=0 或 >24 小时，按无数据处理
  if (durationHours <= 0 || durationHours > 24) return null;

  // 睡眠不足：< 6 小时（橙色严重档）
  if (durationHours < 6) {
    return { level: 'insufficient', color: 'orange', label: '睡眠不足', capsuleLabel: '睡眠不足（橙色预警）', icon: '⚠', abnormal: true };
  }
  // 睡眠偏少：6 ≤ x < 7（黄色预警档）
  if (durationHours < 7) {
    return { level: 'less', color: 'yellow', label: '睡眠偏少', capsuleLabel: '睡眠偏少（黄色预警）', icon: '⚠', abnormal: true };
  }
  // 睡眠充足：7 ≤ x ≤ 9（蓝色正常档）
  if (durationHours <= 9) {
    return { level: 'enough', color: 'blue', label: '睡眠充足', capsuleLabel: '睡眠充足', icon: '✓', abnormal: false };
  }
  // 睡眠偏多：> 9 小时（黄色预警档）
  return { level: 'more', color: 'yellow', label: '睡眠偏多', capsuleLabel: '睡眠偏多（黄色预警）', icon: '⚠', abnormal: true };
}
