/**
 * [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 血糖档位判定（五档制 + 6 种测量类型）
 *
 * 五档：重度偏低 / 偏低 / 正常 / 偏高 / 重度偏高（去除"危象"字眼）
 * 6 种测量类型：空腹 / 餐后1h / 餐后2h / 睡前 / 凌晨 / 随机
 *
 * 完整阈值表（mmol/L，前闭后开）：
 *  | 测量类型 | 重度偏低 | 偏低     | 正常       | 偏高       | 重度偏高 |
 *  |----------|----------|----------|------------|------------|----------|
 *  | 空腹     | <2.8     | 2.8–3.9  | 3.9–6.1    | 6.1–7.0    | ≥7.0     |
 *  | 餐后1h   | <2.8     | 2.8–3.9  | 3.9–9.0    | 9.0–11.1   | ≥11.1    |
 *  | 餐后2h   | <2.8     | 2.8–3.9  | 3.9–7.8    | 7.8–11.1   | ≥11.1    |
 *  | 睡前     | <2.8     | 2.8–4.4  | 4.4–6.7    | 6.7–10.0   | ≥10.0    |
 *  | 凌晨     | <2.8     | 2.8–3.9  | 3.9–5.6    | 5.6–7.0    | ≥7.0     |
 *  | 随机     | <2.8     | 2.8–3.9  | 3.9–11.1   | 11.1–16.7  | ≥16.7    |
 *
 * 特殊规则：任意测量类型 <2.8 一律判为重度偏低。
 */

import { type BpColor, type BpPalette, getBpPalette } from './bp-level';

/** 5 档级别 key（与后端 LEVEL_KEY 对齐） */
export type BgLevel = 'low_critical' | 'low' | 'normal' | 'high' | 'high_critical';

/** 6 种测量类型 key */
export type BgScene =
  | 'fasting'
  | 'after_meal_1h'
  | 'after_meal_2h'
  | 'before_sleep'
  | 'dawn'
  | 'random';

export interface BgJudgement {
  level: BgLevel;
  color: BpColor;       // 复用血压配色：'blue' | 'yellow' | 'orange' | ...
  hexColor: string;     // 直接的 hex 色值
  label: string;        // 短文案：重度偏低/偏低/正常/偏高/重度偏高
  capsuleLabel: string; // 含简要说明的胶囊文案
  icon: string;
}

/** 数字场景编码（与后端 scene 字段对应） */
export const BG_SCENE_CODE: Record<BgScene, number> = {
  fasting: 1,
  after_meal_2h: 2,
  random: 3,
  before_sleep: 4,
  after_meal_1h: 5,
  dawn: 6,
};

export const BG_SCENE_LABEL: Record<BgScene, string> = {
  fasting: '空腹',
  after_meal_1h: '餐后1h',
  after_meal_2h: '餐后2h',
  before_sleep: '睡前',
  dawn: '凌晨',
  random: '随机',
};

/** 显示用的有序数组（PRD §4.1 录入页 2×3 排布） */
export const BG_SCENE_OPTIONS: BgScene[] = [
  'fasting',
  'after_meal_1h',
  'after_meal_2h',
  'before_sleep',
  'dawn',
  'random',
];

/** 兼容旧称（before_sleep 旧 key = bedtime；after_meal 旧 key = after_meal_2h） */
type LegacyScene = 'bedtime' | 'after_meal';
const LEGACY_TO_NEW: Record<LegacyScene, BgScene> = {
  bedtime: 'before_sleep',
  after_meal: 'after_meal_2h',
};

/** 中文 / 英文 / 数字编码 → BgScene */
export function normalizeScene(input: unknown): BgScene {
  if (input == null) return 'random';
  if (typeof input === 'number') {
    const found = (Object.entries(BG_SCENE_CODE) as [BgScene, number][]).find(
      ([, code]) => code === input,
    );
    return found ? found[0] : 'random';
  }
  const s = String(input).trim().toLowerCase();
  if (!s) return 'random';
  // 直接命中新 key
  if ((BG_SCENE_CODE as Record<string, number>)[s]) return s as BgScene;
  // 旧 key 兼容
  if (s in LEGACY_TO_NEW) return LEGACY_TO_NEW[s as LegacyScene];
  // 中文命中
  if (s.includes('空腹')) return 'fasting';
  if (s.includes('凌晨')) return 'dawn';
  if (s.includes('餐后1') || s.includes('餐后 1')) return 'after_meal_1h';
  if (s.includes('餐后2') || s.includes('餐后 2') || s.includes('餐后')) return 'after_meal_2h';
  if (s.includes('睡前') || s.includes('入睡')) return 'before_sleep';
  // 英文命中
  if (s.includes('fast')) return 'fasting';
  if (s.includes('dawn')) return 'dawn';
  if (s.includes('1h')) return 'after_meal_1h';
  if (s.includes('2h') || s.includes('after') || s.includes('post')) return 'after_meal_2h';
  if (s.includes('bed') || s.includes('sleep')) return 'before_sleep';
  return 'random';
}

