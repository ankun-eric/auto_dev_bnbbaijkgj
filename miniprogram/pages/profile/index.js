const { syncTabBar } = require('../../utils/util');

const app = getApp();

Page({
  data: {
    pageMode: 'user',
    isLoggedIn: false,
    userInfo: null,
    merchantProfile: null,
    currentStore: null,
    canSwitchRole: false,
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
    ],
    merchantMenuList: [
      { id: 'store', label: '重新选择门店', icon: '🏪', path: '/pages/store-select/index' },
      { id: 'message', label: '商家消息', icon: '🔔', path: '/pages/merchant-messages/index' }
    ]
  },

  onShow() {
    syncTabBar(this, '/pages/profile/index');
    const pageMode = app.getCurrentRole() || 'user';
    const userInfo = app.getUserInfo();
    const merchantProfile = app.getMerchantProfile();
    if (pageMode === 'merchant') {
      if (!app.hasMerchantIdentity()) {
        wx.navigateTo({ url: '/pages/no-permission/index?scene=merchant' });
        return;
      }
      if (!app.getCurrentStore()) {
        wx.navigateTo({ url: '/pages/store-select/index' });
        return;
      }
    } else if (app.globalData.isLoggedIn && !app.hasUserIdentity()) {
      wx.navigateTo({ url: '/pages/no-permission/index?scene=user' });
      return;
    }

    this.setData({
      pageMode,
      isLoggedIn: app.globalData.isLoggedIn,
      userInfo,
      merchantProfile,
      currentStore: app.getCurrentStore(),
      canSwitchRole: app.isDualIdentity()
    });

    if (pageMode === 'user') {
      if (app.globalData.isLoggedIn) {
        this.loadUserData();
      }
    }
  },

  async loadUserData() {
    try {
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

  switchRole() {
    if (!app.isDualIdentity()) return;
    const currentRole = this.data.pageMode;
    const targetRole = currentRole === 'merchant' ? 'user' : 'merchant';
    const targetLabel = targetRole === 'merchant' ? '商家端' : '用户端';
    wx.showModal({
      title: '切换角色',
      content: `确认切换到${targetLabel}吗？`,
      success: (res) => {
        if (!res.confirm) return;
        app.setCurrentRole(targetRole);
        if (targetRole === 'merchant') {
          app.clearCurrentStore();
          wx.navigateTo({ url: '/pages/store-select/index' });
          return;
        }
        wx.switchTab({ url: '/pages/home/index' });
      }
    });
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
  },

  logout() {
    wx.showModal({
      title: '确认退出',
      content: '确定要退出当前账号吗？',
      success: (res) => {
        if (!res.confirm) return;
        app.logout();
        wx.reLaunch({ url: '/pages/login/index' });
      }
    });
  }
});
