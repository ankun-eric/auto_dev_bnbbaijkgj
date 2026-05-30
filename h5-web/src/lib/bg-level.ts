/**
 * [PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30] 血糖档位判定
 *
 * 依据 PRD §3.2 提供的医学标准（mmol/L）：
 *
 *  | 测量类型   | 偏低     | 正常        | 偏高        | 危象              |
 *  |------------|----------|-------------|-------------|-------------------|
 *  | 空腹       | <3.9     | 3.9–6.1     | 6.1–7.0     | >7.0 或 <2.8      |
 *  | 餐后 2h    | <3.9     | 3.9–7.8     | 7.8–11.1    | >11.1 或 <2.8     |
 *  | 睡前       | <4.4     | 4.4–6.7     | 6.7–10.0    | >10.0 或 <2.8     |
 *  | 随机       | <3.9     | 3.9–11.1    | 11.1–16.7   | >16.7 或 <2.8     |
 *
 * 视觉档位与血压保持一致：
 *   - normal → blue
 *   - low / high → yellow
 *   - crisis → orange（严重档）
 */

import { type BpColor, type BpPalette, getBpPalette } from './bp-level';

export type BgLevel = 'low' | 'normal' | 'high' | 'crisis';
export type BgScene = 'fasting' | 'after_meal' | 'bedtime' | 'random';

export interface BgJudgement {
  level: BgLevel;
  color: BpColor; // 与血压共用配色
  label: string; // 简短文案：偏低/正常/偏高/危象
  capsuleLabel: string; // 含括号说明文案
  icon: string;
}

/** 数字场景编码（与后端 scene 字段对应：1 空腹 / 2 餐后 / 3 随机 / 4 睡前） */
export const BG_SCENE_CODE: Record<BgScene, number> = {
  fasting: 1,
  after_meal: 2,
  random: 3,
  bedtime: 4,
};

export const BG_SCENE_LABEL: Record<BgScene, string> = {
  fasting: '空腹',
  after_meal: '餐后2h',
  bedtime: '睡前',
  random: '随机',
};

/** 中文 / 英文 / 数字编码 → BgScene */
export function normalizeScene(input: unknown): BgScene {
  if (input == null) return 'random';
  if (typeof input === 'number') {
    if (input === 1) return 'fasting';
    if (input === 2) return 'after_meal';
    if (input === 4) return 'bedtime';
    return 'random';
  }
  const s = String(input).trim().toLowerCase();
  if (!s) return 'random';
  if (s.includes('fast') || s.includes('空腹')) return 'fasting';
  if (s.includes('after') || s.includes('post') || s.includes('餐后') || s.includes('餐 后')) return 'after_meal';
  if (s.includes('bed') || s.includes('sleep') || s.includes('睡前') || s.includes('睡 前')) return 'bedtime';
  return 'random';
}

/** 目标参考范围（来自 PRD §4.3） */
export const BG_TARGET_RANGE: Record<BgScene, { min: number | null; max: number | null; label: string }> = {
  fasting: { min: 3.9, max: 6.1, label: '空腹 3.9–6.1 mmol/L' },
  after_meal: { min: null, max: 7.8, label: '餐后 2h < 7.8 mmol/L' },
  bedtime: { min: 4.4, max: 6.7, label: '睡前 4.4–6.7 mmol/L' },
  random: { min: 3.9, max: 11.1, label: '随机 3.9–11.1 mmol/L' },
};

interface SceneThresholds {
  /** 严重低糖（危象）阈值，<= 该值算危象 */
  crisisLow: number;
  /** 偏低上限（不含），值 < 该值且 >= crisisLow 算偏低 */
  lowMax: number;
  /** 正常上限（不含） */
  normalMax: number;
  /** 偏高上限（不含），>=该值算危象 */
  highMax: number;
}

const SCENE_THRESHOLDS: Record<BgScene, SceneThresholds> = {
  fasting: { crisisLow: 2.8, lowMax: 3.9, normalMax: 6.1, highMax: 7.0 },
  after_meal: { crisisLow: 2.8, lowMax: 3.9, normalMax: 7.8, highMax: 11.1 },
  bedtime: { crisisLow: 2.8, lowMax: 4.4, normalMax: 6.7, highMax: 10.0 },
  random: { crisisLow: 2.8, lowMax: 3.9, normalMax: 11.1, highMax: 16.7 },
};

export function judgeBg(value: number | null | undefined, scene: BgScene | unknown): BgJudgement | null {
  if (value == null || Number.isNaN(value)) return null;
  const sc = normalizeScene(scene);
  const t = SCENE_THRESHOLDS[sc];
  if (value < t.crisisLow) {
    return { level: 'crisis', color: 'orange', label: '危象', capsuleLabel: '低糖危象（橙色预警）', icon: '⚠' };
  }
  if (value < t.lowMax) {
    return { level: 'low', color: 'yellow', label: '偏低', capsuleLabel: '偏低（黄色预警）', icon: '⚠' };
  }
  if (value < t.normalMax) {
    return { level: 'normal', color: 'blue', label: '正常', capsuleLabel: '正常', icon: '✓' };
  }
  if (value < t.highMax) {
    return { level: 'high', color: 'yellow', label: '偏高', capsuleLabel: '偏高（黄色预警）', icon: '⚠' };
  }
  return { level: 'crisis', color: 'orange', label: '危象', capsuleLabel: '高糖危象（橙色预警）', icon: '⚠' };
}

/** 复用血压调色板，保持视觉一致 */
export function getBgPalette(color: BpColor): BpPalette {
  return getBpPalette(color);
}

/** 测试手段胶囊文案：设备测量 / 手动录入 */
export function formatBgSourceCapsule(source?: string | null): { label: string; isDevice: boolean } {
  const s = (source || '').trim().toLowerCase();
  if (!s || s === 'manual' || s === '手动' || s === '手动录入') {
    return { label: '手动录入', isDevice: false };
  }
  return { label: '设备测量', isDevice: true };
}
