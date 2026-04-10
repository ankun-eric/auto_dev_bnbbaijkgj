const { get, post, put, del } = require('../../../utils/request');

Page({
  data: {
    medications: [],
    loading: false
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
      if (res && res.groups && typeof res.groups === 'object') {
        Object.values(res.groups).forEach(function(groupItems) {
          if (Array.isArray(groupItems)) {
            groupItems.forEach(function(item) {
              items.push(Object.assign({}, item, {
                name: item.medicine_name || item.name,
                frequency: item.time_period || item.frequency,
                remind_times: item.remind_time || item.remind_times,
              }));
            });
          }
        });
      } else {
        items = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      }
      this.setData({ medications: items });
    } catch (e) {
      this.setData({ medications: [] });
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
      await post(`/api/health-plan/medications/${id}/checkin`, {});
      wx.showToast({ title: '打卡成功', icon: 'success' });
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
