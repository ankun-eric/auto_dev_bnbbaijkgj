/**
 * [PRD-HEALTH-OPT-V1 2026-05-14] 健康档案优化 — 设计令牌
 *
 * 蓝白渐变 + 大圆角 + 柔和阴影。
 * 信息架构不变，仅替换视觉变量。
 */
export const BH_TOKENS = {
  bgPage: 'linear-gradient(180deg, #E8F4FF 0%, #F5FAFF 100%)',
  cardPrimary: 'linear-gradient(135deg, #6DB8F0 0%, #4A9EE0 100%)',
  cardSurface: '#FFFFFF',
  cardRadius: 20,
  cardShadow: '0 4px 16px rgba(74, 158, 224, 0.08)',
  accentBlue: '#4A9EE0',
  accentRed: '#F26B6B',
  accentPink: '#F08AA8',
  accentPurple: '#8B7AD9',
  accentGreen: '#3CC68A',
  accentOrange: '#F5B544',
  statusNormal: '#3CC68A',
  statusWarn: '#F5B544',
  statusDanger: '#F26B6B',
  textPrimary: '#1F2A37',
  textSecondary: '#6B7280',
  textTertiary: '#9CA3AF',
  tabHeight: 48,
  // 兼容旧 v5 API（h5 健康档案旧代码以 brand* 引用）
  brand50: '#F5FAFF',
  brand100: '#E8F4FF',
  brand200: '#CDE5FA',
  brand300: '#9CCAEE',
  brand400: '#6DB8F0',
  brand500: '#4A9EE0',
  brand600: '#3884C2',
  brand700: '#296B9F',
  brand800: '#1F4D7A',
  yellow: '#F5B544',
  warn: '#F26B6B',
  cardLineGreen: '4px solid #4A9EE0',
  cardLineYellow: '4px solid #F5B544',
  shadow: '0 4px 16px rgba(74, 158, 224, 0.08)',
  gradient: 'linear-gradient(135deg, #6DB8F0 0%, #4A9EE0 100%)',
};

export type BhTokens = typeof BH_TOKENS;
