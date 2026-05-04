const { get } = require('./request');
// [2026-05-05 全端图片附件 BasePath 治理 v1.0] 上传成功后回写绝对 URL 字段
const { resolveAssetUrl } = require('./asset-url');

let _limitsCache = null;
const CACHE_TTL = 10 * 60 * 1000;

function fetchUploadLimits() {
  if (_limitsCache && Date.now() - _limitsCache.ts < CACHE_TTL) {
    return Promise.resolve(_limitsCache.items);
  }
  return get('/api/cos/upload-limits', {}, { showLoading: false, suppressErrorToast: true })
    .then(res => {
      const items = (res && Array.isArray(res.items)) ? res.items : [];
      _limitsCache = { items, ts: Date.now() };
      return items;
    })
    .catch(() => {
      return _limitsCache ? _limitsCache.items : [];
    });
}

function checkFileSize(filePath, module) {
  return new Promise((resolve) => {
    wx.getFileInfo({
      filePath,
      success(res) {
        fetchUploadLimits().then(limits => {
          const rule = limits.find(l => l.module === module);
          if (!rule) {
            resolve({ ok: true });
            return;
          }
          const maxBytes = rule.max_size_mb * 1024 * 1024;
          if (res.size > maxBytes) {
            resolve({ ok: false, maxMb: rule.max_size_mb });
          } else {
            resolve({ ok: true });
          }
        });
      },
      fail() {
        resolve({ ok: true });
      }
    });
  });
}

function uploadWithProgress(url, filePath, options = {}) {
  const { name = 'file', formData = {}, onProgress, timeout } = options;
  const app = getApp();
  const token = app.globalData.token;
  const headers = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    const uploadTask = wx.uploadFile({
      url: app.globalData.baseUrl + url,
      filePath,
      name,
      formData,
      header: headers,
      timeout: timeout || 60000,
      success(res) {
        try {
          const data = JSON.parse(res.data);
          if (res.statusCode === 200) {
            // [2026-05-05 全端图片附件 BasePath 治理 v1.0]
            // 上传成功后，对 url / file_url 同时挂载绝对 URL 字段供 UI 直接渲染。
            // 注意：保留原始裸路径（url / file_url）不变，以维持既有数据契约（后端再次回传时不被破坏）。
            try {
              if (data && typeof data === 'object') {
                if (data.url && !data.absolute_url) {
                  data.absolute_url = resolveAssetUrl(data.url);
                }
                if (data.file_url && !data.absolute_file_url) {
                  data.absolute_file_url = resolveAssetUrl(data.file_url);
                }
              }
            } catch (_) { /* 兜底失败不影响主流程 */ }
            resolve(data);
          } else {
            const detail = (data && data.detail) || '上传失败';
            wx.showToast({ title: typeof detail === 'string' ? detail.slice(0, 60) : '上传失败', icon: 'none' });
            reject({ statusCode: res.statusCode, detail, raw: data });
          }
        } catch (e) {
          wx.showToast({ title: '上传响应解析失败', icon: 'none' });
          reject({ statusCode: res.statusCode, detail: '上传响应解析失败', raw: res.data });
        }
      },
      fail(err) {
        const msg = (err && err.errMsg) || '上传失败';
        wx.showToast({ title: msg, icon: 'none' });
        reject({ statusCode: 0, detail: msg, raw: err });
      }
    });

    if (onProgress && uploadTask) {
      uploadTask.onProgressUpdate(res => {
        onProgress(res.progress, res.totalBytesSent, res.totalBytesExpectedToSend);
      });
    }
  });
}

module.exports = { fetchUploadLimits, checkFileSize, uploadWithProgress };
