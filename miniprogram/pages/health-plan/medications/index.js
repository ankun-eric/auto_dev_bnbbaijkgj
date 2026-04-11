const { get, post, put, del } = require('../../../utils/request');
const { showCheckinPointsToast } = require('../../../utils/checkin-points');

Page({
  data: {
    medications: [],
    medGroups: [],
    loading: false,
    pointsRefreshKey: 0
  },

  onShow() {
    this.loadList();
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh());
  },

  async loadList() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/health-plan/medications', {}, { showLoading: false });
      let items = [];
      let medGroups = [];
      if (res && res.groups && typeof res.groups === 'object') {
        var groupKeys = Object.keys(res.groups);
        groupKeys.forEach(function(period) {
          var groupItems = res.groups[period];
          if (!Array.isArray(groupItems)) return;
          var mapped = groupItems.map(function(item) {
            return Object.assign({}, item, {
              name: item.medicine_name || item.name,
              frequency: item.time_period || item.frequency,
              remind_times: item.remind_time || item.remind_times,
            });
          });
          items = items.concat(mapped);
          medGroups.push({ period: period, items: mapped });
        });
      } else {
        var raw = Array.isArray(res) ? res : (res && res.items ? res.items : []);
        items = raw.map(function(item) {
          return Object.assign({}, item, {
            name: item.medicine_name || item.name,
            frequency: item.time_period || item.frequency,
            remind_times: item.remind_time || item.remind_times,
          });
        });
      }
      this.setData({ medications: items, medGroups: medGroups });
    } catch (e) {
      this.setData({ medications: [], medGroups: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  goAdd() {
    wx.navigateTo({ url: '/pages/health-plan/medication-form/index' });
  },

  goEdit(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/medication-form/index?id=${id}` });
  },

  async onCheckin(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const result = await post(`/api/health-plan/medications/${id}/checkin`, {});
      showCheckinPointsToast(result);
      this.setData({ pointsRefreshKey: this.data.pointsRefreshKey + 1 });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  async onTogglePause(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await put(`/api/health-plan/medications/${id}/pause`, {});
      wx.showToast({ title: '操作成功', icon: 'success' });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这条用药提醒吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/health-plan/medications/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadList();
        } catch (e) {
          // error handled by request
        }
      }
    });
  }
});
