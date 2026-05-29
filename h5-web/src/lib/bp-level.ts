/**
 * [BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 血压档位判定
 *
 * 依据《中国高血压防治指南（最新版）》通用医学标准
 * 判定原则：收缩压与舒张压「或」关系——任一项落入更高档位即按更高档位定级
 *
 *  | 档位                  | SBP        | 关系 | DBP        | 颜色档 | 文案         |
 *  | 偏低（严重）          | <90        | 或  | <60        | 橙    | 偏低         |
 *  | 正常                  | 90~119     | 且  | 60~79      | 蓝    | 正常         |
 *  | 正常高值（轻度偏高）  | 120~139    | 或  | 80~89      | 黄    | 轻度偏高     |
 *  | 1 级高血压（中度偏高）| 140~159    | 或  | 90~99      | 黄    | 中度偏高     |
 *  | 2 级及以上            | >=160      | 或  | >=100      | 橙    | 严重偏高     |
 *
 * 注：「偏低」与「严重偏高」均落在橙色严重档（低血压同样具有医学风险）。
 */

export type BpColor = 'blue' | 'yellow' | 'orange';
export type BpLevel = 'low' | 'normal' | 'mild_high' | 'mid_high' | 'severe_high';

export interface BpJudgement {
  level: BpLevel;
  color: BpColor;
  /** 简短文案，如「正常」「轻度偏高」 */
  label: string;
  /** 胶囊完整文案（含括号说明），如「轻度偏高（黄色预警）」 */
  capsuleLabel: string;
  /** 胶囊前缀图标，未达正常档为 ⚠ */
  icon: string;
}

export interface BpPalette {
  /** 卡片背景色 */
  cardBg: string;
  /** 主文字色（数值/同步信息） */
  text: string;
  /** 胶囊背景色 */
  capsuleBg: string;
  /** 胶囊文字色 */
  capsuleText: string;
  /** 描边色 */
  border: string;
}

const PALETTES: Record<BpColor, BpPalette> = {
  blue: {
    cardBg: '#E8F2FF',
    text: '#1B4DA0',
    capsuleBg: '#3B82F6',
    capsuleText: '#FFFFFF',
    border: '#BFDBFE',
  },
  yellow: {
    cardBg: '#FFF4D1',
    text: '#7A4A00',
    capsuleBg: '#F5B73D',
    capsuleText: '#FFFFFF',
    border: '#FCD980',
  },
  orange: {
    cardBg: '#FFE2C7',
    text: '#8A3A00',
    capsuleBg: '#F97316',
    capsuleText: '#FFFFFF',
    border: '#FDBA74',
  },
};

export function getBpPalette(color: BpColor): BpPalette {
  return PALETTES[color];
}

/**
 * 血压档位判定。
 * sbp/dbp 任一缺失时返回 null（视为"无数据"）。
 */
export function judgeBp(sbp: number | null | undefined, dbp: number | null | undefined): BpJudgement | null {
  if (sbp == null || dbp == null || Number.isNaN(sbp) || Number.isNaN(dbp)) return null;
  // 严重偏高：SBP>=160 或 DBP>=100
  if (sbp >= 160 || dbp >= 100) {
    return { level: 'severe_high', color: 'orange', label: '严重偏高', capsuleLabel: '严重偏高（橙色预警）', icon: '⚠' };
  }
  // 偏低：SBP<90 或 DBP<60（统一按严重档处理）
  if (sbp < 90 || dbp < 60) {
    return { level: 'low', color: 'orange', label: '偏低', capsuleLabel: '偏低（橙色预警）', icon: '⚠' };
  }
  // 中度偏高：SBP>=140 或 DBP>=90
  if (sbp >= 140 || dbp >= 90) {
    return { level: 'mid_high', color: 'yellow', label: '中度偏高', capsuleLabel: '中度偏高（黄色预警）', icon: '⚠' };
  }
  // 轻度偏高：SBP>=120 或 DBP>=80
  if (sbp >= 120 || dbp >= 80) {
    return { level: 'mild_high', color: 'yellow', label: '轻度偏高', capsuleLabel: '轻度偏高（黄色预警）', icon: '⚠' };
  }
  // 正常：SBP 90~119 且 DBP 60~79
  return { level: 'normal', color: 'blue', label: '正常', capsuleLabel: '正常', icon: '✓' };
}
