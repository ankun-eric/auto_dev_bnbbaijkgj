/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2 API 封装。
 *
 * 服务端契约：参考 backend/app/api/devices_v2.py
 *   GET    /api/devices/catalog
 *   GET    /api/devices/my
 *   POST   /api/devices/bind
 *   POST   /api/devices/unbind
 *   PATCH  /api/devices/binding/:id
 */
import api from '@/lib/api';

export type BrandCode = 'binni' | 'huawei' | 'xiaomi' | 'apple' | 'other';

export interface CatalogItem {
  id: number;
  brand_code: BrandCode;
  brand_name: string;
  category_code: string;
  device_name: string;
  icon: string;
  is_active: boolean;
  is_unique: boolean;
  sort_order: number;
  bound_count: number;
}

export interface CatalogGroup {
  brand_code: BrandCode;
  brand_name: string;
  items: CatalogItem[];
}

export interface MyDeviceItem {
  id: number;
  catalog_id: number;
  brand_code: BrandCode;
  brand_name: string;
  category_code: string;
  device_name: string;
  icon: string;
  is_unique: boolean;
  sn: string;
  sn_masked: string;
  alias?: string | null;
  member_id?: number | null;
  member_nickname?: string | null;
  member_relation?: string | null;
  member_is_self?: boolean;
  bound_at?: string | null;
  is_active: boolean;
}

function unwrap<T>(res: any): T {
  return (res?.data ?? res) as T;
}

export async function fetchCatalog(): Promise<{ groups: CatalogGroup[]; total: number }> {
  const res = await api.get('/api/devices/catalog');
  return unwrap<{ groups: CatalogGroup[]; total: number }>(res);
}

export async function fetchMyDevices(memberId?: string | number | null): Promise<{ items: MyDeviceItem[]; total: number }> {
  const qs = memberId != null && memberId !== '' ? `?member_id=${memberId}` : '';
  const res = await api.get(`/api/devices/my${qs}`);
  return unwrap<{ items: MyDeviceItem[]; total: number }>(res);
}

export interface BindPayload {
  catalog_id: number;
  sn: string;
  alias?: string | null;
  member_id?: number | null;
}

export async function bindDevice(payload: BindPayload): Promise<{ id: number; binding: MyDeviceItem }> {
  const res = await api.post('/api/devices/bind', payload);
  return unwrap<{ id: number; binding: MyDeviceItem }>(res);
}

export async function unbindDevice(binding_id: number): Promise<{ message: string; id: number }> {
  const res = await api.post('/api/devices/unbind', { binding_id });
  return unwrap<{ message: string; id: number }>(res);
}

export interface EditBindingPayload {
  alias?: string | null;
  member_id?: number | null;
}

export async function editBinding(
  binding_id: number,
  payload: EditBindingPayload,
): Promise<{ message: string; binding: MyDeviceItem }> {
  const res = await api.patch(`/api/devices/binding/${binding_id}`, payload);
  return unwrap<{ message: string; binding: MyDeviceItem }>(res);
}
