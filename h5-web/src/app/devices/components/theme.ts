/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」页面色板。
 * 与 AI-home / h5 theme.ts 的 11 级天蓝色阶保持一致。
 */
export const DV_COLOR = {
  brand50: '#F0F9FF',
  brand100: '#E0F2FE',
  brand400: '#38BDF8',
  brand500: '#0EA5E9',
  brand600: '#0284C7',
  gradient: 'linear-gradient(135deg, #38BDF8, #0284C7)',
  danger: '#EF4444',
  dangerLight: '#FEE2E2',
  gray: '#9CA3AF',
  grayBg: '#F3F4F6',
  textPrimary: '#1F2937',
  textSecondary: '#6B7280',
  border: '#E5E7EB',
  cardBg: '#FFFFFF',
} as const;

export const BRAND_BADGE: Record<string, { bg: string; color: string }> = {
  binni: { bg: 'linear-gradient(135deg, #38BDF8, #0284C7)', color: '#FFFFFF' },
  huawei: { bg: '#C8000B', color: '#FFFFFF' },
  xiaomi: { bg: '#FF6700', color: '#FFFFFF' },
  apple: { bg: '#1D1D1F', color: '#FFFFFF' },
  other: { bg: '#6B7280', color: '#FFFFFF' },
};
