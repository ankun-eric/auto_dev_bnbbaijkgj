// [日期时区简化 2026-06-06] 简化版时间格式化工具（小程序端）
// 后端统一返回北京时间 "YYYY-MM-DD HH:mm:ss"，前端直接解析即可。

function pad2(n) {
  return String(n).padStart(2, '0');
}

function parseServerTime(iso) {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }
  var d = new Date(String(iso));
  return isNaN(d.getTime()) ? null : d;
}

function formatDateTime(iso, pattern) {
  var p = pattern || 'YYYY-MM-DD HH:mm';
  var d = parseServerTime(iso);
  if (!d) return '';
  return p
    .replace('YYYY', String(d.getFullYear()))
    .replace('MM', pad2(d.getMonth() + 1))
    .replace('DD', pad2(d.getDate()))
    .replace('HH', pad2(d.getHours()))
    .replace('mm', pad2(d.getMinutes()))
    .replace('ss', pad2(d.getSeconds()));
}

function formatFullTime(iso) {
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm:ss');
}

function formatDate(iso) {
  return formatDateTime(iso, 'YYYY-MM-DD');
}

function formatTime(iso) {
  var d = parseServerTime(iso);
  if (!d) return '';
  return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
}

function formatRelativeTime(iso) {
  var d = parseServerTime(iso);
  if (!d) return '';
  var diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return formatDateTime(iso);
  var sec = Math.floor(diffMs / 1000);
  if (sec < 60) return '刚刚';
  var min = Math.floor(sec / 60);
  if (min < 60) return min + ' 分钟前';
  var hour = Math.floor(min / 60);
  if (hour < 24) return hour + ' 小时前';
  var day = Math.floor(hour / 24);
  if (day < 30) return day + ' 天前';
  return formatDate(iso);
}

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function formatFriendlyTime(iso) {
  var d = parseServerTime(iso);
  if (!d) return '';
  var now = new Date();
  var diffDays = Math.floor(
    (startOfDay(now).getTime() - startOfDay(d).getTime()) / 86400000,
  );
  var hh = pad2(d.getHours());
  var mm = pad2(d.getMinutes());
  if (diffDays === 0) return '今日 ' + hh + ':' + mm;
  if (diffDays === 1) return '昨日 ' + hh + ':' + mm;
  if (diffDays >= 2 && diffDays <= 6) return diffDays + ' 天前';
  if (d.getFullYear() === now.getFullYear()) return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
}

module.exports = {
  parseServerTime: parseServerTime,
  formatDateTime: formatDateTime,
  formatFullTime: formatFullTime,
  formatDate: formatDate,
  formatTime: formatTime,
  formatRelativeTime: formatRelativeTime,
  formatFriendlyTime: formatFriendlyTime,
};
