App({
  onLaunch: function () {
    this.checkLogin()
  },

  checkLogin: function () {
    const token = wx.getStorageSync('token')
    const userInfo = wx.getStorageSync('userInfo')
    if (token && userInfo) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo
    }
  },

  globalData: {
    token: '',
    userInfo: null,
    baseUrl: 'https://api.binnixiaokang.com'
  }
})
