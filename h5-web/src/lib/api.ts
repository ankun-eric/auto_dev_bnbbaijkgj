import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

/**
 * 根据当前浏览器 pathname 判定应跳转到哪个登录页，以及应清除的 token key。
 *
 * - /merchant/m/* -> 商家端 H5（手机版）登录页
 * - /merchant/*   -> 商家端 PC 版登录页
 * - 其它          -> C 端用户 H5 登录页
 *
 * 设计要点：
 * - 当前 pathname 已经在目标登录页时，返回 alreadyOnLogin=true，调用方不再做跳转，避免登录页自循环刷新。
 * - tokenKey 返回本端对应的 key，避免串端残留。
 */
export function resolveLoginRedirectPath(pathname: string, base: string): {
  path: string;
  tokenKey: string;
  alreadyOnLogin: boolean;
} {
  const p = pathname || '';
  const normalized = p.replace(/\/+$/, '');
  const prefix = (base || '').replace(/\/+$/, '');

  // 去掉 basePath 前缀，得到应用内路径，便于匹配
  const appPath = prefix && normalized.startsWith(prefix)
    ? normalized.substring(prefix.length)
    : normalized;

  if (appPath.startsWith('/merchant/m/') || appPath === '/merchant/m') {
    const target = `${prefix}/merchant/m/login`;
    return {
      path: target,
      tokenKey: 'merchant_token',
      alreadyOnLogin: appPath === '/merchant/m/login' || appPath.startsWith('/merchant/m/login/'),
    };
  }
  if (appPath.startsWith('/merchant/') || appPath === '/merchant') {
    const target = `${prefix}/merchant/login`;
    return {
      path: target,
      tokenKey: 'merchant_token',
      alreadyOnLogin: appPath === '/merchant/login' || appPath.startsWith('/merchant/login/'),
    };
  }
  const target = `${prefix}/login`;
  return {
    path: target,
    tokenKey: 'token',
    alreadyOnLogin: appPath === '/login' || appPath.startsWith('/login/'),
  };
}

const api = axios.create({
  baseURL: basePath,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      // 商家端页面优先使用 merchant_token，其它端使用 token
      const pathname = window.location.pathname || '';
      const prefix = basePath.replace(/\/+$/, '');
      const appPath = prefix && pathname.startsWith(prefix)
        ? pathname.substring(prefix.length)
        : pathname;
      const isMerchant = appPath.startsWith('/merchant/') || appPath === '/merchant';
      const token = isMerchant
        ? (localStorage.getItem('merchant_token') || localStorage.getItem('token'))
        : localStorage.getItem('token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      // [PRD-05 核销动作收口手机端 v1.0] 客户端类型 Header
      // - /merchant/m/*           -> h5-mobile（商家端 H5 移动版，含 /merchant/m/verify 核销页）
      // - 其他 H5 页面（含 PC 端商家后台 /merchant/*、C 端 /*）-> pc-web
      // 后端 require_mobile_verify_client 依赖项据此放行/拦截核销动作。
      if (config.headers) {
        const clientType = appPath.startsWith('/merchant/m/') || appPath === '/merchant/m'
          ? 'h5-mobile'
          : 'pc-web';
        config.headers['Client-Type'] = clientType;
        config.headers['X-Client-Type'] = clientType;
      }
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        const { path, tokenKey, alreadyOnLogin } = resolveLoginRedirectPath(
          window.location.pathname || '',
          basePath
        );
        // 清除本端对应的 token（及通用 token、user/profile 残留）
        try {
          localStorage.removeItem(tokenKey);
          if (tokenKey !== 'token') localStorage.removeItem('token');
          localStorage.removeItem('user');
          if (tokenKey === 'merchant_token') {
            localStorage.removeItem('merchant_profile');
            localStorage.removeItem('merchant_current_store');
          }
        } catch {}
        // 已在对应登录页上，不再重定向（避免登录页自循环刷新 / 打断登录页自身的 401 提示）
        if (!alreadyOnLogin) {
          window.location.href = path;
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
