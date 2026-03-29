const { get, put } = require('../../utils/request');
const { ensureMerchantEntry } = require('../../utils/util');

Page({
  data: {
    notifications: [],
    unreadCount: 0
  },

  onShow() {
    if (!ensureMerchantEntry()) return;
    this.loadData();
  },

  async loadData() {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    if (!currentStore) return;
    try {
      const res = await get('/api/merchant/notifications', { store_id: currentStore.id }, { showLoading: false });
      this.setData({
        notifications: res.items || [],
        unreadCount: res.unread_count || 0
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '消息加载失败', icon: 'none' });
    }
  },

  async readNotify(e) {
    const item = e.currentTarget.dataset.item;
    if (!item || item.is_read) return;
    try {
      await put(`/api/merchant/notifications/${item.id}/read`, {});
      this.loadData();
    } catch (e2) {
      wx.showToast({ title: e2.detail || '操作失败', icon: 'none' });
    }
  },

  async clearAll() {
    try {
      await put('/api/merchant/notifications/read-all', {});
      this.loadData();
      wx.showToast({ title: '全部已读', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: e.detail || '操作失败', icon: 'none' });
    }
  }
});
