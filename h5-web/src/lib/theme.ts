/**
 * PRD-442「宾尼小康」品牌色 token —— H5 端 TS 引用版
 * 单一真相源：design-system/design-tokens.json
 * 色值与 h5-web/src/app/globals.css :root 完全一致
 */
export const THEME = {
  primary: '#0EA5E9',          // brand-500（宾尼小康主色）
  primaryHover: '#0284C7',     // brand-600
  primaryLight: '#E0F2FE',     // brand-100
  background: '#F0F9FF',
  cardBg: '#FFFFFF',
  textPrimary: '#1F2937',
  textSecondary: '#6B7280',
  divider: '#E5E7EB',
  gradient: 'linear-gradient(135deg, #38BDF8, #0284C7)',  // gradient-primary-btn
} as const;

export const GRADIENTS = {
  topbar: 'linear-gradient(180deg, #F0F9FF 0%, #DBEAFE 100%)',
  primaryBtn: 'linear-gradient(135deg, #38BDF8, #0284C7)',
  userBubble: 'linear-gradient(135deg, #38BDF8, #0284C7)',
  heroDark: 'linear-gradient(135deg, #0C4A6E, #0284C7)',
  coupon: 'linear-gradient(135deg, #0284C7, #075985)',
} as const;

export const SHADOWS = {
  card: '0 2px 12px rgba(14,165,233,0.08)',
  primaryBtn: '0 4px 12px rgba(2,132,199,0.3)',
} as const;

/** 11 级天蓝色阶 hex（与 globals.css --color-brand-* 严格对齐） */
export const BRAND = {
  50: '#F0F9FF',
  100: '#E0F2FE',
  150: '#DBEAFE',
  200: '#BAE6FD',
  300: '#7DD3FC',
  400: '#38BDF8',
  500: '#0EA5E9',
  600: '#0284C7',
  700: '#0369A1',
  800: '#075985',
  900: '#0C4A6E',
} as const;
