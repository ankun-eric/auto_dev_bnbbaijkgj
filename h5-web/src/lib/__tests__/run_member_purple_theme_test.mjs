/**
 * [PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心蓝紫主题纯函数单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_member_purple_theme_test.mjs
 *
 * 覆盖：
 *  - computeThemeState：付费正常 / 付费即将到期(30天内) / 已过期 / 未付费
 *  - computeLevelKey：尊享=premium / 健康=health / 普通=free / 其他付费=paid
 *  - getCtaText：四态 + 三档付费用户文案
 *  - calcQuotaPercent：常规、零分母、不限档、负值兜底
 *  - getBadgePalette：四档徽章配色齐全
 *  - normalizeLevelLabel
 *  - isPurpleThemeEnabled
 */

// ── 直接镜像 theme-purple.ts 中的纯函数（避免 ts 依赖） ──

function computeThemeState(input) {
  if (input.level === 'free') return 'unpaid';
  if (input.expireAt) {
    const exp = new Date(input.expireAt).getTime();
    if (!Number.isNaN(exp) && exp < Date.now()) return 'expired';
  }
  if (typeof input.daysLeft === 'number' && input.daysLeft >= 0 && input.daysLeft <= 30) {
    return 'paid_expiring';
  }
  if (input.expiringSoon) return 'paid_expiring';
  return 'paid_normal';
}

function computeLevelKey(planName, level) {
  if (level === 'free') return 'free';
  const n = (planName || '').trim();
  if (!n) return 'paid';
  if (n.includes('尊享') || /premium|vip/i.test(n)) return 'premium';
  if (n.includes('健康') || /health|basic/i.test(n)) return 'health';
  return 'paid';
}

function getCtaText(input) {
  if (input.themeState === 'expired') return '立即续费，恢复权益';
  if (input.themeState === 'unpaid') return '立即开通会员';
  if (input.levelKey === 'premium') return '续费 1 年';
  if (input.levelKey === 'health') return '升级到尊享会员';
  return '续费 1 年';
}

function calcQuotaPercent(used, total) {
  if (total === null || total === undefined) return null;
  if (total === -1 || total >= 9999) return null;
  if (total <= 0) return 0;
  const u = used && used > 0 ? used : 0;
  return Math.min(100, Math.max(0, Math.round((u / total) * 100)));
}

function getBadgePalette(key) {
  switch (key) {
    case 'premium':
      return { bg: 'gold', text: '#5C3B00', border: '#F2C94C' };
    case 'health':
    case 'paid':
      return { bg: 'purple', text: '#FFFFFF', border: '#8B5CF6' };
    case 'free':
    default:
      return { bg: '#F1F5F9', text: '#64748B', border: '#E2E8F0' };
  }
}

function normalizeLevelLabel(planName, level) {
  if (level === 'free') return '普通用户';
  return (planName || '').trim() || '会员';
}

function isPurpleThemeEnabled(state) {
  return state === 'paid_normal' || state === 'paid_expiring';
}

