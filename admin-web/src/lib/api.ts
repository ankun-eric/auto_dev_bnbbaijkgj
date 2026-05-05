import axios, { AxiosRequestConfig } from 'axios';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
const apiBase = apiUrl ? apiUrl.replace(/\/api\/?$/, '') : '';

const api = axios.create({
  baseURL: apiBase,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      // [PRD-05 核销动作收口手机端 v1.0] Admin 平台是 PC 端管理后台，
      // 显式声明 Client-Type=pc-web，后端核销接口将拒绝此来源的调用。
      config.headers['Client-Type'] = 'pc-web';
      config.headers['X-Client-Type'] = 'pc-web';
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        // 清除本端（admin）对应的 token 和用户信息
        try {
          localStorage.removeItem('admin_token');
          localStorage.removeItem('admin_user');
        } catch {}
        // [2026-04-25] Bug 修复：跳转到 admin 端登录页，并避免登录页自循环刷新。
        // admin-web 自身的登录页路由是 /login（项目内部路径），basePath 已包含 /admin 前缀时
        // ${basePath}/login 即为 /admin/login；否则即为 /login。统一口径为 "admin 端登录页"。
        const pathname = window.location.pathname || '';
        const normalized = pathname.replace(/\/+$/, '');
        const prefix = (basePath || '').replace(/\/+$/, '');
        const appPath = prefix && normalized.startsWith(prefix)
          ? normalized.substring(prefix.length)
          : normalized;
        const alreadyOnLogin = appPath === '/login' || appPath.startsWith('/login/');
        if (!alreadyOnLogin) {
          window.location.href = `${basePath}/login`;
        }
      }
    }
    return Promise.reject(error);
  }
);

export async function get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.get(url, { params, ...config });
  return res.data;
}

export async function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.post(url, data, config);
  return res.data;
}

export async function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.put(url, data, config);
  return res.data;
}

export async function del<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.delete(url, config);
  return res.data;
}

export async function patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.patch(url, data, config);
  return res.data;
}

export async function upload<T = any>(url: string, file: File, fieldName = 'file'): Promise<T> {
  const formData = new FormData();
  formData.append(fieldName, file);
  const res = await api.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export default api;
