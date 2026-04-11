const { get, del } = require('../../utils/request');

Page({
  data: {
    loading: true,
    list: [],
    empty: false
  },

  onLoad() {
    this.loadList();
  },

  onShow() {
    if (!this.data.loading) {
      this.loadList();
    }
  },

  async loadList() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/family/managed-by', {}, { showLoading: false });
      const items = res && res.items ? res.items : [];
      this.setData({
        list: items,
        loading: false,
        empty: items.length === 0
      });
    } catch (e) {
      this.setData({ list: [], loading: false, empty: true });
    }
  },

  onRevoke(e) {
    const item = e.currentTarget.dataset.item;
    const name = item.manager_nickname || '对方';
    wx.showModal({
      title: '取消授权',
      content: `确定要取消「${name}」对您健康档案的管理权限吗？`,
      confirmColor: '#ff4d4f',
      confirmText: '确认取消',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/family/management/${item.id}`);
          wx.showToast({ title: '已取消授权', icon: 'success' });
          this.loadList();
        } catch (e) {
          wx.showToast({ title: '操作失败', icon: 'none' });
        }
      }
    });
  },

  onPullDownRefresh() {
    this.loadList().then(() => {
      wx.stopPullDownRefresh();
    });
  }
});
