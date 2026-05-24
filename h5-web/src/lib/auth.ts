import { useState, useEffect, useCallback } from 'react';

interface UserInfo {
  id: string;
  phone: string;
  nickname: string;
  avatar: string;
  /**
   * @deprecated 旧"积分会员等级"已废弃（PRD v1.1），UI 不再展示该字段。
   * 请改用 `/api/membership/me` 返回的付费会员套餐信息（plan_code / plan_name / is_paid_member）。
   * 字段保留仅为兼容旧数据反序列化，不要在新代码中读取。
   */
  memberLevel?: string;
  points: number;
  user_no?: string;
  referrer_no?: string;
}

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
        setIsLoggedIn(true);
      } catch {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  const updateUser = useCallback((info: UserInfo) => {
    setUser(info);
    localStorage.setItem('user', JSON.stringify(info));
  }, []);

  return { user, isLoggedIn, loading, updateUser };
}

export function login(token: string, user?: Record<string, unknown>) {
  localStorage.setItem('token', token);
  if (user) {
    localStorage.setItem('user', JSON.stringify(user));
  }
}

export function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  // [2026-05-04 H5 支付链路 BasePath 修复] 用 withBasePath 包裹，
  // 防止部署在 /autodev/<uuid>/ 子路径下时，logout 跳转掉到根域名 /login
  const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/+$/, '');
  window.location.href = (basePath || '') + '/login';
}
