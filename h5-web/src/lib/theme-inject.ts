/**
 * PRD-447 v2 · H5 主题热注入（最小化、失败安全）
 *
 * 启动流程：
 * 1) 先用 localStorage 缓存的 token 秒开（如果有）
 * 2) 异步拉 /api/h5/active-theme
 * 3) 拉取成功且 version 变了，覆盖到 <style id="theme-vars">
 * 4) 任何失败：保留工程内置默认 token（即 globals.css 中的硬编码 token），不影响渲染
 *
 * 注入到 <style id="theme-vars">:root{...}</style>，由 cascade 覆盖 globals.css 中的同名变量。
 */

interface ThemePayload {
  id: number;
  name: string;
  version: number;
  tokens: any;
}

const STYLE_ID = 'theme-vars';
const CACHE_KEY = 'bh.theme.v447.cache';

function buildCssText(tokens: any): string {
  if (!tokens) return '';
  const lines: string[] = [];
  // atomic.color_brand → --color-brand-<n>
  const brand = tokens?.atomic?.color_brand || {};
  for (const [k, v] of Object.entries(brand)) {
    lines.push(`--color-brand-${k}: ${v};`);
  }
  // atomic.color_neutral → --color-neutral-<n>
  const neu = tokens?.atomic?.color_neutral || {};
  for (const [k, v] of Object.entries(neu)) {
    lines.push(`--color-neutral-${k}: ${v};`);
  }
  // atomic.gradients → --gradient-*
  const grad = tokens?.atomic?.gradients || {};
  const gradMap: Record<string, string> = {
    topbar: '--gradient-topbar-a',
    fn_cell: '--gradient-fn-cell',
    primary: '--gradient-primary',
    hero_dark: '--gradient-hero-dark',
    user_card: '--gradient-user-card-a',
  };
  for (const [k, v] of Object.entries(grad)) {
    const cssVar = gradMap[k];
    if (cssVar) lines.push(`${cssVar}: ${v};`);
  }
  // theme + semantic 层用下划线->短横线规则
  const passthrough = (obj: any) => {
    if (!obj) return;
    for (const [k, v] of Object.entries(obj)) {
      lines.push(`--${String(k).replace(/_/g, '-')}: ${v};`);
    }
  };
  passthrough(tokens?.theme);
  passthrough(tokens?.semantic);
  return `:root{${lines.join('')}}`;
}

function applyTokens(tokens: any) {
  if (typeof document === 'undefined') return;
  const css = buildCssText(tokens);
  if (!css) return;
  let el = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement('style');
    el.id = STYLE_ID;
    document.head.appendChild(el);
  }
  el.textContent = css;
}

function getApiBase(): string {
  if (typeof window === 'undefined') return '';
  // 与现有项目保持一致：直接用相对路径走 nginx 反向代理
  return '';
}

export async function bootstrapTheme() {
  if (typeof window === 'undefined') return;
  // 1) 缓存秒开
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (raw) {
      const cached = JSON.parse(raw) as ThemePayload;
      if (cached?.tokens) applyTokens(cached.tokens);
    }
  } catch {/* 忽略缓存读失败 */}

  // 2) 异步拉最新
  try {
    const res = await fetch(`${getApiBase()}/api/h5/active-theme`, {
      credentials: 'omit',
      cache: 'no-store',
    });
    if (!res.ok) return;
    const data = (await res.json()) as ThemePayload;
    if (!data?.tokens) return;
    applyTokens(data.tokens);
    try { window.localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch {/* ignore */}
  } catch {
    // 3) 拉取失败：保留工程内置默认 token，零影响
  }
}
