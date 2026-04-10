const { get, post, del } = require('../../../utils/request');

Page({
  data: {
    items: [],
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
      const res = await get('/api/health-plan/checkin-items', {}, { showLoading: false });
      const items = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      this.setData({ items });
    } catch (e) {
      this.setData({ items: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  goAdd() {
    wx.navigateTo({ url: '/pages/health-plan/checkin-form/index' });
  },

  goEdit(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/checkin-form/index?id=${id}` });
  },

  async onCheckin(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await post(`/api/health-plan/checkin-items/${id}/checkin`, {});
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这个打卡项目吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/health-plan/checkin-items/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadList();
        } catch (e) {
          // error handled by request
        }
      }
    });
  }
});
