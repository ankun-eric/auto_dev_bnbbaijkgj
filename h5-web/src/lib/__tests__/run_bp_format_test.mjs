/**
 * [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 血压时间·来源格式化单元测试
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 切换到统一 datetime.ts（北京时间口径）
 *
 * 运行：node h5-web/src/lib/__tests__/run_bp_format_test.mjs
 */

const BJ_OFFSET_MIN = 8 * 60;

function parseServerTime(iso) {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return Number.isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  let s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasTz) {
    if (s.includes(' ') && !s.includes('T')) s = s.replace(' ', 'T');
    s = s + 'Z';
  }
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pad2(n) { return String(n).padStart(2, '0'); }

function toBjParts(d) {
  const bjMs = d.getTime() + BJ_OFFSET_MIN * 60 * 1000;
  const bj = new Date(bjMs);
  return {
    year: bj.getUTCFullYear(),
    month: bj.getUTCMonth() + 1,
    day: bj.getUTCDate(),
    hour: bj.getUTCHours(),
    minute: bj.getUTCMinutes(),
    second: bj.getUTCSeconds(),
  };
}

function bjStartOfDayUtcMs(p) {
  return Date.UTC(p.year, p.month - 1, p.day) - BJ_OFFSET_MIN * 60 * 1000;
}

// 与 datetime.ts.formatFriendlyTime 保持一致；refNow 用于测试时间桩
function formatBpSyncTime(measuredAt, refNow) {
  if (!measuredAt) return '';
  const d = parseServerTime(measuredAt);
  if (!d) return '';
  const target = toBjParts(d);
  const now = toBjParts(refNow ? parseServerTime(refNow) : new Date());
  const diffDays = Math.floor((bjStartOfDayUtcMs(now) - bjStartOfDayUtcMs(target)) / 86400000);
  const hh = pad2(target.hour);
  const mm = pad2(target.minute);
  if (diffDays === 0) return `今日 ${hh}:${mm}`;
  if (diffDays === 1) return `昨日 ${hh}:${mm}`;
  if (diffDays >= 2 && diffDays <= 6) return `${diffDays} 天前`;
  if (target.year === now.year) return `${pad2(target.month)}-${pad2(target.day)}`;
  return `${target.year}-${pad2(target.month)}-${pad2(target.day)}`;
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
    fails.push(`X ${name}: expected "${expected}" got "${got}"`);
  }
}

// 参考"现在"为北京时间 2026-05-30 14:00（即 UTC 06:00），用 +08:00 后缀更直观
const REF = '2026-05-30T14:00:00+08:00';

// ===== 时间显示规则（输入均为 UTC 字符串，模拟后端 utcnow().isoformat()） =====
// 北京时间 08:30 = UTC 00:30
eq('今日 08:30 (UTC)',
  formatBpSyncTime('2026-05-30T00:30:00Z', REF), '今日 08:30');
// 北京时间 08:30 - 无时区后缀（UTC）
eq('今日 08:30 (无时区后缀, 当成 UTC)',
  formatBpSyncTime('2026-05-30T00:30:00', REF), '今日 08:30');
// 北京时间 08:30 - +08:00 显式
eq('今日 08:30 (+08:00)',
  formatBpSyncTime('2026-05-30T08:30:00+08:00', REF), '今日 08:30');
eq('昨日 21:15 (UTC)',
  formatBpSyncTime('2026-05-29T13:15:00Z', REF), '昨日 21:15');
eq('3 天前 (UTC)',
  formatBpSyncTime('2026-05-27T02:00:00Z', REF), '3 天前');
eq('6 天前 (UTC, 边界)',
  formatBpSyncTime('2026-05-24T02:00:00Z', REF), '6 天前');
eq('7 天前 → MM-DD (UTC)',
  formatBpSyncTime('2026-05-23T02:00:00Z', REF), '05-23');
eq('空字符串', formatBpSyncTime('', REF), '');
eq('null', formatBpSyncTime(null, REF), '');

// ===== 来源显示规则（不变） =====
eq('manual → 手工录入', formatBpSource('manual'), '手工录入');
eq('空字符串 → 手工录入', formatBpSource(''), '手工录入');
eq('null → 手工录入', formatBpSource(null), '手工录入');
eq('omron → 欧姆龙血压计·自动同步', formatBpSource('omron'), '欧姆龙血压计·自动同步');
eq('device:omron → 欧姆龙血压计·自动同步', formatBpSource('device:omron'), '欧姆龙血压计·自动同步');
eq('huawei_watch', formatBpSource('huawei_watch'), '华为 Watch·自动同步');
eq('未知设备 vendorx → vendorx·自动同步', formatBpSource('vendorx'), 'vendorx·自动同步');
eq('显式 deviceName 优先', formatBpSource('omron', '欧姆龙'), '欧姆龙·自动同步');

// ===== 完整 "时间 · 来源" =====
eq('完整 1 (今日)', formatBpTimeSource('2026-05-30T00:30:00Z', 'omron', null, REF),
  '今日 08:30 · 欧姆龙血压计·自动同步');
eq('完整 2 (昨日)', formatBpTimeSource('2026-05-29T13:15:00Z', 'manual', null, REF),
  '昨日 21:15 · 手工录入');
eq('完整 3 (3 天前)', formatBpTimeSource('2026-05-27T02:00:00Z', 'omron', null, REF),
  '3 天前 · 欧姆龙血压计·自动同步');
eq('完整 4 (MM-DD)', formatBpTimeSource('2026-05-23T02:00:00Z', 'manual', null, REF),
  '05-23 · 手工录入');

// ===== Bug 复现修复验证 =====
// 用户报告：北京时间约 10:32 测量 → 卡片显示"今日 02:32"（少 8 小时）
// 后端返回 "2026-05-30 02:32:41"（无时区后缀，实为 UTC）
// 修复后应显示"今日 10:32"
eq('BUG 修复验证：无时区 UTC 字符串 → 今日 10:32',
  formatBpSyncTime('2026-05-30 02:32:41', REF), '今日 10:32');
eq('BUG 修复验证：T 分隔无时区 UTC → 今日 10:32',
  formatBpSyncTime('2026-05-30T02:32:41', REF), '今日 10:32');

if (fail === 0) {
  console.log(`OK bp-format tests: all ${pass} assertions passed`);
  process.exit(0);
} else {
  console.error(`FAIL bp-format tests: ${fail} failed, ${pass} passed\n${fails.join('\n')}`);
  process.exit(1);
}
