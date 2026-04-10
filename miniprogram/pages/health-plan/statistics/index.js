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
      if (res) {
        res.streak_days = res.consecutive_days || res.streak_days || 0;
        res.total_checkins = res.today_completed || 0;
        res.today_pending = (res.today_total || 0) - (res.today_completed || 0);
        if (res.weekly_data && res.weekly_data.length > 0) {
          const maxCount = Math.max(...res.weekly_data.map(function(d) { return d.count || 0; }), 1);
          res.weekly_data = res.weekly_data.map(function(d) {
            const dateObj = new Date(d.date);
            const dayNames = ['日', '一', '二', '三', '四', '五', '六'];
            return {
              day: '周' + dayNames[dateObj.getDay()],
              count: d.count || 0,
              rate: Math.round(((d.count || 0) / maxCount) * 100),
            };
          });
        }
      }
      this.setData({ stats: res || {} });
    } catch (e) {
      this.setData({ stats: {} });
    } finally {
      this.setData({ loading: false });
    }
  }
});
