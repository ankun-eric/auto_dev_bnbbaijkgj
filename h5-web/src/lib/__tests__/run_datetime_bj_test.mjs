/**
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 时间显示统一治理（北京时间口径）单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_datetime_bj_test.mjs
 *
 * 覆盖：
 *   - parseServerTime：兼容带/不带时区后缀字符串
 *   - formatFriendlyTime：北京时间口径输出"今日/昨日/X 天前/MM-DD/YYYY-MM-DD"
 *   - formatFullTime：北京时间 YYYY-MM-DD HH:mm:ss
 *   - 海外/UTC 浏览器时区下，结果仍为北京时间（不依赖设备时区）
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

function formatFullTime(iso) {
  const d = parseServerTime(iso);
  if (!d) return '';
  const p = toBjParts(d);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)} ${pad2(p.hour)}:${pad2(p.minute)}:${pad2(p.second)}`;
}

function formatFriendlyTimeWithRef(iso, refNowDate) {
  const d = parseServerTime(iso);
  if (!d) return '';
  const target = toBjParts(d);
  const now = toBjParts(refNowDate);
  const diffDays = Math.floor((bjStartOfDayUtcMs(now) - bjStartOfDayUtcMs(target)) / 86400000);
  const hh = pad2(target.hour);
  const mm = pad2(target.minute);
  if (diffDays === 0) return `今日 ${hh}:${mm}`;
  if (diffDays === 1) return `昨日 ${hh}:${mm}`;
  if (diffDays >= 2 && diffDays <= 6) return `${diffDays} 天前`;
  if (target.year === now.year) return `${pad2(target.month)}-${pad2(target.day)}`;
  return `${target.year}-${pad2(target.month)}-${pad2(target.day)}`;
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

// === 关键场景：北京时间 10:32 测量，但后端返回 UTC 02:32 ===
// 后端 datetime.utcnow().isoformat() 不带时区后缀
eq(
  'BUG-CASE: 无时区后缀 "2026-05-30 02:32:41"（UTC）→ 应解析为北京时间 10:32',
  formatFullTime('2026-05-30 02:32:41'),
  '2026-05-30 10:32:41',
);
eq(
  'BUG-CASE: 无时区后缀 "2026-05-30T02:32:41"（UTC）→ 应解析为北京时间 10:32',
  formatFullTime('2026-05-30T02:32:41'),
  '2026-05-30 10:32:41',
);
eq(
  'Z 后缀 "2026-05-30T02:32:41Z" → 北京时间 10:32',
  formatFullTime('2026-05-30T02:32:41Z'),
  '2026-05-30 10:32:41',
);
eq(
  '+08:00 后缀 "2026-05-30T10:32:41+08:00" → 北京时间 10:32',
  formatFullTime('2026-05-30T10:32:41+08:00'),
  '2026-05-30 10:32:41',
);

// === friendlyTime ===
// 参考"现在"为北京时间 2026-05-30 14:00（即 UTC 06:00）
const refNow = new Date('2026-05-30T06:00:00Z');

eq('今日（同一天，UTC 字符串）',
  formatFriendlyTimeWithRef('2026-05-30T02:32:41Z', refNow), '今日 10:32');
eq('今日（无时区后缀）',
  formatFriendlyTimeWithRef('2026-05-30 02:32:41', refNow), '今日 10:32');
eq('今日（+08:00 后缀）',
  formatFriendlyTimeWithRef('2026-05-30T10:32:41+08:00', refNow), '今日 10:32');
eq('昨日（北京时间 23:50）',
  formatFriendlyTimeWithRef('2026-05-29T15:50:00Z', refNow), '昨日 23:50');
eq('3 天前',
  formatFriendlyTimeWithRef('2026-05-27T02:00:00Z', refNow), '3 天前');
eq('6 天前（边界，仍是 X 天前）',
  formatFriendlyTimeWithRef('2026-05-24T02:00:00Z', refNow), '6 天前');
eq('7 天前 → MM-DD',
  formatFriendlyTimeWithRef('2026-05-23T02:00:00Z', refNow), '05-23');
eq('跨年 → YYYY-MM-DD',
  formatFriendlyTimeWithRef('2025-12-31T02:00:00Z', refNow), '2025-12-31');
eq('空 → 空字符串',
  formatFriendlyTimeWithRef('', refNow), '');
eq('null → 空字符串',
  formatFriendlyTimeWithRef(null, refNow), '');

// === 跨日临界 ===
// 北京时间 23:50 测量（UTC 15:50）；5 分钟后看（北京时间 23:55，UTC 15:55）→ 今日
eq('北京时间 23:50 -> 5 分钟后看（仍同日）',
  formatFriendlyTimeWithRef('2026-05-30T15:50:00Z', new Date('2026-05-30T15:55:00Z')),
  '今日 23:50');
// 北京时间 23:50 测量（UTC 15:50）；次日 0:10 看（北京时间 00:10，UTC 16:10）→ 昨日
eq('北京时间 23:50 -> 次日 0:10 看（昨日）',
  formatFriendlyTimeWithRef('2026-05-30T15:50:00Z', new Date('2026-05-30T16:10:00Z')),
  '昨日 23:50');

// === 海外/UTC 时区不变性 ===
// 模拟"海外服务端"返回时间字符串。无论调用环境时区如何，输出都按北京时间。
// 注意：Node.js 默认按本机时区运行；这里我们的 toBjParts 是按 UTC 偏移 +480 分钟纯算，
// 与本机时区无关，因此结果在任何时区下一致。
eq('UTC 输入 02:32 → 北京 10:32',
  formatFullTime('2026-05-30T02:32:41Z'), '2026-05-30 10:32:41');
eq('UTC 输入 23:00 跨日 → 北京次日 07:00',
  formatFullTime('2026-05-29T23:00:00Z'), '2026-05-30 07:00:00');

// === 闰年 / 跨月 ===
eq('闰年 2024-02-29 12:00:00 UTC → 北京 20:00',
  formatFullTime('2024-02-29T12:00:00Z'), '2024-02-29 20:00:00');

if (fail === 0) {
  console.log(`OK datetime-bj tests: all ${pass} assertions passed`);
  process.exit(0);
} else {
  console.error(`FAIL datetime-bj tests: ${fail} failed, ${pass} passed\n${fails.join('\n')}`);
  process.exit(1);
}
