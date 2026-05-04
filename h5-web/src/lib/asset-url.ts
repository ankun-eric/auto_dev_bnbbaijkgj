/**
 * [2026-05-05 全端图片附件 BasePath 治理 v1.0]
 *
 * 资源 URL 解析工具：把后端返回的"裸路径"（如 /uploads/xxx.jpg）
 * 安全地补齐为带部署 basePath 前缀的可访问 URL，避免在
 * /autodev/<uuid>/ 这类子路径部署下被 nginx 网关返回纯文本
 * "Gateway OK"导致图片裂开。
 *
 * 设计原则（与 backend 解耦的纯前端工具）：
 *   1. 后端返回的 URL 形态保持不变（/uploads/...），由前端统一处理；
 *   2. 三类输入幂等处理：
 *      - 完整 URL（http(s)://、blob:、data:）→ 原样返回
 *      - 已带 basePath 前缀的路径 → 原样返回（防重复拼接）
 *      - 其他以 / 开头或相对路径 → 拼上 basePath
 *   3. basePath 为空（根路径部署 / 本地开发）时透传，零副作用。
 */

import { BASE_PATH, withBasePath } from './basePath';

/**
 * 解析任意"后端返回的资源路径"为浏览器可直接访问的 URL。
 *
 * 适用范围：所有 <img src>、<Image src>、<a href download>、
 * background-image: url(...) 中"由后端字段直出"的链接。
 *
 * @param path 后端返回的资源路径或 URL
 * @returns 浏览器可直接访问的完整路径（带 basePath 前缀）
 *
 * 示例：
 *   resolveAssetUrl('/uploads/order_attachments/35.jpg')
 *     -> '/autodev/<uuid>/uploads/order_attachments/35.jpg'
 *   resolveAssetUrl('https://cdn.x.com/a.jpg')
 *     -> 'https://cdn.x.com/a.jpg'           (跨域 CDN 原样)
 *   resolveAssetUrl('blob:http://localhost/abc')
 *     -> 'blob:http://localhost/abc'         (本地预览原样)
 *   resolveAssetUrl('data:image/png;base64,iVBOR...')
 *     -> 'data:image/png;base64,iVBOR...'    (内嵌图原样)
 *   resolveAssetUrl('/autodev/<uuid>/uploads/x.jpg')
 *     -> '/autodev/<uuid>/uploads/x.jpg'     (幂等)
 *   resolveAssetUrl('')        -> ''
 *   resolveAssetUrl(null)      -> ''
 *   resolveAssetUrl(undefined) -> ''
 */
export function resolveAssetUrl(path: string | null | undefined): string {
  if (!path) return '';
  const s = String(path).trim();
  if (!s) return '';

  if (/^(https?:|blob:|data:)/i.test(s)) {
    return s;
  }

  if (s.startsWith('//')) {
    return s;
  }

  if (!s.startsWith('/')) {
    if (!BASE_PATH) return s;
    return BASE_PATH + '/' + s;
  }

  return withBasePath(s);
}

/**
 * 批量解析。常用于后端返回的图片地址数组。
 */
export function resolveAssetUrls(
  paths: ReadonlyArray<string | null | undefined> | null | undefined,
): string[] {
  if (!paths || !Array.isArray(paths)) return [];
  return paths.map((p) => resolveAssetUrl(p)).filter((u) => !!u);
}
