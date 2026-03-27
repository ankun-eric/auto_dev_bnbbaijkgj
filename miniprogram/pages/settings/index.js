const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    userInfo: {},
    healthReminder: true,
    orderNotify: true,
    activityPush: false,
    cacheSize: '2.3 MB'
  },

  onShow() {
    this.setData({
      isLoggedIn: app.globalData.isLoggedIn,
      userInfo: app.globalData.userInfo || {}
    });
  },

  editNickname() {
    wx.showModal({
      title: '修改昵称',
      editable: true,
      placeholderText: '请输入新昵称',
      success: (res) => {
        if (res.confirm && res.content) {
          const userInfo = { ...this.data.userInfo, nickname: res.content.trim() };
          this.setData({ userInfo });
          app.globalData.userInfo = userInfo;
          wx.setStorageSync('userInfo', userInfo);
          wx.showToast({ title: '修改成功', icon: 'success' });
        }
      }
    });
  },

  editAvatar() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath;
        const userInfo = { ...this.data.userInfo, avatar: tempFilePath };
        this.setData({ userInfo });
        app.globalData.userInfo = userInfo;
        wx.setStorageSync('userInfo', userInfo);
        wx.showToast({ title: '头像已更新', icon: 'success' });
      }
    });
  },

  toggleHealthReminder(e) {
    this.setData({ healthReminder: e.detail.value });
  },

  toggleOrderNotify(e) {
    this.setData({ orderNotify: e.detail.value });
  },

  toggleActivityPush(e) {
    this.setData({ activityPush: e.detail.value });
  },

  clearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '确定清除所有缓存数据吗？',
      success: (res) => {
        if (res.confirm) {
          wx.clearStorageSync();
          this.setData({ cacheSize: '0 KB' });
          wx.showToast({ title: '缓存已清除', icon: 'success' });
        }
      }
    });
  },

  showAbout() {
    wx.showModal({
      title: '关于宾尼小康',
      content: '宾尼小康AI健康管家 v1.0.0\n\n致力于为您提供智能、便捷、专业的健康管理服务。\n\n© 2026 宾尼小康',
      showCancel: false
    });
  },

  showAgreement() {
    wx.showModal({
      title: '用户服务协议',
      content: '用户协议内容正在完善中，请稍后查看。',
      showCancel: false
    });
  },

  showPrivacy() {
    wx.showModal({
      title: '隐私政策',
      content: '隐私政策内容正在完善中，请稍后查看。',
      showCancel: false
    });
  },

  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          app.logout();
          wx.showToast({ title: '已退出', icon: 'success' });
          setTimeout(() => {
            wx.switchTab({ url: '/pages/home/index' });
          }, 1500);
        }
      }
    });
  }
});
