const app = getApp();

function formatErrorDetail(data) {
  if (data == null) return '网络请求失败';
  if (typeof data === 'string') return data;
  if (typeof data !== 'object') return '网络请求失败';

  const d = data.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d.length) {
    const first = d[0];
    if (typeof first === 'string') return first;
    if (first && typeof first.msg === 'string') return first.msg;
    try {
      return JSON.stringify(first);
    } catch (_) {
      return '请求参数错误';
    }
  }
  if (typeof data.message === 'string') return data.message;
  return '网络请求失败';
}

function request(options) {
  const {
    url,
    method = 'GET',
    data = {},
    header = {},
    showLoading = true,
    suppressErrorToast = false
  } = options;

  if (showLoading) {
    wx.showLoading({ title: '加载中...', mask: true });
  }

  return new Promise((resolve, reject) => {
    const token = app.globalData.token;
    const headers = {
      'Content-Type': 'application/json',
      ...header
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    wx.request({
      url: app.globalData.baseUrl + url,
      method,
      data,
      header: headers,
      success(res) {
        if (showLoading) wx.hideLoading();

        if (res.statusCode === 200) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          app.logout();
          wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' });
          setTimeout(() => {
            wx.navigateTo({ url: '/pages/login/index' });
          }, 1500);
          const detail = formatErrorDetail(res.data);
          reject({
            statusCode: res.statusCode,
            detail,
            raw: res.data
          });
        } else {
          const detail = formatErrorDetail(res.data);
          if (!suppressErrorToast) {
            wx.showToast({
              title: detail.length > 60 ? detail.slice(0, 60) + '…' : detail,
              icon: 'none',
              duration: 3000
            });
          }
          reject({
            statusCode: res.statusCode,
            detail,
            raw: res.data
          });
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading();
        const msg = (err && err.errMsg) || '网络连接失败';
        if (!suppressErrorToast) {
          wx.showToast({ title: msg, icon: 'none' });
        }
        reject({
          statusCode: 0,
          detail: msg,
          raw: err
        });
      }
    });
  });
}

function get(url, data, options = {}) {
  return request({ url, method: 'GET', data, ...options });
}

function post(url, data, options = {}) {
  return request({ url, method: 'POST', data, ...options });
}

function put(url, data, options = {}) {
  return request({ url, method: 'PUT', data, ...options });
}

function del(url, data, options = {}) {
  return request({ url, method: 'DELETE', data, ...options });
}

function patch(url, data, options = {}) {
  return request({ url, method: 'PATCH', data, ...options });
}

function uploadFile(url, filePath, name = 'file', formData = {}, options = {}) {
  const { onProgress, showLoading: showLoad = true } = options;
  const token = app.globalData.token;
  if (showLoad) {
    wx.showLoading({ title: '上传中...', mask: true });
  }

  return new Promise((resolve, reject) => {
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const uploadTask = wx.uploadFile({
      url: app.globalData.baseUrl + url,
      filePath,
      name,
      formData,
      header: headers,
      success(res) {
        if (showLoad) wx.hideLoading();
        try {
          const data = JSON.parse(res.data);
          if (res.statusCode === 200) {
            resolve(data);
          } else {
            const detail = formatErrorDetail(data);
            wx.showToast({ title: detail.slice(0, 60), icon: 'none' });
            reject({ statusCode: res.statusCode, detail, raw: data });
          }
        } catch (e) {
          wx.showToast({ title: '上传响应解析失败', icon: 'none' });
          reject({ statusCode: res.statusCode, detail: '上传响应解析失败', raw: res.data });
        }
      },
      fail(err) {
        if (showLoad) wx.hideLoading();
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

module.exports = { request, get, post, put, del, patch, uploadFile };
