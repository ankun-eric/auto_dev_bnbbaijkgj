/**
 * [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（H5 / Web 端）
 * [PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27] 后端统一 utcnow() + 'Z'，前端按本地（即北京）时区显示
 * [BUG_FIX_H5_GLOBAL_CRASH_20260528] 恢复全站使用的导出函数（parseServerTime/formatTime/
 *   formatRelativeTime/formatFriendlyTime），修复 H5 全站跳转崩溃。
 *
 * 设计目标：
 * - 后端所有 datetime 都以 UTC（"+00:00" 或 "Z" 后缀）返回，前端按设备本地时区显示
 * - 兼容老接口：如果后端字段不带时区后缀（如 "2026-05-17T02:30:00"），强制按 UTC 解析
 *   而非 JS 默认的"本地时区"解析，避免出现 8 小时偏差
 *
 * 使用规范（强制）：
 * - 禁止在组件中散写 `new Date(iso)` 来解析后端时间，必须用 parseServerTime
 * - 禁止散写 `formatRelativeTime`、`formatTime` 等逻辑，统一调用本文件提供的函数
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

/**
 * 按用户本地时区格式化为 "YYYY-MM-DD HH:mm:ss" 等模式。
 *
 * 支持的占位符：YYYY / MM / DD / HH / mm / ss
 *
 * 默认 pattern 为 'YYYY-MM-DD HH:mm:ss'（含秒），兼容居家安全 v1 的显示需求；
 * 其他页面按需传 pattern（如 'YYYY-MM-DD HH:mm'）。
 */
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

export function formatDate(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return iso == null || iso === '' ? '-' : String(iso);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function formatTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

export function formatRelativeTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) {
    return formatDateTime(iso);
  }
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
