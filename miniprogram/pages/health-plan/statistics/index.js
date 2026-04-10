const { get } = require('../../../utils/request');

Page({
  data: {
    stats: null,
    loading: false
  },

  onShow() {
    this.loadStats();
  },

  onPullDownRefresh() {
    this.loadStats().finally(() => wx.stopPullDownRefresh());
  },

  async loadStats() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/health-plan/statistics', {}, { showLoading: false });
      this.setData({ stats: res || {} });
    } catch (e) {
      this.setData({ stats: {} });
    } finally {
      this.setData({ loading: false });
    }
  }
});
