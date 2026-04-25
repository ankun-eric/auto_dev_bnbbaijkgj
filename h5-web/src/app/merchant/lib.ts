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

// [2026-04-26 PRD v1.0 §R1] 角色统一治理：业务上仅 4 角色（boss/store_manager/finance/clerk）
// 物理 member_role 仍存历史值（owner/store_manager/finance/verifier/staff），
// roleLabel 同时覆盖两套，确保不同入口点都能正确展示中文。
export const roleLabel: Record<string, string> = {
  // 物理 member_role
  owner: '老板',
  store_manager: '店长',
  verifier: '店员',  // [R1] 核销员合并到店员
  finance: '财务',
  staff: '店员',     // [R1] 历史 staff 合并到店员
  // 业务 role_code（4 角色）
  boss: '老板',
  clerk: '店员',
  manager: '店长',   // 历史别名
};

// 按角色决定菜单可见性
// [2026-04-24] 扩充 8 个模块；新增 finance（财务对账汇总）、保留原 settlement/invoice/staff/store-settings
// [2026-04-26 §R1] 同时支持 role_code（4 角色）与 member_role（5 物理值）输入；
// 历史/别名分支保留，避免 H5 旧 token 在过渡期内菜单空白。
export function canAccess(role: string | undefined, page: string): boolean {
  if (!role) return false;
  const matrix: Record<string, string[]> = {
    // 老板（boss / owner）：全部 8 个模块
    owner: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'store-settings', 'downloads', 'messages'],
    boss:  ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'store-settings', 'downloads', 'messages'],
    // 店长（store_manager / manager）：除门店设置外，全部
    store_manager: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'downloads', 'messages'],
    manager:       ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'staff', 'downloads', 'messages'],
    // 财务：财务相关
    finance: ['dashboard', 'orders', 'verifications', 'reports', 'settlement', 'invoice', 'finance', 'downloads', 'messages'],
    // 店员（clerk / verifier / staff）：核销 & 工作台
    verifier: ['dashboard', 'orders', 'verifications', 'messages'],
    clerk:    ['dashboard', 'orders', 'verifications', 'messages'],
    staff:    ['dashboard', 'orders', 'verifications', 'messages'],
  };
  return (matrix[role] || []).includes(page);
}

// 角色 code（4 角色）到底层 member_role 的映射
export const roleCodeToMemberRole: Record<string, 'owner' | 'store_manager' | 'finance' | 'verifier'> = {
  boss: 'owner',
  store_manager: 'store_manager',
  finance: 'finance',
  clerk: 'verifier',  // clerk 在 DB 物理上落 verifier 枚举
  // 历史别名兼容
  manager: 'store_manager',
};

// [2026-04-26 §R1] role_code → 中文（仅 4 角色）；历史别名再保留 1 个版本
export const roleCodeLabel: Record<string, string> = {
  boss: '老板',
  store_manager: '店长',
  finance: '财务',
  clerk: '店员',
  // 历史兼容
  manager: '店长',
  verifier: '店员',
  staff: '店员',
  owner: '老板',
};

export { api };
