/**
 * [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（Admin Web 端）
 *
 * 与 h5-web/src/lib/datetime.ts 保持完全一致的语义：
 * - 后端时间统一按 UTC 解析（兼容无时区后缀的老接口）
 * - 按用户本地时区格式化显示
 *
 * 使用规范（强制）：
 * - 禁止在页面/组件中散写 `new Date(iso)` 解析后端时间
 * - 禁止散写 `toLocaleString()`、自实现的 `formatRelativeTime`
 */

export function parseServerTime(iso?: string | number | Date | null): Date | null {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return Number.isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  const normalized = hasTz ? s : s + 'Z';
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

export function formatDateTime(
  iso?: string | number | Date | null,
  pattern = 'YYYY-MM-DD HH:mm',
): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  return pattern
    .replace('YYYY', String(d.getFullYear()))
    .replace('MM', pad2(d.getMonth() + 1))
    .replace('DD', pad2(d.getDate()))
    .replace('HH', pad2(d.getHours()))
    .replace('mm', pad2(d.getMinutes()))
    .replace('ss', pad2(d.getSeconds()));
}

export function formatDate(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'YYYY-MM-DD');
}

export function formatTime(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'HH:mm');
}

export function formatRelativeTime(iso?: string | number | Date | null): string {
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

export function formatFriendlyTime(iso?: string | number | Date | null): string {
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
  if (isYesterday) return `昨天 ${formatTime(iso)}`;
  if (d.getFullYear() === now.getFullYear()) {
    return formatDateTime(iso, 'MM-DD HH:mm');
  }
  return formatDate(iso);
}
