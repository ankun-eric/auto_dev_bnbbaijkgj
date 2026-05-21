/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料优化 — H5 API 封装
 *
 * 包含：
 *   - 4 卡片 overview
 *   - 健康预警列表 / 标记已处理 / 全部已处理 / 测试数据 seed
 *   - 就医资料 CRUD / 回收站 / 恢复 / 立即彻底删除
 */
import api from '@/lib/api';

export type AlertType = 'checkup' | 'medication' | 'device' | 'manual';
export type Severity = 'high' | 'medium' | 'low';
export type RecordCategory = 'case_note' | 'checkup_report' | 'drug' | 'other';
export type RecordSource = 'ai_checkup' | 'ai_drug' | 'manual';

export interface OverviewResp {
  member_id: number | null;
  is_self: boolean;
  alerts_unresolved: number;
  medication_plan_count: number;
  family_member_count: number;
  device_count: number;
  medical_records_total: number;
  medical_records_by_category: Record<RecordCategory, number>;
  trash_count: number;
  show_alert_banner: boolean;
  banner_text: string;
}

export interface AlertItem {
  id: number;
  member_id: number | null;
  alert_type: AlertType;
  indicator: string;
  title: string;
  detail: string | null;
  severity: Severity;
  source_label: string | null;
  advice: string | null;
  merged_count: number;
  last_occurred_at: string;
  status: 'open' | 'done';
  resolved_at: string | null;
  ref_record_id: number | null;
  ref_plan_id: number | null;
  ref_device_id: number | null;
  raw_payload: any;
}

export interface RecordFile {
  id?: number;
  file_url: string;
  file_name: string;
  file_type: 'image' | 'pdf';
  file_size?: number | null;
}

export interface MedicalRecordItem {
  id: number;
  member_id: number | null;
  category: RecordCategory;
  category_label: string;
  title: string;
  record_date: string | null;
  source: RecordSource;
  source_label: string;
  has_ai_interpretation: boolean;
  file_count: number;
  thumbnail_url: string | null;
  is_deleted: boolean;
  days_to_purge: number | null;
  created_at: string;
  updated_at: string;
}

export interface MedicalRecordDetail extends MedicalRecordItem {
  files: RecordFile[];
  ai_interpretation: any | null;
  remark: string | null;
}

function unwrap<T>(res: any): T {
  return (res && (res.data ?? res)) as T;
}

export async function fetchOverview(memberId?: number | null): Promise<OverviewResp> {
  const qs = memberId != null && memberId > 0 ? `?member_id=${memberId}` : '';
  return unwrap(await api.get(`/api/health-archive-v5/overview${qs}`));
}

export async function fetchAlerts(params: {
  memberId?: number | null;
  status?: 'open' | 'done' | 'all';
  alertType?: AlertType;
}): Promise<{ total: number; items: AlertItem[] }> {
  const qp = new URLSearchParams();
  if (params.memberId != null && params.memberId > 0) qp.set('member_id', String(params.memberId));
  qp.set('status', params.status || 'open');
  if (params.alertType) qp.set('alert_type', params.alertType);
  return unwrap(await api.get(`/api/health-alerts?${qp.toString()}`));
}

export async function resolveAlert(id: number): Promise<{ ok: boolean }> {
  return unwrap(await api.post(`/api/health-alerts/${id}/resolve`));
}

export async function resolveAllAlerts(memberId?: number | null): Promise<{ ok: boolean }> {
  const qs = memberId != null && memberId > 0 ? `?member_id=${memberId}` : '';
  return unwrap(await api.post(`/api/health-alerts/resolve-all${qs}`));
}

export async function seedAlerts(payload: {
  member_id?: number | null;
  items: Array<Partial<AlertItem> & { alert_type: AlertType; indicator: string; title: string }>;
}): Promise<{ ok: boolean; created: number; merged: number }> {
  return unwrap(await api.post('/api/health-alerts/_seed', payload));
}

export async function listRecords(params: {
  memberId?: number | null;
  category?: RecordCategory;
}): Promise<{ total: number; items: MedicalRecordItem[]; grouped: Record<RecordCategory, number> }> {
  const qp = new URLSearchParams();
  if (params.memberId != null && params.memberId > 0) qp.set('member_id', String(params.memberId));
  if (params.category) qp.set('category', params.category);
  return unwrap(await api.get(`/api/medical-records?${qp.toString()}`));
}

export async function listTrash(memberId?: number | null): Promise<{ total: number; items: MedicalRecordItem[] }> {
  const qs = memberId != null && memberId > 0 ? `?member_id=${memberId}` : '';
  return unwrap(await api.get(`/api/medical-records/trash${qs}`));
}

export async function getRecord(id: number): Promise<MedicalRecordDetail> {
  return unwrap(await api.get(`/api/medical-records/${id}`));
}

export async function createRecord(payload: {
  member_id?: number | null;
  category: RecordCategory;
  title: string;
  record_date?: string | null;
  source?: RecordSource;
  files: RecordFile[];
  ai_interpretation?: any;
  remark?: string;
}): Promise<MedicalRecordDetail> {
  return unwrap(await api.post('/api/medical-records', payload));
}

export async function patchRecord(id: number, payload: { title?: string; remark?: string; record_date?: string | null }): Promise<MedicalRecordDetail> {
  return unwrap(await api.patch(`/api/medical-records/${id}`, payload));
}

export async function softDeleteRecord(id: number): Promise<{ ok: boolean }> {
  return unwrap(await api.delete(`/api/medical-records/${id}`));
}

export async function restoreRecord(id: number): Promise<MedicalRecordDetail> {
  return unwrap(await api.post(`/api/medical-records/${id}/restore`));
}

export async function permanentDelete(id: number): Promise<{ ok: boolean }> {
  return unwrap(await api.delete(`/api/medical-records/${id}/permanent`));
}
