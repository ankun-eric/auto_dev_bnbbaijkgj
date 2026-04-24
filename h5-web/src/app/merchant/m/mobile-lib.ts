'use client';

// 移动端共享工具：复用桌面端登录态和 profile，但提供移动端特有的辅助函数。
// [2026-04-24] 商家端移动端 H5 PRD v1.0

import {
  getProfile,
  isAuthed,
  saveLogin,
  logoutMerchant as baseLogoutMerchant,
  setCurrentStoreId,
  getCurrentStoreId,
  canAccess,
  roleLabel,
  MerchantLoginProfile,
} from '../lib';
import api from '@/lib/api';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export {
  getProfile,
  isAuthed,
  saveLogin,
  setCurrentStoreId,
  getCurrentStoreId,
  canAccess,
  roleLabel,
  api,
};
export type { MerchantLoginProfile };

// 移动端退出：清除所有 localStorage 的 merchant 数据，然后跳转到移动端登录页
export function logoutMerchantMobile() {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem('merchant_token');
    localStorage.removeItem('token');
    localStorage.removeItem('merchant_profile');
    localStorage.removeItem('merchant_current_store');
  } catch {}
  window.location.href = `${basePath}/merchant/m/login`;
}

// 检测是否移动端
export function isMobileUA(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /iphone|ipod|ipad|android|mobile/i.test(navigator.userAgent);
}

// 检测是否微信内置浏览器
export function isWechatBrowser(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /micromessenger/i.test(navigator.userAgent);
}

// 订单状态映射（与 PC 一致）
export const statusMap: Record<string, { text: string; color: string }> = {
  pending_payment: { text: '待支付', color: '#faad14' },
  paid: { text: '待核销', color: '#1677ff' },
  redeemed: { text: '已核销', color: '#52c41a' },
  cancelled: { text: '已取消', color: '#8c8c8c' },
  refunded: { text: '已退款', color: '#ff4d4f' },
  completed: { text: '已完成', color: '#52c41a' },
};

// TabBar 项（按角色过滤）
export interface TabItem {
  key: string;
  title: string;
  path: string;
  icon: string; // emoji 占位，渲染时可替换
}

export function getTabsForRole(role?: string): TabItem[] {
  const base: TabItem[] = [
    { key: 'dashboard', title: '工作台', path: '/merchant/m/dashboard', icon: '🏠' },
    { key: 'orders', title: '订单', path: '/merchant/m/orders', icon: '📋' },
  ];
  if (role === 'finance') {
    base.push({ key: 'settlement', title: '对账', path: '/merchant/m/settlement', icon: '💰' });
  } else {
    base.push({ key: 'verify', title: '核销', path: '/merchant/m/verify', icon: '✓' });
  }
  base.push({ key: 'me', title: '我的', path: '/merchant/m/me', icon: '👤' });
  return base;
}

// 统一包含 basePath 的链接
export function withBase(path: string): string {
  return `${basePath}${path}`;
}

// 兼容 PC 端 logoutMerchant 的导出
export { baseLogoutMerchant };
