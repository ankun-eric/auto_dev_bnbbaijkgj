const { get } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '可使用', status: 'unused' },
      { label: '已使用', status: 'used' },
      { label: '已过期', status: 'expired' }
    ],
    coupons: [],
    loading: false
  },

  onLoad() {
    this.loadCoupons();
  },

  onPullDownRefresh() {
    this.loadCoupons().finally(() => wx.stopPullDownRefresh());
  },

  switchTab(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentTab: idx });
    this.loadCoupons();
  },

  async loadCoupons() {
    this.setData({ loading: true });
    const status = this.data.tabs[this.data.currentTab].status;
    try {
      const res = await get('/api/coupons/mine', { tab: status }, { showLoading: false });
      this.setData({ coupons: res.items || res || [] });
    } catch (e) {
      console.log('loadCoupons error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  useCoupon(e) {
    wx.navigateTo({ url: '/pages/products/index' });
  }
});
