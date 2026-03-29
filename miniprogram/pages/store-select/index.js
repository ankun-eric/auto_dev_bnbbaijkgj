const { get } = require('../../utils/request');

Page({
  data: {
    stores: [],
    loading: false
  },

  onLoad() {
    this.loadStores();
  },

  async loadStores() {
    const app = getApp();
    if (!app.globalData.isLoggedIn) {
      wx.redirectTo({ url: '/pages/login/index' });
      return;
    }
    if (!app.hasMerchantIdentity()) {
      wx.redirectTo({ url: '/pages/no-permission/index?scene=merchant' });
      return;
    }
    this.setData({ loading: true });
    try {
      const res = await get('/api/merchant/stores', {}, { showLoading: false });
      this.setData({ stores: res.items || [] });
    } catch (e) {
      wx.showToast({ title: e.detail || '门店加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectStore(e) {
    const store = e.currentTarget.dataset.store;
    if (!store) return;
    const app = getApp();
    app.setCurrentRole('merchant');
    app.setCurrentStore(store);
    wx.reLaunch({ url: '/pages/home/index' });
  }
});
