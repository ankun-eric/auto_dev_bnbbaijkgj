Page({
  data: {
    title: '暂无商家权限',
    desc: '当前账号未开通商家身份，请返回用户端继续使用。'
  },

  onLoad(options) {
    if (options && options.scene === 'user') {
      this.setData({
        title: '暂无用户权限',
        desc: '当前账号仅开通商家身份，不支持进入用户端。'
      });
    }
  },

  goHome() {
    const app = getApp();
    if (app.hasUserIdentity()) {
      app.setCurrentRole('user');
    }
    wx.switchTab({ url: '/pages/home/index' });
  }
});
