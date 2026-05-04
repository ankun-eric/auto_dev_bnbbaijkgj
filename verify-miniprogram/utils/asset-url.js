/**
 * [2026-05-05 全端图片附件 BasePath 治理 v1.0]
 *
 * 资源 URL 解析工具：把后端返回的"裸路径"（如 /uploads/xxx.jpg）
 * 安全地补齐为带 域名+部署 basePath 前缀的完整 URL，避免
 * 在 /autodev/<uuid>/ 这类子路径部署下小程序无法加载图片。
 *
 * 设计原则：
 *   1. 完整 URL（http/https/data/blob/wxfile）原样返回；
 *   2. 已经带 baseUrl 前缀的原样返回（幂等）；
 *   3. 裸 / 开头或相对路径 → 拼上 app.globalData.baseUrl；
 *   4. 空值安全（返回 ''）。
 */

function getBaseUrl() {
  try {
    const app = getApp();
    if (app && app.globalData && app.globalData.baseUrl) {
      return String(app.globalData.baseUrl).replace(/\/+$/, '');
    }
  } catch (e) {
    // getApp() 在 app.js 自身执行期间可能不可用
  }
  return '';
}

/**
 * 解析任意"后端返回的资源路径"为小程序可直接访问的 URL。
 *
 * 适用范围：所有 <image src>、wx.previewImage urls、
 * cover-image、background-image 中由后端字段直出的链接。
 */
function resolveAssetUrl(path) {
  if (!path) return '';
  const s = String(path).trim();
  if (!s) return '';

  if (/^(https?:|data:|blob:|wxfile:|cloud:|http-local:)/i.test(s)) {
    return s;
  }

  if (s.startsWith('//')) {
    return 'https:' + s;
  }

  const base = getBaseUrl();
  if (!base) return s;

  if (s.startsWith(base)) {
    return s;
  }

  if (s.startsWith('/')) {
    return base + s;
  }
  return base + '/' + s;
}

function resolveAssetUrls(paths) {
  if (!paths || !Array.isArray(paths)) return [];
  return paths.map(resolveAssetUrl).filter(function (u) { return !!u; });
}

module.exports = { resolveAssetUrl, resolveAssetUrls };
