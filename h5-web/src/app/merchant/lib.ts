'use client';

import api from '@/lib/api';

const TOKEN_KEY = 'merchant_token';
const PROFILE_KEY = 'merchant_profile';
const STORE_KEY = 'merchant_current_store';

export interface MerchantLoginProfile {
  merchant_id: number;
  merchant_name: string;
  merchant_category?: string | null;
  role: 'owner' | 'store_manager' | 'verifier' | 'finance' | 'staff';
  store_ids: number[];
  stores: { id: number; name: string }[];
}

export function saveLogin(token: string, profile: MerchantLoginProfile) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem('token', token); // 共用 axios 拦截器
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  if (profile.store_ids?.length === 1) {
    localStorage.setItem(STORE_KEY, String(profile.store_ids[0]));
  }
}

export function logoutMerchant() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem('token');
  localStorage.removeItem(PROFILE_KEY);
  localStorage.removeItem(STORE_KEY);
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  window.location.href = `${basePath}/merchant/login`;
}

export function getProfile(): MerchantLoginProfile | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(PROFILE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MerchantLoginProfile;
  } catch {
    return null;
  }
}

export function setCurrentStoreId(id: number) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORE_KEY, String(id));
}

export function getCurrentStoreId(): number | null {
  if (typeof window === 'undefined') return null;
  const v = localStorage.getItem(STORE_KEY);
  return v ? Number(v) : null;
}

export function isAuthed(): boolean {
  if (typeof window === 'undefined') return false;
  return !!localStorage.getItem(TOKEN_KEY);
}

export const roleLabel: Record<string, string> = {
  owner: '老板',
  store_manager: '店长',
  verifier: '核销员',
  finance: '财务',
  staff: '员工',
};

// 按角色决定菜单可见性
// [2026-04-24] 扩充 8 个模块；新增 finance（财务对账汇总）、保留原 settlement/invoice/staff/store-settings
export function canAccess(role: string | undefined, page: string): boolean {
  if (!role) return false;
  const matrix: Record<string, string[]> = {
    // boss 老板：全部
    owner: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'store-settings', 'downloads', 'messages'],
    // manager 店长：全部
    store_manager: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'store-settings', 'downloads', 'messages'],
    // finance 财务：dashboard/records/messages/profile/finance（不能核销、不能看员工/门店设置）
    finance: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'downloads', 'messages'],
    // clerk 店员 = verifier：dashboard/verify/records/messages/profile
    verifier: ['dashboard', 'orders', 'verifications', 'messages'],
    // 历史兜底：staff 视同 clerk
    staff: ['dashboard', 'orders', 'verifications', 'messages'],
  };
  return (matrix[role] || []).includes(page);
}

// 角色 code（boss/manager/finance/clerk）到底层 member_role 的映射
export const roleCodeToMemberRole: Record<string, 'owner' | 'store_manager' | 'finance' | 'verifier'> = {
  boss: 'owner',
  manager: 'store_manager',
  finance: 'finance',
  clerk: 'verifier',
};

export const roleCodeLabel: Record<string, string> = {
  boss: '老板',
  manager: '店长',
  finance: '财务',
  clerk: '店员',
};

export { api };
