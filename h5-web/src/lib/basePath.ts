/**
 * [2026-05-04 H5 支付链路 BasePath 修复 v1.0]
 *
 * 统一的"BasePath 前缀工具"。集中处理 H5 项目被部署在子路径下
 * （如 /autodev/<uuid>/）时的路径拼接问题，确保任何"裸 / 开头"的
 * 内部跳转都能正确保留 basePath 前缀，不会"掉到根域名"上。
 *
 * 核心约定：
 * - basePath 通过环境变量 NEXT_PUBLIC_BASE_PATH 注入（构建期常量）
 * - basePath 末尾不带 /；为空字符串时表示根域名/独立子域名场景
 * - Next.js 自身的 router.push / <Link> / next/image 等已经会自动处理 basePath，
 *   本工具主要用于"绕过 Next.js 路由系统"的硬跳转：
 *     - window.location.href = ...
 *     - <a href="...">
 *     - 后端返回的相对 pay_url
 *
 * 前向兼容性：未来切换到根域名或独立子域名时，
 * 只需把 NEXT_PUBLIC_BASE_PATH 改为空串，业务代码零改动。
 */

/** 当前 H5 部署的 basePath（如 "/autodev/6b099ed3-...".  空串表示根域）。 */
export const BASE_PATH: string = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/+$/, '');

/**
 * 给一个"以 / 开头的应用内路径"加上 basePath 前缀。
 *
 * - 如果 path 已经包含 basePath，则原样返回（幂等）
 * - 如果 path 是绝对 URL（http(s)://...），原样返回
 * - 如果 path 是相对路径（不以 / 开头），原样返回
 * - 如果 BASE_PATH 为空（根域场景），原样返回
 *
 * 示例：
 *   withBasePath('/login')                     -> '/autodev/<uuid>/login'
 *   withBasePath('/autodev/<uuid>/login')       -> '/autodev/<uuid>/login'  (幂等)
 *   withBasePath('https://x.com/foo')           -> 'https://x.com/foo'      (跨域)
 *   withBasePath('foo')                          -> 'foo'                    (相对路径)
 */
export function withBasePath(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  if (!path.startsWith('/')) return path;
  if (!BASE_PATH) return path;
  if (path === BASE_PATH || path.startsWith(BASE_PATH + '/')) return path;
  return BASE_PATH + path;
}

/**
 * 拼接"完整 URL"——基于当前浏览器 origin + basePath + path。
 * 用于需要把 URL 作为参数传给后端（例如未来真实支付宝下单的 return_url）。
 *
 * 仅在浏览器端可用；SSR 时会回退为相对的 withBasePath(path)。
 */
export function absoluteUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const withPrefix = withBasePath(path.startsWith('/') ? path : '/' + path);
  if (typeof window === 'undefined') return withPrefix;
  return window.location.origin + withPrefix;
}

/**
 * 安全地跳转到后端返回的 pay_url（支付宝沙盒/真实收银台 URL）。
 *
 * 兼容三种 pay_url 形态：
 * 1) 完整 URL（http(s)://...） —— 原样跳转（最常见的真实支付宝收银台）
 * 2) 以 basePath 开头的绝对路径 —— 原样跳转
 * 3) 以 / 开头但不带 basePath 的"裸绝对路径"（如 /sandbox-pay?...）
 *    —— 自动补上 basePath 前缀，避免落到根域名上的"另一个项目"
 *
 * 这是修复 H5 支付链路在 /autodev/<uuid>/ 子路径下整体错乱 Bug 的关键工具。
 */
export function redirectToPayUrl(payUrl: string): void {
  if (!payUrl) return;
  if (typeof window === 'undefined') return;
  let target = payUrl;
  if (/^https?:\/\//i.test(payUrl)) {
    target = payUrl;
  } else if (payUrl.startsWith('/')) {
    target = withBasePath(payUrl);
  } else {
    target = payUrl;
  }
  window.location.href = target;
}
