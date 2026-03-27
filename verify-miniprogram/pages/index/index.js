const { get } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    userName: '',
    todayCount: 0,
    todayAmount: '0.00'
  },

  onLoad: function () {
    this.checkAuth()
  },

  onShow: function () {
    if (app.globalData.token) {
      this.loadUserInfo()
      this.loadTodayStats()
    }
  },

  checkAuth: function () {
    if (!app.globalData.token) {
      wx.redirectTo({ url: '/pages/login/index' })
    }
  },

  loadUserInfo: function () {
    try {
      const userInfoStr = wx.getStorageSync('userInfo')
      if (userInfoStr) {
        const userInfo = typeof userInfoStr === 'string' ? JSON.parse(userInfoStr) : userInfoStr
        this.setData({
          userName: userInfo.name || userInfo.nickname || '工作人员'
        })
      }
    } catch (e) {
      this.setData({ userName: '工作人员' })
    }
  },

  loadTodayStats: function () {
    get('/api/orders', { page: 1, page_size: 1 }).then(res => {
      this.setData({
        todayCount: res.total || 0,
        todayAmount: '0.00'
      })
    }).catch(() => {
    })
  },

  goScan: function () {
    wx.navigateTo({ url: '/pages/scan/index' })
  },

  goRecords: function () {
    wx.navigateTo({ url: '/pages/records/index' })
  },

  handleLogout: function () {
    wx.showModal({
      title: '确认退出',
      content: '确定要退出登录吗？',
      confirmColor: '#52c41a',
      success: function (res) {
        if (res.confirm) {
          wx.removeStorageSync('token')
          wx.removeStorageSync('userInfo')
          app.globalData.token = ''
          app.globalData.userInfo = null
          wx.reLaunch({ url: '/pages/login/index' })
        }
      }
    })
  }
})
