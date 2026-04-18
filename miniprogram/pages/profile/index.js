const { syncTabBar } = require('../../utils/util');
const { get } = require('../../utils/request');

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
    couponCount: 0,
    favoriteCount: 0,
    orderCount: 0,
    familyCount: 0,
    checkDays: 0,
    orderTabs: [
      { label: '待付款', icon: '💰', status: 'pending_payment' },
      { label: '待收货', icon: '📦', status: 'pending_receipt' },
      { label: '待使用', icon: '🎫', status: 'pending_use' },
      { label: '待评价', icon: '⭐', status: 'pending_review' },
      { label: '退款', icon: '💔', status: 'refund' }
    ],
    menuList: [
      { id: 'member', label: '会员卡', icon: '💳', path: '/pages/member-card/index' },
      { id: 'addresses', label: '地址管理', icon: '📍', path: '/pages/my-addresses/index' },
      { id: 'health', label: '健康档案', icon: '📋', path: '/pages/health-profile/index' },
      { id: 'plan', label: '健康计划', icon: '📅', path: '/pages/health-plan/index' },
      { id: 'invite', label: '邀请好友', icon: '🎁', path: '/pages/invite/index' },
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
      const userInfo = app.getUserInfo();
      this.setData({
        points: (userInfo && userInfo.points) || 0
      });

      get('/api/users/me/stats', {}, { showLoading: false, suppressErrorToast: true })
        .then(res => {
          this.setData({
            points: Number(res.points || 0),
            couponCount: Number(res.coupon_count || 0),
            favoriteCount: Number(res.favorite_count || 0)
          });
        })
        .catch(() => {});
    } catch (e) {
      console.log('loadUserData error', e);
    }
  },

  goMemberCard() {
    wx.navigateTo({ url: '/pages/member-card/index' });
  },

  goCoupons() {
    wx.navigateTo({ url: '/pages/my-coupons/index' });
  },

  goFavorites() {
    wx.navigateTo({ url: '/pages/my-favorites/index' });
  },

  goUnifiedOrders(e) {
    const status = (e && e.currentTarget.dataset.status) || '';
    wx.navigateTo({ url: `/pages/unified-orders/index?status=${status}` });
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

  copyUserNo() {
    const userNo = this.data.userInfo && this.data.userInfo.user_no;
    if (!userNo) return;
    wx.setClipboardData({
      data: userNo,
      success() {
        wx.showToast({ title: '用户编号已复制', icon: 'success' });
      }
    });
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
