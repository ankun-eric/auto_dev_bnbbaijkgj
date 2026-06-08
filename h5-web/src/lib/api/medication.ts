/**
 * [PRD-MED-HISTORY-V1] 用药提醒历史打卡记录 — H5 API 封装
 *
 * 包含：
 *   - 日历月视图
 *   - 单日打卡记录详情
 *   - 补打卡
 */
import api from '@/lib/api';

/* ───── 日历月视图 ───── */

export interface CalendarDay {
  date: string;
  status: 'fully_done' | 'partial' | 'missed' | 'no_plan';
}

export interface CalendarResponse {
  year: number;
  month: number;
  days: CalendarDay[];
}

export async function fetchCalendar(year: number, month: number): Promise<CalendarResponse> {
  const res = await api.get('/api/medication/calendar', { params: { year, month } });
  return res.data || res;
}

/* ───── 单日打卡记录详情 ───── */

export type RecordStatus = 'done' | 'supplement' | 'missed' | 'expired' | 'not_yet';

export interface RecordItem {
  plan_id: number;
  drug_name: string;
  dosage: string;
  scheduled_time: string;
  status: RecordStatus;
  check_in_time: string | null;
  check_in_type: 'normal' | 'supplement' | null;
  can_supplement: boolean;
}

export interface RecordsResponse {
  date: string;
  records: RecordItem[];
}

export async function fetchRecords(date: string): Promise<RecordsResponse> {
  const res = await api.get('/api/medication/records', { params: { date } });
  return res.data || res;
}

/* ───── 补打卡 ───── */

export interface SupplementRequest {
  plan_id: number;
  check_in_date: string;
  scheduled_time: string;
}

export interface SupplementResponse {
  id: number;
  plan_id: number;
  check_in_date: string;
  scheduled_time: string;
  check_in_time: string;
  check_in_type: 'supplement';
}

export async function submitSupplement(data: SupplementRequest): Promise<SupplementResponse> {
  const res = await api.post('/api/medication/supplement', data);
  return res.data || res;
}
