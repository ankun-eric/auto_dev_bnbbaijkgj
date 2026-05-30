/**
 * [PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27]
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 全局固定北京时间口径，新增 formatFriendlyTime / formatFullTime
 *
 * 后端 datetime 应统一以 UTC 返回；老接口若无时区后缀，前端按 UTC 解析后转为北京时间显示。
 */
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import tz from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(tz);

const CN_TZ = 'Asia/Shanghai';

function normalize(input: string | number | Date | null | undefined): dayjs.Dayjs | null {
  if (input === null || input === undefined || input === '') return null;
  if (input instanceof Date || typeof input === 'number') {
    const m = dayjs(input).tz(CN_TZ);
    return m.isValid() ? m : null;
  }
  let s = String(input).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasTz) {
    if (s.includes(' ') && !s.includes('T')) s = s.replace(' ', 'T');
    s = s + 'Z';
  }
  const m = dayjs.utc(s).tz(CN_TZ);
  return m.isValid() ? m : null;
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
  const now = dayjs().tz(CN_TZ);
  const startToday = now.startOf('day');
  const startTarget = m.startOf('day');
  const diffDays = startToday.diff(startTarget, 'day');
  if (diffDays === 0) return `今日 ${m.format('HH:mm')}`;
  if (diffDays === 1) return `昨日 ${m.format('HH:mm')}`;
  if (diffDays >= 2 && diffDays <= 6) return `${diffDays} 天前`;
  if (m.year() === now.year()) return m.format('MM-DD');
  return m.format('YYYY-MM-DD');
}
