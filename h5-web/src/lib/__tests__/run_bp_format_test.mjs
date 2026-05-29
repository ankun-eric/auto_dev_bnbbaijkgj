/**
 * [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 血压时间·来源格式化单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_bp_format_test.mjs
 *
 * 覆盖 PRD §3.3：
 *   - 时间显示规则（今日 / 昨日 / X 天前 / MM-dd）
 *   - 来源显示规则（手工录入 / {设备名}·自动同步）
 *   - 完整 "时间 · 来源" 单行
 */

// 内联实现（与 h5-web/src/app/health-metric/[type]/page.tsx 保持一致）
function formatBpSyncTime(measuredAt, refNow) {
  if (!measuredAt) return '';
  const d = new Date(measuredAt);
  if (Number.isNaN(d.getTime())) return '';
  const today = refNow ? new Date(refNow) : new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const startD = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.floor((startToday - startD) / 86400000);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (diffDays === 0) return `今日 ${hh}:${mm}`;
  if (diffDays === 1) return `昨日 ${hh}:${mm}`;
  if (diffDays >= 2 && diffDays <= 7) return `${diffDays} 天前`;
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${mo}-${dd}`;
}

function formatBpSource(source, deviceName) {
  if (!source) return '手工录入';
  const s = String(source).trim();
  if (!s || s === 'manual') return '手工录入';
  const dn = (deviceName || '').trim();
  if (dn) return `${dn}·自动同步`;
  const last = s.split(':').pop() || s;
  const map = {
    omron: '欧姆龙血压计',
    huawei_watch: '华为 Watch',
    xiaomi_band: '小米手环',
    bp_meter: '血压计',
  };
  return `${map[last] || last}·自动同步`;
}

function formatBpTimeSource(measuredAt, source, deviceName, refNow) {
  const t = formatBpSyncTime(measuredAt, refNow);
  const s = formatBpSource(source, deviceName);
  if (!t) return s;
  return `${t} · ${s}`;
}

let pass = 0, fail = 0;
const fails = [];
function eq(name, got, expected) {
  if (got === expected) pass++;
  else {
    fail++;
    fails.push(`✗ ${name}: expected "${expected}" got "${got}"`);
  }
}

// 固定参考时间：2026-05-30 14:00
const REF = '2026-05-30T14:00:00';

// 时间显示规则
eq('今日 08:30',
  formatBpSyncTime('2026-05-30T08:30:00', REF), '今日 08:30');
eq('昨日 21:15',
  formatBpSyncTime('2026-05-29T21:15:00', REF), '昨日 21:15');
eq('3 天前',
  formatBpSyncTime('2026-05-27T10:00:00', REF), '3 天前');
eq('7 天前',
  formatBpSyncTime('2026-05-23T10:00:00', REF), '7 天前');
eq('超过 7 天 → MM-dd',
  formatBpSyncTime('2026-05-22T10:00:00', REF), '05-22');
eq('空字符串',
  formatBpSyncTime('', REF), '');
eq('null',
  formatBpSyncTime(null, REF), '');

// 来源显示规则
eq('manual → 手工录入', formatBpSource('manual'), '手工录入');
eq('空字符串 → 手工录入', formatBpSource(''), '手工录入');
eq('null → 手工录入', formatBpSource(null), '手工录入');
eq('omron → 欧姆龙血压计·自动同步', formatBpSource('omron'), '欧姆龙血压计·自动同步');
eq('device:omron → 欧姆龙血压计·自动同步', formatBpSource('device:omron'), '欧姆龙血压计·自动同步');
eq('huawei_watch', formatBpSource('huawei_watch'), '华为 Watch·自动同步');
eq('未知设备 vendorx → vendorx·自动同步', formatBpSource('vendorx'), 'vendorx·自动同步');
eq('显式 deviceName 优先', formatBpSource('omron', '欧姆龙'), '欧姆龙·自动同步');

// 完整 "时间 · 来源"
eq('完整 1', formatBpTimeSource('2026-05-30T08:30:00', 'omron', null, REF),
  '今日 08:30 · 欧姆龙血压计·自动同步');
eq('完整 2', formatBpTimeSource('2026-05-29T21:15:00', 'manual', null, REF),
  '昨日 21:15 · 手工录入');
eq('完整 3', formatBpTimeSource('2026-05-27T10:00:00', 'omron', null, REF),
  '3 天前 · 欧姆龙血压计·自动同步');
eq('完整 4', formatBpTimeSource('2026-05-22T10:00:00', 'manual', null, REF),
  '05-22 · 手工录入');

if (fail === 0) {
  console.log(`✓ bp-format tests: all ${pass} assertions passed`);
  process.exit(0);
} else {
  console.error(`✗ bp-format tests: ${fail} failed, ${pass} passed\n${fails.join('\n')}`);
  process.exit(1);
}
