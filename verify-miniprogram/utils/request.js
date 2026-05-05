const app = getApp()

function request(options) {
  return new Promise((resolve, reject) => {
    const token = app.globalData.token || wx.getStorageSync('token')
    const header = {
      'Content-Type': 'application/json',
      // [PRD-05 核销动作收口手机端 v1.0] 显式声明客户端类型为「核销小程序」，
      // 后端 require_mobile_verify_client 依赖项据此放行核销动作；缺失时被识别为 unknown 并 403。
      'Client-Type': 'verify-miniprogram',
      'X-Client-Type': 'verify-miniprogram',
    }
    if (token) {
      header['Authorization'] = 'Bearer ' + token
    }

    wx.request({
      url: app.globalData.baseUrl + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: Object.assign(header, options.header || {}),
      success: function (res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync('token')
          wx.removeStorageSync('userInfo')
          app.globalData.token = ''
          app.globalData.userInfo = null
          wx.redirectTo({ url: '/pages/login/index' })
          reject(new Error('登录已过期，请重新登录'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(res.data || { message: '请求失败' })
        }
      },
      fail: function (err) {
        wx.showToast({ title: '网络异常', icon: 'none' })
        reject(err)
      }
    })
  })
}

function get(url, data) {
  return request({ url, method: 'GET', data })
}

function post(url, data) {
  return request({ url, method: 'POST', data })
}

module.exports = { request, get, post }
