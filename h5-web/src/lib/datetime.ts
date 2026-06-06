/**
 * [日期时区简化 2026-06-06] 简化版时间格式化工具（H5/Web 端）
 *
 * 后端统一返回北京时间 "YYYY-MM-DD HH:mm:ss"，前端直接 new Date() 解析即可。
 * 无需任何时区转换。
 */

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

export function parseServerTime(iso?: string | number | Date | null): Date | null {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return Number.isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const d = new Date(String(iso));
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(
  iso?: string | number | Date | null,
  pattern: string = 'YYYY-MM-DD HH:mm:ss',
): string {
  const d = parseServerTime(iso);
  if (!d) return iso == null || iso === '' ? '-' : String(iso);
  return pattern
    .replace('YYYY', String(d.getFullYear()))
    .replace('MM', pad2(d.getMonth() + 1))
    .replace('DD', pad2(d.getDate()))
    .replace('HH', pad2(d.getHours()))
    .replace('mm', pad2(d.getMinutes()))
    .replace('ss', pad2(d.getSeconds()));
}

export function formatFullTime(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm:ss');
}

export function formatDate(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'YYYY-MM-DD');
}

export function formatTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
}

export function formatRelativeTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return formatDateTime(iso);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return '刚刚';
  const min = Math.floor(sec / 60);
  if (min < 60) return min + ' 分钟前';
  const hour = Math.floor(min / 60);
  if (hour < 24) return hour + ' 小时前';
  const day = Math.floor(hour / 24);
  if (day < 30) return day + ' 天前';
  return formatDate(iso);
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function formatFriendlyTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const now = new Date();
  const targetStart = startOfDay(d);
  const todayStart = startOfDay(now);
  const diffDays = Math.floor((todayStart.getTime() - targetStart.getTime()) / 86400000);
  const hh = pad2(d.getHours());
  const mm = pad2(d.getMinutes());
  if (diffDays === 0) return '今日 ' + hh + ':' + mm;
  if (diffDays === 1) return '昨日 ' + hh + ':' + mm;
  if (diffDays >= 2 && diffDays <= 6) return diffDays + ' 天前';
  if (d.getFullYear() === now.getFullYear()) return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
}

export function formatRecordTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const now = new Date();
  const targetStart = startOfDay(d);
  const todayStart = startOfDay(now);
  const diffDays = Math.floor((todayStart.getTime() - targetStart.getTime()) / 86400000);
  if (diffDays === 0) {
    return '今日 ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm');
}

function hourPeriod(hour: number): string {
  if (hour >= 0 && hour < 6) return '凌晨';
  if (hour >= 6 && hour < 12) return '上午';
  if (hour >= 12 && hour < 14) return '中午';
  if (hour >= 14 && hour < 18) return '下午';
  return '晚上';
}

function spokenMinutes(minute: number): string {
  if (minute === 0) return '点';
  if (minute === 30) return '点半';
  return ':' + pad2(minute);
}

function spokenDatePrefix(diffDays: number, target: Date, now: Date): string {
  if (diffDays === 0) return '今天';
  if (diffDays === -1) return '明天';
  if (diffDays === -2) return '后天';
  if (target.getFullYear() === now.getFullYear()) return (target.getMonth() + 1) + '月' + target.getDate() + '日';
  return target.getFullYear() + '年' + (target.getMonth() + 1) + '月' + target.getDate() + '日';
}

function spokenDatePrefixPast(diffDays: number, target: Date, now: Date): string {
  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays >= 2 && diffDays <= 6) return diffDays + '天前';
  if (target.getFullYear() === now.getFullYear()) return (target.getMonth() + 1) + '月' + target.getDate() + '日';
  return target.getFullYear() + '年' + (target.getMonth() + 1) + '月' + target.getDate() + '日';
}

function preciseSuffix(target: Date, now: Date): string {
  if (target.getFullYear() === now.getFullYear()) {
    return pad2(target.getMonth() + 1) + '-' + pad2(target.getDate()) + ' ' + pad2(target.getHours()) + ':' + pad2(target.getMinutes());
  }
  return target.getFullYear() + '-' + pad2(target.getMonth() + 1) + '-' + pad2(target.getDate()) + ' ' + pad2(target.getHours()) + ':' + pad2(target.getMinutes());
}

export function formatSpokenTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const now = new Date();
  const targetStart = startOfDay(d);
  const todayStart = startOfDay(now);
  const diffDays = Math.floor((todayStart.getTime() - targetStart.getTime()) / 86400000);
  const hour = d.getHours();
  const period = hourPeriod(hour);
  const h12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  const minStr = spokenMinutes(d.getMinutes());
  const prefix = spokenDatePrefixPast(diffDays, d, now);
  const suffix = preciseSuffix(d, now);
  return prefix + period + h12 + minStr + '已签到（' + suffix + '）';
}

export function formatSpokenDeadline(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const now = new Date();
  const targetStart = startOfDay(d);
  const todayStart = startOfDay(now);
  const diffDays = Math.floor((todayStart.getTime() - targetStart.getTime()) / 86400000);
  const hour = d.getHours();
  const period = hourPeriod(hour);
  const h12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  const minStr = spokenMinutes(d.getMinutes());
  const prefix = spokenDatePrefix(diffDays, d, now);
  const suffix = preciseSuffix(d, now);
  return '最晚' + prefix + period + h12 + minStr + '前签到（' + suffix + '）';
}
