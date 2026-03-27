const app = getApp();

function request(options) {
  const { url, method = 'GET', data = {}, header = {}, showLoading = true } = options;

  if (showLoading) {
    wx.showLoading({ title: '加载中...', mask: true });
  }

  return new Promise((resolve, reject) => {
    const token = app.globalData.token;
    wx.request({
      url: app.globalData.baseUrl + url,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...header
      },
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
          reject(res.data);
        } else {
          wx.showToast({ title: '网络请求失败', icon: 'none' });
          reject(res.data);
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading();
        wx.showToast({ title: '网络连接失败', icon: 'none' });
        reject(err);
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

function uploadFile(url, filePath, name = 'file', formData = {}) {
  const token = app.globalData.token;
  wx.showLoading({ title: '上传中...', mask: true });

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: app.globalData.baseUrl + url,
      filePath,
      name,
      formData,
      header: {
        'Authorization': token ? `Bearer ${token}` : ''
      },
      success(res) {
        wx.hideLoading();
        const data = JSON.parse(res.data);
        resolve(data);
      },
      fail(err) {
        wx.hideLoading();
        wx.showToast({ title: '上传失败', icon: 'none' });
        reject(err);
      }
    });
  });
}

module.exports = { request, get, post, put, del, uploadFile };
