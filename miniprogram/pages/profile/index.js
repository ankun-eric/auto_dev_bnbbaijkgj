const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    userInfo: null,
    points: 0,
    orderCount: 0,
    familyCount: 0,
    checkDays: 0,
    menuList: [
      { id: 'health', label: '健康档案', icon: '📋', path: '/pages/health-profile/index' },
      { id: 'family', label: '家庭成员', icon: '👨‍👩‍👧‍👦', path: '/pages/family/index' },
      { id: 'points', label: '积分中心', icon: '🎯', path: '/pages/points/index' },
      { id: 'mall', label: '积分商城', icon: '🛍️', path: '/pages/points-mall/index' },
      { id: 'plan', label: '健康计划', icon: '📅', path: '/pages/health-plan/index' },
      { id: 'service', label: '在线客服', icon: '🎧', path: '/pages/customer-service/index' },
      { id: 'settings', label: '设置', icon: '⚙️', path: '/pages/settings/index' }
    ]
  },

  onShow() {
    this.setData({
      isLoggedIn: app.globalData.isLoggedIn,
      userInfo: app.globalData.userInfo
    });
    if (app.globalData.isLoggedIn) {
      this.loadUserData();
    }
  },

  async loadUserData() {
    try {
      // const res = await get('/api/auth/me');
      // this.setData({ ...res.data });
      this.setData({
        points: 1280,
        orderCount: 5,
        familyCount: 3,
        checkDays: 15
      });
    } catch (e) {
      console.log('loadUserData error', e);
    }
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/index' });
  },

  goHealthProfile() {
    wx.navigateTo({ url: '/pages/health-profile/index' });
  },

  goPoints() {
    wx.navigateTo({ url: '/pages/points/index' });
  },

  goOrders(e) {
    const status = e.currentTarget.dataset.status || '';
    wx.navigateTo({ url: `/pages/orders/index?status=${status}` });
  },

  goFamily() {
    wx.navigateTo({ url: '/pages/family/index' });
  },

  onMenuTap(e) {
    const item = e.currentTarget.dataset.item;
    wx.navigateTo({ url: item.path });
  }
});
