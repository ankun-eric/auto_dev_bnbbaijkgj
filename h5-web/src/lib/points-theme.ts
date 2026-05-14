/**
 * 积分模块视觉换肤 PRD v1.0
 * 统一的天蓝色调主题色，供积分模块 6 个页面引用，
 * 与 AI 对话首页视觉一致，消除"进入积分页面像跳到另一个 App"的割裂感。
 */

export const POINTS_THEME = {
  // 主操作色：CTA 按钮背景、重点数字、激活态 tab、签到按钮
  primary: '#0EA5E9',
  primaryDark: '#0284C7',
  primaryDisabled: '#BAE6FD',

  // 装饰渐变背景（浅）：卡片背景、banner 渐变、空状态背景、积分卡片底色
  bgGradientStart: '#F0F9FF',
  bgGradientEnd: '#DBEAFE',

  // 强调描边 / 次级元素：卡片边框、次级按钮描边、icon 描边
  borderAccent: '#7DD3FC',
  borderLight: '#BAE6FD',

  // 辅助文字色（保留）
  textSecondary: '#666666',
  textTertiary: '#999999',

  // 正向积分数字（蓝色）
  textPositive: '#0EA5E9',
  // 负向积分数字（灰色，按 PRD 不再用红色）
  textNegative: '#999999',
} as const;

// 主 CTA 按钮通用样式
export const POINTS_PRIMARY_BTN_STYLE: React.CSSProperties = {
  background: POINTS_THEME.primary,
  color: '#FFFFFF',
  borderRadius: 8,
  border: 'none',
  fontSize: 16,
  height: 44,
};

// 主 CTA 按钮渐变样式（含背景渐变，用于强调）
export const POINTS_PRIMARY_BTN_GRADIENT: React.CSSProperties = {
  background: `linear-gradient(135deg, ${POINTS_THEME.primary}, #38BDF8)`,
  color: '#FFFFFF',
  borderRadius: 8,
  border: 'none',
  fontSize: 16,
  height: 44,
};

// 次级胶囊按钮（白底蓝字蓝边）
export const POINTS_SECONDARY_BTN_STYLE: React.CSSProperties = {
  background: '#FFFFFF',
  color: POINTS_THEME.primary,
  border: `1px solid ${POINTS_THEME.primary}`,
  borderRadius: 18,
  height: 32,
  fontSize: 13,
};

// Banner 渐变背景
export const POINTS_BANNER_BG: React.CSSProperties = {
  background: `linear-gradient(135deg, ${POINTS_THEME.bgGradientStart}, ${POINTS_THEME.bgGradientEnd})`,
};
