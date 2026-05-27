/**
 * [PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27]
 * 后端统一使用 datetime.utcnow() 存储，isoformat() 时附 'Z' 标识 UTC。
 * 前端使用 dayjs 转为北京时间显示。
 */
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import tz from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(tz);

const CN_TZ = 'Asia/Shanghai';

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '-';
  const m = dayjs.utc(iso).tz(CN_TZ);
  if (!m.isValid()) return (iso as string);
  return m.format('YYYY-MM-DD HH:mm:ss');
}

export function formatDate(iso?: string | null): string {
  if (!iso) return '-';
  const m = dayjs.utc(iso).tz(CN_TZ);
  if (!m.isValid()) return (iso as string);
  return m.format('YYYY-MM-DD');
}
