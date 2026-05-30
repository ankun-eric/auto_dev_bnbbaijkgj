// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（微信小程序端）
// [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 全局固定北京时间口径，新增 formatFriendlyTime / formatFullTime
//
// 后端 datetime 应统一以 UTC 返回；老接口若无时区后缀，前端按 UTC 解析后转为北京时间显示。
// 与设备本地时区无关，全局以东八区为口径。

const BJ_OFFSET_MIN = 8 * 60;

function parseServerTime(iso) {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }
  let s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasTz) {
    if (s.indexOf(' ') >= 0 && s.indexOf('T') < 0) s = s.replace(' ', 'T');
    s = s + 'Z';
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

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

function formatDateTime(iso, pattern) {
  const p = pattern || 'YYYY-MM-DD HH:mm';
  const d = parseServerTime(iso);
  if (!d) return '';
  const bp = toBjParts(d);
  return p
    .replace('YYYY', String(bp.year))
    .replace('MM', pad2(bp.month))
    .replace('DD', pad2(bp.day))
    .replace('HH', pad2(bp.hour))
    .replace('mm', pad2(bp.minute))
    .replace('ss', pad2(bp.second));
}

function formatFullTime(iso) {
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm:ss');
}

function formatDate(iso) {
  return formatDateTime(iso, 'YYYY-MM-DD');
}

function formatTime(iso) {
  return formatDateTime(iso, 'HH:mm');
}

function formatRelativeTime(iso) {
  const d = parseServerTime(iso);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return formatDateTime(iso);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return '刚刚';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  if (day < 30) return `${day} 天前`;
  return formatDate(iso);
}

function formatFriendlyTime(iso) {
  const d = parseServerTime(iso);
  if (!d) return '';
  const target = toBjParts(d);
  const now = toBjParts(new Date());
  const diffDays = Math.floor(
    (bjStartOfDayUtcMs(now) - bjStartOfDayUtcMs(target)) / 86400000,
  );
  const hh = pad2(target.hour);
  const mm = pad2(target.minute);
  if (diffDays === 0) return '今日 ' + hh + ':' + mm;
  if (diffDays === 1) return '昨日 ' + hh + ':' + mm;
  if (diffDays >= 2 && diffDays <= 6) return diffDays + ' 天前';
  if (target.year === now.year) return pad2(target.month) + '-' + pad2(target.day);
  return target.year + '-' + pad2(target.month) + '-' + pad2(target.day);
}

module.exports = {
  parseServerTime,
  formatDateTime,
  formatFullTime,
  formatDate,
  formatTime,
  formatRelativeTime,
  formatFriendlyTime,
};
