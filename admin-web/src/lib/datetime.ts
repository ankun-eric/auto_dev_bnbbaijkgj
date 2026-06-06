/**
 * [日期时区简化 2026-06-06] 简化版时间格式化工具（Admin 端）
 *
 * 后端统一返回北京时间，dayjs 直接解析即可，无需时区转换。
 */
import dayjs from 'dayjs';

function normalize(input: string | number | Date | null | undefined): dayjs.Dayjs | null {
  if (input === null || input === undefined || input === '') return null;
  const d = dayjs(input);
  return d.isValid() ? d : null;
}

export function parseServerTime(iso?: string | number | Date | null): string {
  const d = normalize(iso);
  return d ? d.format('YYYY-MM-DD HH:mm:ss') : '';
}

export function formatDateTime(iso?: string | number | Date | null): string {
  const m = normalize(iso);
  if (!m) return iso == null || iso === '' ? '-' : String(iso);
  return m.format('YYYY-MM-DD HH:mm:ss');
}

export function formatFullTime(iso?: string | number | Date | null): string {
  return formatDateTime(iso);
}

export function formatDate(iso?: string | number | Date | null): string {
  const m = normalize(iso);
  if (!m) return iso == null || iso === '' ? '-' : String(iso);
  return m.format('YYYY-MM-DD');
}

export function formatTime(iso?: string | number | Date | null): string {
  const m = normalize(iso);
  if (!m) return '';
  return m.format('HH:mm');
}

export function formatFriendlyTime(iso?: string | number | Date | null): string {
  const m = normalize(iso);
  if (!m) return '';
  const now = dayjs();
  const startToday = now.startOf('day');
  const startTarget = m.startOf('day');
  const diffDays = startToday.diff(startTarget, 'day');
  if (diffDays === 0) return '今日 ' + m.format('HH:mm');
  if (diffDays === 1) return '昨日 ' + m.format('HH:mm');
  if (diffDays >= 2 && diffDays <= 6) return diffDays + ' 天前';
  if (m.year() === now.year()) return m.format('MM-DD');
  return m.format('YYYY-MM-DD');
}
