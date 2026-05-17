// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（微信小程序端）
//
// 设计目标：
// - 后端 datetime 统一为 UTC ISO（带 "+00:00" 或 "Z" 后缀）
// - 前端按设备本地时区显示
// - 兼容无时区后缀的老接口：强制按 UTC 解析，避免 8 小时偏差

function parseServerTime(iso) {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }
  const s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  const normalized = hasTz ? s : s + 'Z';
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? null : d;
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function formatDateTime(iso, pattern) {
  const p = pattern || 'YYYY-MM-DD HH:mm';
  const d = parseServerTime(iso);
  if (!d) return '';
  return p
    .replace('YYYY', String(d.getFullYear()))
    .replace('MM', pad2(d.getMonth() + 1))
    .replace('DD', pad2(d.getDate()))
    .replace('HH', pad2(d.getHours()))
    .replace('mm', pad2(d.getMinutes()))
    .replace('ss', pad2(d.getSeconds()));
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
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) return formatTime(iso);
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  const isYesterday =
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate();
  if (isYesterday) return '昨天 ' + formatTime(iso);
  if (d.getFullYear() === now.getFullYear()) {
    return formatDateTime(iso, 'MM-DD HH:mm');
  }
  return formatDate(iso);
}

module.exports = {
  parseServerTime,
  formatDateTime,
  formatDate,
  formatTime,
  formatRelativeTime,
  formatFriendlyTime,
};
