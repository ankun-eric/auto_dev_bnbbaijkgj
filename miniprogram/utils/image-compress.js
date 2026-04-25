/**
 * [2026-04-25 PRD F1] 微信小程序图片压缩工具
 *
 * 目标：长边 ≤ 1600 px，输出体积 ≤ 600 KB
 * 借助 wx.compressImage（>=2.13.0）+ wx.getImageInfo 实现。
 * 若压缩后体积反而更大，则回退到原图。
 */

const TARGET_LONG_EDGE = 1600;
const TARGET_BYTES = 600 * 1024;

function getImageInfo(src) {
  return new Promise((resolve, reject) => {
    wx.getImageInfo({ src, success: resolve, fail: reject });
  });
}

function getFileSize(filePath) {
  return new Promise((resolve) => {
    try {
      const fs = wx.getFileSystemManager();
      fs.stat({
        path: filePath,
        success: (res) => resolve((res.stats && res.stats.size) || 0),
        fail: () => resolve(0),
      });
    } catch (_) {
      resolve(0);
    }
  });
}

function compressOnce(src, quality, compressedWidth) {
  return new Promise((resolve, reject) => {
    const params = { src, quality };
    if (compressedWidth && compressedWidth > 0) params.compressedWidth = compressedWidth;
    try {
      wx.compressImage({
        ...params,
        success: (r) => resolve(r.tempFilePath),
        fail: reject,
      });
    } catch (e) {
      reject(e);
    }
  });
}

/**
 * 压缩单张图片，返回压缩后的本地路径（若压缩后更大或失败，回退原路径）。
 */
async function compressImage(srcPath) {
  if (!srcPath || typeof srcPath !== 'string') return srcPath;
  const lower = srcPath.toLowerCase();
  if (lower.endsWith('.pdf') || lower.endsWith('.gif')) return srcPath;

  let info;
  try {
    info = await getImageInfo(srcPath);
  } catch (_) {
    return srcPath;
  }

  const w = info.width || 0;
  const h = info.height || 0;
  if (!w || !h) return srcPath;

  const longest = Math.max(w, h);
  const compressedWidth = longest > TARGET_LONG_EDGE
    ? Math.round((w * TARGET_LONG_EDGE) / longest)
    : 0;

  const originalSize = await getFileSize(srcPath);
  const tries = [85, 75, 65];
  let bestPath = srcPath;
  let bestSize = originalSize > 0 ? originalSize : Number.MAX_SAFE_INTEGER;

  for (const q of tries) {
    try {
      const out = await compressOnce(srcPath, q, compressedWidth);
      const sz = await getFileSize(out);
      if (sz > 0 && sz < bestSize) {
        bestSize = sz;
        bestPath = out;
      }
      if (sz > 0 && sz <= TARGET_BYTES) break;
    } catch (_) {
      // ignore single failure
    }
  }

  return bestPath;
}

async function compressImages(srcList) {
  const out = [];
  for (const p of srcList || []) {
    try {
      out.push(await compressImage(p));
    } catch (_) {
      out.push(p);
    }
  }
  return out;
}

module.exports = {
  compressImage,
  compressImages,
};
