import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { showToast } from './toast-unified';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

/**
 * [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
 * 网关/反向代理层兜底文本特征列表
 *
 * 背景：当请求 URL 未命中 gateway-nginx 已注册路由时，gateway 会返回纯文本
 * （如 "gateway ok"），且 HTTP 状态码为 200。前端如果将其直接当作业务数据
 * 渲染，会导致整页白屏只剩一行文字。
 *
 * 处理：在响应拦截器中识别这类「成功但非合法 JSON / 命中兜底文本」的响应，
 * 主动转化为业务错误，弹友好 toast 提示，避免白屏。
 */
const GATEWAY_FALLBACK_PATTERNS: RegExp[] = [
  /^gateway ok\s*$/i,
  /^ok\s*$/i,
  /^bad gateway/i,
  /^gateway timeout/i,
];

function isGatewayFallback(body: unknown): boolean {
  if (typeof body !== 'string') return false;
  const trimmed = body.trim();
  if (!trimmed) return false;
  if (trimmed.length > 200) return false;
  return GATEWAY_FALLBACK_PATTERNS.some((re) => re.test(trimmed));
}

function isJsonContentType(ct: string | undefined | null): boolean {
  if (!ct) return false;
  return /application\/(?:json|.*\+json)/i.test(ct);
}

/**
 * 上报前端"网关静默失败"事件，便于主动监控同类问题。
 * 仅在浏览器环境且 sendBeacon 可用时上报；不影响主流程。
 */
function reportGatewayFallback(response: AxiosResponse) {
  try {
    if (typeof window === 'undefined') return;
    const payload = {
      type: 'gateway_fallback',
      url: response.config?.url || '',
      full_url: (response.config?.baseURL || '') + (response.config?.url || ''),
      method: (response.config?.method || 'GET').toUpperCase(),
      status: response.status,
      content_type: response.headers?.['content-type'] || '',
      body_excerpt: String(response.data || '').slice(0, 200),
      page_path: window.location?.pathname || '',
      user_id: (() => {
        try {
          return window.localStorage.getItem('user_id') || '';
        } catch {
          return '';
        }
      })(),
      ts: new Date().toISOString(),
    };
    console.warn('[gateway-fallback]', payload);
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const url = `${basePath}/api/_frontend_log`;
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      try {
        navigator.sendBeacon(url, blob);
      } catch {
        /* ignore */
      }
    }
  } catch {
    /* swallow to avoid breaking response flow */
  }
}

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
      // [PRD-05 核销动作收口手机端 v1.0 + 客户端订单顾客操作鉴权误判 Bug 修复 v1.0]
      // 客户端类型 Header 三段式判定（按 path 分流）：
      // - /merchant/m/*           -> h5-mobile（商家端 H5 移动版，含 /merchant/m/verify 核销页）
      // - /merchant/*（含 /merchant、/merchant/login 等 PC 商家后台）-> pc-web
      // - 其他（C 端顾客域/路径）-> h5-user（顾客 H5 客户端，订单顾客接口的合法来源之一）
      //
      // 用途：
      //   - require_mobile_verify_client：放行 h5-mobile / verify-miniprogram
      //   - require_customer_client_session：放行 h5-user / miniprogram-user / app-user
      // 商家兼顾客的用户在 C 端登录后将以 h5-user 身份发请求，不再被全局 role=merchant 一刀切。
      if (config.headers) {
        let clientType: string;
        if (appPath.startsWith('/merchant/m/') || appPath === '/merchant/m') {
          clientType = 'h5-mobile';
        } else if (appPath.startsWith('/merchant/') || appPath === '/merchant') {
          clientType = 'pc-web';
        } else {
          clientType = 'h5-user';
          // [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
          // C 端顾客域请求统一带上 X-Client-Source: h5-customer，
          // 后端据此识别"本次操作以顾客身份发起"，避免双重身份用户被商家规则误伤。
          // 仅在 C 端顾客域（非 /merchant/*）注入此 Header，避免污染商家端请求。
          config.headers['X-Client-Source'] = 'h5-customer';
        }
        config.headers['Client-Type'] = clientType;
        config.headers['X-Client-Type'] = clientType;
      }
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => {
    // [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
    // 兜底容错：识别 gateway 兜底文本 / 非 JSON 响应，转为业务错误，避免白屏
    try {
      const ct = (response.headers?.['content-type'] as string | undefined) || '';
      const body = response.data;

      if (isGatewayFallback(body)) {
        reportGatewayFallback(response);
        try {
          showToast('网络异常，请稍后重试');
        } catch {}
        return Promise.reject(
          Object.assign(new Error('gateway_fallback_response'), {
            isGatewayFallback: true,
            response,
          }),
        );
      }

      // 期望 JSON 但拿到纯文本（且非空），同样视为异常
      if (typeof body === 'string' && body.length > 0 && !isJsonContentType(ct)) {
        const trimmed = body.trim();
        if (trimmed && trimmed[0] !== '{' && trimmed[0] !== '[') {
          reportGatewayFallback(response);
          try {
            showToast('网络异常，请稍后重试');
          } catch {}
          return Promise.reject(
            Object.assign(new Error('non_json_response'), {
              isGatewayFallback: true,
              response,
            }),
          );
        }
      }
    } catch {
      /* 任何兜底判断异常都不影响正常返回 */
    }
    return response.data;
  },
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
