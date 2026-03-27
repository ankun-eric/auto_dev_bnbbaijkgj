import { useState, useEffect, useCallback } from 'react';

interface UserInfo {
  id: string;
  phone: string;
  nickname: string;
  avatar: string;
  memberLevel: string;
  points: number;
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
  window.location.href = '/login';
}
