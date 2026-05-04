/**
 * [2026-05-05 全端图片附件 BasePath 治理 v1.0]
 *
 * 资源 URL 解析工具：把后端返回的"裸路径"（如 /uploads/xxx.jpg）
 * 安全地补齐为带部署 basePath 前缀的可访问 URL，避免在
 * /autodev/<uuid>/ 这类子路径部署下被 nginx 网关返回纯文本
 * "Gateway OK"导致图片裂开。
 *
 * 与 h5-web 的 asset-url.ts 保持一致的契约（独立一份避免跨工程依赖）。
 */

const BASE_PATH: string = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/+$/, '');

/**
 * 解析任意"后端返回的资源路径"为浏览器可直接访问的 URL。
 *
 * - 完整 URL（http(s)://、blob:、data:、//）原样返回
 * - 已带 basePath 前缀的路径原样返回（幂等）
 * - 其他以 / 开头或相对路径 → 拼上 basePath
 * - 空值安全（返回 ''）
 */
export function resolveAssetUrl(path: string | null | undefined): string {
  if (!path) return '';
  const s = String(path).trim();
  if (!s) return '';

  if (/^(https?:|blob:|data:)/i.test(s)) return s;
  if (s.startsWith('//')) return s;

  if (!s.startsWith('/')) {
    if (!BASE_PATH) return s;
    return BASE_PATH + '/' + s;
  }

  if (!BASE_PATH) return s;
  if (s === BASE_PATH || s.startsWith(BASE_PATH + '/')) return s;
  return BASE_PATH + s;
}

export function resolveAssetUrls(
  paths: ReadonlyArray<string | null | undefined> | null | undefined,
): string[] {
  if (!paths || !Array.isArray(paths)) return [];
  return paths.map((p) => resolveAssetUrl(p)).filter((u) => !!u);
}
