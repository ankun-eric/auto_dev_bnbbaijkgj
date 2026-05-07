const app = getApp();

// [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
// 改约错误码 → 文案映射，与后端 RESCHEDULE_* 常量保持一致。
const RESCHEDULE_ERROR_TEXT = {
  RESCHEDULE_NO_PERMISSION: '无权操作此订单',
  RESCHEDULE_ORDER_NOT_FOUND: '订单不存在或无权操作此订单',
  RESCHEDULE_ORDER_STATUS_INVALID: '当前订单状态不允许改约',
  RESCHEDULE_LIMIT_EXCEEDED: '该订单已达改约次数上限，无法继续改约',
  RESCHEDULE_NOT_ALLOWED: '该商品不支持改约',
  RESCHEDULE_TIME_EXPIRED: '所选时段已过期，请选择未来时间',
  RESCHEDULE_TIME_OUT_OF_RANGE: '所选日期超出可改约范围',
  RESCHEDULE_TIME_CONFLICT: '所选时段已被预约满，请选其他时段',
  RESCHEDULE_REFUND_IN_PROGRESS: '该订单退款处理中，暂不允许调整预约时间',
  RESCHEDULE_PARTIALLY_USED: '该订单已部分核销，无法修改预约时间',
  RESCHEDULE_INTERNAL_ERROR: '改约失败，请稍后重试或联系客服',
};

function formatErrorDetail(data) {
  if (data == null) return '网络请求失败';
  if (typeof data === 'string') return data;
  if (typeof data !== 'object') return '网络请求失败';

  const d = data.detail;
  // [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
  // 后端新版结构化错误：detail 是对象 {code, message, detail}
  if (d && typeof d === 'object' && !Array.isArray(d)) {
    if (typeof d.code === 'string' && RESCHEDULE_ERROR_TEXT[d.code]) {
      return RESCHEDULE_ERROR_TEXT[d.code];
    }
    if (typeof d.message === 'string' && d.message) return d.message;
    if (typeof d.detail === 'string' && d.detail) return d.detail;
  }
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
  if (typeof data.code === 'string' && RESCHEDULE_ERROR_TEXT[data.code]) {
    return RESCHEDULE_ERROR_TEXT[data.code];
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
      // [客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 顾客微信小程序固定来源标识
      // 后端 require_customer_client_session 依赖项据此放行订单顾客专属接口
      // （改期/取消/退款/确认/评价/下单/支付等），避免商家兼顾客用户被一刀切。
      'Client-Type': 'miniprogram-user',
      'X-Client-Type': 'miniprogram-user',
      // [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
      // 顾客端入口标识：后端据此识别"以顾客身份发起"，使双重身份用户的改约请求
      // 跳过商家身份限制、不卡改约次数。
      'X-Client-Source': 'miniprogram-customer',
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
    const headers = {
      // [客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 上传场景同样标识为顾客小程序
      'Client-Type': 'miniprogram-user',
      'X-Client-Type': 'miniprogram-user',
      // [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0] 顾客端入口标识
      'X-Client-Source': 'miniprogram-customer',
    };
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
