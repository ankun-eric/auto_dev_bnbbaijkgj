const { post } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    phone: '',
    password: '',
    showPassword: false,
    loading: false
  },

  onPhoneInput: function (e) {
    this.setData({ phone: e.detail.value })
  },

  onPasswordInput: function (e) {
    this.setData({ password: e.detail.value })
  },

  togglePassword: function () {
    this.setData({ showPassword: !this.data.showPassword })
  },

  handleLogin: function () {
    const { phone, password } = this.data
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }

    this.setData({ loading: true })

    post('/api/auth/login', {
      phone: phone,
      password: password
    }).then(res => {
      const token = res.access_token
      const userInfo = res.user
      app.globalData.token = token
      app.globalData.userInfo = userInfo
      wx.setStorageSync('token', token)
      wx.setStorageSync('userInfo', JSON.stringify(userInfo))
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(function () {
        wx.reLaunch({ url: '/pages/index/index' })
      }, 1000)
    }).catch(err => {
      wx.showToast({ title: (err && err.detail) || '登录失败，请重试', icon: 'none' })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