/** 各类型阈值 (low_max, normal_max, high_max) — 与后端 SCENE_THRESHOLDS 对齐 */
const SCENE_THRESHOLDS: Record<BgScene, { lowMax: number; normalMax: number; highMax: number }> = {
  fasting:       { lowMax: 3.9, normalMax: 6.1,  highMax: 7.0  },
  after_meal_1h: { lowMax: 3.9, normalMax: 9.0,  highMax: 11.1 },
  after_meal_2h: { lowMax: 3.9, normalMax: 7.8,  highMax: 11.1 },
  before_sleep:  { lowMax: 4.4, normalMax: 6.7,  highMax: 10.0 },
  dawn:          { lowMax: 3.9, normalMax: 5.6,  highMax: 7.0  },
  random:        { lowMax: 3.9, normalMax: 11.1, highMax: 16.7 },
};

const CRISIS_LOW = 2.8;

/** 目标参考范围（用于卡片底部小字提示，PRD §4.3） */
export const BG_TARGET_RANGE: Record<BgScene, { min: number | null; max: number | null; label: string }> = {
  fasting:       { min: 3.9, max: 6.1,  label: '空腹 3.9–6.1 mmol/L' },
  after_meal_1h: { min: 3.9, max: 9.0,  label: '餐后 1h 3.9–9.0 mmol/L' },
  after_meal_2h: { min: 3.9, max: 7.8,  label: '餐后 2h 3.9–7.8 mmol/L' },
  before_sleep:  { min: 4.4, max: 6.7,  label: '睡前 4.4–6.7 mmol/L' },
  dawn:          { min: 3.9, max: 5.6,  label: '凌晨 3.9–5.6 mmol/L' },
  random:        { min: 3.9, max: 11.1, label: '随机 3.9–11.1 mmol/L' },
};

/** 五档配色与文案 */
const LEVEL_META: Record<BgLevel, { color: BpColor; hex: string; label: string; cap: string; icon: string }> = {
  low_critical:  { color: 'orange', hex: '#DC2626', label: '重度偏低', cap: '重度偏低（建议立即处理）', icon: '⚠' },
  low:           { color: 'yellow', hex: '#F59E0B', label: '偏低',     cap: '偏低（黄色提示）',           icon: '⚠' },
  normal:        { color: 'blue',   hex: '#10B981', label: '正常',     cap: '正常',                       icon: '✓' },
  high:          { color: 'yellow', hex: '#FF8C00', label: '偏高',     cap: '偏高（橙色提示）',           icon: '⚠' },
  high_critical: { color: 'orange', hex: '#DC2626', label: '重度偏高', cap: '重度偏高（建议就医）',       icon: '⚠' },
};

export function judgeBg(value: number | null | undefined, scene: BgScene | unknown): BgJudgement | null {
  if (value == null || Number.isNaN(value)) return null;
  const sc = normalizeScene(scene);
  const t = SCENE_THRESHOLDS[sc];

  let level: BgLevel;
  if (value < CRISIS_LOW) level = 'low_critical';
  else if (value < t.lowMax) level = 'low';
  else if (value < t.normalMax) level = 'normal';
  else if (value < t.highMax) level = 'high';
  else level = 'high_critical';

  const meta = LEVEL_META[level];
  return {
    level,
    color: meta.color,
    hexColor: meta.hex,
    label: meta.label,
    capsuleLabel: meta.cap,
    icon: meta.icon,
  };
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

/** [PRD-GLUCOSE-CARD-OPTIMIZE-V2] 把字符串 key 转为后端 scene 数字编码（用于 POST） */
export function sceneKeyToCode(scene: BgScene): number {
  return BG_SCENE_CODE[scene];
}
