Page({
  data: {
    status: '',
    orderNo: '',
    reason: ''
  },

  onLoad: function (options) {
    this.setData({
      status: options.status || 'fail',
      orderNo: options.orderNo || '',
      reason: decodeURIComponent(options.reason || '')
    })
  },

  goScanAgain: function () {
    wx.redirectTo({ url: '/pages/scan/index' })
  },

  goHome: function () {
    wx.navigateBack({
      delta: 10,
      fail: function () {
        wx.reLaunch({ url: '/pages/index/index' })
      }
    })
  }
})