// ── 测试 runner ──
let passed = 0;
let failed = 0;
function eq(actual, expected, label) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    passed++;
  } else {
    failed++;
    console.error(`✗ ${label}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

// 1. computeThemeState
eq(computeThemeState({ level: 'free', expireAt: null, daysLeft: null, expiringSoon: false }), 'unpaid', 'state: free → unpaid');
eq(computeThemeState({ level: 'paid', expireAt: '2099-01-01T00:00:00Z', daysLeft: 365, expiringSoon: false }), 'paid_normal', 'state: paid 一年后 → paid_normal');
eq(computeThemeState({ level: 'paid', expireAt: new Date(Date.now() + 15 * 86400000).toISOString(), daysLeft: 15, expiringSoon: false }), 'paid_expiring', 'state: paid 15天 → paid_expiring');
eq(computeThemeState({ level: 'paid', expireAt: new Date(Date.now() + 30 * 86400000).toISOString(), daysLeft: 30, expiringSoon: false }), 'paid_expiring', 'state: paid 边界 30天 → paid_expiring');
eq(computeThemeState({ level: 'paid', expireAt: new Date(Date.now() + 31 * 86400000).toISOString(), daysLeft: 31, expiringSoon: false }), 'paid_normal', 'state: paid 31天 → paid_normal');
eq(computeThemeState({ level: 'paid', expireAt: new Date(Date.now() - 86400000).toISOString(), daysLeft: -1, expiringSoon: false }), 'expired', 'state: paid 已过期 → expired');
eq(computeThemeState({ level: 'paid', expireAt: null, daysLeft: null, expiringSoon: true }), 'paid_expiring', 'state: paid 旧字段 expiring_soon=true → paid_expiring');
eq(computeThemeState({ level: 'paid', expireAt: null, daysLeft: null, expiringSoon: false }), 'paid_normal', 'state: paid 无到期数据 → paid_normal（永不到期）');

// 2. computeLevelKey
eq(computeLevelKey(null, 'free'), 'free', 'level: free');
eq(computeLevelKey('普通会员', 'free'), 'free', 'level: free 即使 planName 写了也按 level 判');
eq(computeLevelKey('尊享会员', 'paid'), 'premium', 'level: 尊享 → premium');
eq(computeLevelKey('Premium VIP', 'paid'), 'premium', 'level: Premium → premium');
eq(computeLevelKey('健康会员', 'paid'), 'health', 'level: 健康 → health');
eq(computeLevelKey('Health Plus', 'paid'), 'health', 'level: Health → health');
eq(computeLevelKey('白银会员', 'paid'), 'paid', 'level: 其他付费 → paid');
eq(computeLevelKey('', 'paid'), 'paid', 'level: 空 planName 走 paid 兜底');
eq(computeLevelKey(null, 'paid'), 'paid', 'level: null planName → paid');

// 3. getCtaText
eq(getCtaText({ themeState: 'unpaid', levelKey: 'free' }), '立即开通会员', 'cta: 未付费');
eq(getCtaText({ themeState: 'expired', levelKey: 'health' }), '立即续费，恢复权益', 'cta: 已过期');
eq(getCtaText({ themeState: 'paid_normal', levelKey: 'health' }), '升级到尊享会员', 'cta: 健康会员');
eq(getCtaText({ themeState: 'paid_normal', levelKey: 'premium' }), '续费 1 年', 'cta: 尊享会员');
eq(getCtaText({ themeState: 'paid_expiring', levelKey: 'premium' }), '续费 1 年', 'cta: 尊享会员即将到期');
eq(getCtaText({ themeState: 'paid_expiring', levelKey: 'health' }), '升级到尊享会员', 'cta: 健康即将到期');
eq(getCtaText({ themeState: 'paid_normal', levelKey: 'paid' }), '续费 1 年', 'cta: 其他付费档默认续费');

// 4. calcQuotaPercent
eq(calcQuotaPercent(23, 100), 23, 'percent: 23/100');
eq(calcQuotaPercent(0, 100), 0, 'percent: 0/100');
eq(calcQuotaPercent(100, 100), 100, 'percent: 满');
eq(calcQuotaPercent(150, 100), 100, 'percent: 超量截断为 100');
eq(calcQuotaPercent(5, -1), null, 'percent: 不限档隐藏');
eq(calcQuotaPercent(5, 9999), null, 'percent: >=9999 不限');
eq(calcQuotaPercent(5, 99999), null, 'percent: 超大 不限');
eq(calcQuotaPercent(5, null), null, 'percent: total=null 返回 null');
eq(calcQuotaPercent(null, 10), 0, 'percent: used=null → 0%');
eq(calcQuotaPercent(-3, 10), 0, 'percent: 负值 used 兜底为 0');
eq(calcQuotaPercent(5, 0), 0, 'percent: total=0 → 0%');

// 5. getBadgePalette
eq(getBadgePalette('premium').text, '#5C3B00', 'badge: premium 文字深金棕');
eq(getBadgePalette('health').text, '#FFFFFF', 'badge: health 文字白');
eq(getBadgePalette('paid').text, '#FFFFFF', 'badge: paid 文字白');
eq(getBadgePalette('free').bg, '#F1F5F9', 'badge: free 灰底');
eq(getBadgePalette('free').text, '#64748B', 'badge: free 灰字');

// 6. normalizeLevelLabel
eq(normalizeLevelLabel('健康会员', 'paid'), '健康会员', 'label: 付费透传');
eq(normalizeLevelLabel('  尊享会员  ', 'paid'), '尊享会员', 'label: 付费 trim');
eq(normalizeLevelLabel(null, 'paid'), '会员', 'label: 付费 null 兜底');
eq(normalizeLevelLabel('随便', 'free'), '普通用户', 'label: 免费固定文案');
eq(normalizeLevelLabel(null, 'free'), '普通用户', 'label: 免费 null');

// 7. isPurpleThemeEnabled
eq(isPurpleThemeEnabled('paid_normal'), true, 'purple: paid_normal');
eq(isPurpleThemeEnabled('paid_expiring'), true, 'purple: paid_expiring');
eq(isPurpleThemeEnabled('expired'), false, 'purple: expired 不启用');
eq(isPurpleThemeEnabled('unpaid'), false, 'purple: unpaid 不启用');

console.log(`\n[PRD-MEMBER-PURPLE-THEME-V1] passed=${passed}  failed=${failed}`);
if (failed > 0) {
  process.exit(1);
}
