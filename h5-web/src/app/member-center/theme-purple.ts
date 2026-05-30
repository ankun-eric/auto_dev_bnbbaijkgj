/**
 * [PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心 蓝紫主题视觉资产
 *
 * 颜色资产严格对齐 PRD §8.1：
 * - 蓝紫主色 #5B6CFF
 * - 蓝紫渐变浅端 #6C7BFF
 * - 蓝紫渐变深端 #8B6CFF
 * - 深蓝紫文字 #3D4CCC
 * - 配套金色徽章 #F2C94C
 * - 配套紫色徽章 #8B5CF6
 * - 浅灰未付费底 #F4F5FA
 * - 浅灰描边 #E5E7F0
 * - 暗黑底色 #0F0F1F
 *
 * 同时给出付费/未付费/即将到期/已过期 4 态判定函数。
 */

export const PURPLE_THEME = {
  // 核心蓝紫
  PRIMARY: '#5B6CFF',
  PRIMARY_LIGHT: '#6C7BFF',
  PRIMARY_DEEP: '#8B6CFF',
  PRIMARY_DARK_TEXT: '#3D4CCC',
  // 渐变（顶部 Banner / 配额卡 / CTA 主按钮）
  BANNER_GRADIENT: 'linear-gradient(135deg, #5B6CFF 0%, #6C7BFF 50%, #8B6CFF 100%)',
  BANNER_GRADIENT_DARK: 'linear-gradient(135deg, #2E3DBF 0%, #3A4ACC 50%, #4A2EB8 100%)',
  CTA_GRADIENT: 'linear-gradient(90deg, #5B6CFF 0%, #8B6CFF 100%)',
  // 徽章
  GOLD: '#F2C94C',
  GOLD_DEEP_TEXT: '#5C3B00',
  PURPLE_BADGE: '#8B5CF6',
  GRAY_BADGE_BG: '#F1F5F9',
  GRAY_BADGE_TEXT: '#64748B',
  GRAY_BADGE_BORDER: '#E2E8F0',
  // 浅灰（未付费态/边框）
  UNPAID_BG: '#F4F5FA',
  BORDER_LIGHT: '#E5E7F0',
  // 文字
  TEXT_DARK: '#1F2937',
  TEXT_MUTED: '#6B7280',
  TEXT_GRAY: '#9CA3AF',
  // 状态条
  WARN_ORANGE: 'rgba(245,158,11,0.95)',
  WARN_ORANGE_SOLID: '#F59E0B',
  ERR_RED: '#EF4444',
  // 暗黑
  DARK_BG: '#0F0F1F',
  DARK_CARD_BG: '#1A1A2E',
} as const;

export type ThemeState =
  | 'paid_normal' // 付费态正常
  | 'paid_expiring' // 付费态 + 即将到期（30 天内）
  | 'expired' // 已过期（视觉退化为浅灰）
  | 'unpaid'; // 未付费

export type LevelKey = 'free' | 'health' | 'premium' | 'paid';

/** 计算主题态：覆盖 PRD §5.1~§5.4 的 4 档状态。 */
export function computeThemeState(input: {
  level: 'free' | 'paid';
  expireAt: string | null; // ISO 字符串
  daysLeft: number | null; // 后端 days_left 字段
  expiringSoon: boolean; // 后端 expiring_soon 字段（7 天内）
}): ThemeState {
  if (input.level === 'free') return 'unpaid';
  // 已过期：付费但 expire_at 已过
  if (input.expireAt) {
    const exp = new Date(input.expireAt).getTime();
    if (!Number.isNaN(exp) && exp < Date.now()) return 'expired';
  }
  // 即将到期：30 天内（PRD §5.2 口径）
  if (typeof input.daysLeft === 'number' && input.daysLeft >= 0 && input.daysLeft <= 30) {
    return 'paid_expiring';
  }
  // 兼容后端 expiring_soon 字段（PRD 7 天内）
  if (input.expiringSoon) return 'paid_expiring';
  return 'paid_normal';
}

/** 计算等级 key：用于决定徽章配色（金/紫/灰）。 */
export function computeLevelKey(planName: string | null | undefined, level: 'free' | 'paid'): LevelKey {
  if (level === 'free') return 'free';
  const n = (planName || '').trim();
  if (!n) return 'paid';
  // PRD §5 规则：尊享 → 金；健康 → 紫；其余付费 → 默认 paid（用紫色兜底）
  if (n.includes('尊享') || /premium|vip/i.test(n)) return 'premium';
  if (n.includes('健康') || /health|basic/i.test(n)) return 'health';
  return 'paid';
}

/** 等级徽章配色（PRD §5.5）。 */
export function getBadgePalette(key: LevelKey): { bg: string; text: string; border: string } {
  switch (key) {
    case 'premium':
      return {
        bg: `linear-gradient(90deg, ${PURPLE_THEME.GOLD} 0%, #F4D793 100%)`,
        text: PURPLE_THEME.GOLD_DEEP_TEXT,
        border: PURPLE_THEME.GOLD,
      };
    case 'health':
      return {
        bg: `linear-gradient(90deg, ${PURPLE_THEME.PURPLE_BADGE} 0%, #A78BFA 100%)`,
        text: '#FFFFFF',
        border: PURPLE_THEME.PURPLE_BADGE,
      };
    case 'paid':
      return {
        bg: `linear-gradient(90deg, ${PURPLE_THEME.PURPLE_BADGE} 0%, #A78BFA 100%)`,
        text: '#FFFFFF',
        border: PURPLE_THEME.PURPLE_BADGE,
      };
    case 'free':
    default:
      return {
        bg: PURPLE_THEME.GRAY_BADGE_BG,
        text: PURPLE_THEME.GRAY_BADGE_TEXT,
        border: PURPLE_THEME.GRAY_BADGE_BORDER,
      };
  }
}

/** CTA 主按钮文案（PRD §F5）。 */
export function getCtaText(input: {
  themeState: ThemeState;
  levelKey: LevelKey;
}): string {
  if (input.themeState === 'expired') return '立即续费，恢复权益';
  if (input.themeState === 'unpaid') return '立即开通会员';
  // 付费态
  if (input.levelKey === 'premium') return '续费 1 年';
  if (input.levelKey === 'health') return '升级到尊享会员';
  return '续费 1 年';
}

/** 主题判定是否启用蓝紫主题（vs 浅灰回退）。 */
export function isPurpleThemeEnabled(state: ThemeState): boolean {
  return state === 'paid_normal' || state === 'paid_expiring';
}

/** 进度条百分比安全计算。-1 / >=9999 视为不限（返回 null 隐藏进度条）。 */
export function calcQuotaPercent(used: number | null | undefined, total: number | null | undefined): number | null {
  if (total === null || total === undefined) return null;
  if (total === -1 || total >= 9999) return null;
  if (total <= 0) return 0;
  const u = used && used > 0 ? used : 0;
  return Math.min(100, Math.max(0, Math.round((u / total) * 100)));
}

/** 等级名称归一化展示。 */
export function normalizeLevelLabel(planName: string | null | undefined, level: 'free' | 'paid'): string {
  if (level === 'free') return '普通用户';
  return (planName || '').trim() || '会员';
}
