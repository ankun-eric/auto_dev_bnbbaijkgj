const { get } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '可用', status: 'unused' },
      { label: '已使用', status: 'used' },
      { label: '已过期', status: 'expired' }
    ],
    coupons: [],
    availableCount: 0,
    loading: false
  },

  onLoad() {
    this.loadCoupons();
  },

  onShow() {
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
      // Bug #3: 可用券数量请求独立接口（tab=unused + exclude_expired=true），
      // 顶部"合计"与 Tab "可用(N)" 均使用该数量，保证一致
      const [listRes, availableRes] = await Promise.all([
        get('/api/coupons/mine', { tab: status }, { showLoading: false }),
        status === 'unused'
          ? Promise.resolve(null)
          : get('/api/coupons/mine', { tab: 'unused', exclude_expired: true }, { showLoading: false }).catch(() => null)
      ]);
      const list = (listRes && (listRes.items || listRes)) || [];
      let availableCount;
      if (status === 'unused') {
        availableCount = (listRes && (listRes.available_count != null ? listRes.available_count : (listRes.available != null ? listRes.available : null)));
        if (availableCount == null) availableCount = list.length;
      } else {
        availableCount = (availableRes && (availableRes.available_count != null ? availableRes.available_count : (availableRes.available != null ? availableRes.available : (availableRes.total != null ? availableRes.total : (availableRes.items ? availableRes.items.length : 0)))));
      }
      this.setData({
        coupons: list,
        availableCount: Number(availableCount) || 0
      });
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
