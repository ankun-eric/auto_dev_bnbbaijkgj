// [PRD-FAMILY-GUARDIAN-V1] 老人注册后虚拟档案迁移确认页
const { get, post } = require('../../utils/request');

Page({
  data: {
    loading: true,
    items: [],
    processing: false,
  },

  onShow() {
    this.fetchPending();
  },

  async fetchPending() {
    try {
      const res = await get('/api/me/pending-migrations');
      this.setData({ items: res.items || [], loading: false });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: '获取失败', icon: 'none' });
    }
  },

  async onConfirm(e) {
    if (this.data.processing) return;
    const id = e.currentTarget.dataset.id;
    this.setData({ processing: true });
    try {
      await post(`/api/me/migrations/${id}/confirm`);
      wx.showToast({ title: '已确认接管', icon: 'success' });
      this.fetchPending();
    } catch (err) {
      wx.showToast({ title: (err && err.detail) || '操作失败', icon: 'none' });
    } finally {
      this.setData({ processing: false });
    }
  },

  async onReject(e) {
    if (this.data.processing) return;
    const id = e.currentTarget.dataset.id;
    this.setData({ processing: true });
    try {
      await post(`/api/me/migrations/${id}/reject`);
      wx.showToast({ title: '已拒绝', icon: 'none' });
      this.fetchPending();
    } catch (err) {
      wx.showToast({ title: (err && err.detail) || '操作失败', icon: 'none' });
    } finally {
      this.setData({ processing: false });
    }
  },

  goHome() {
    wx.switchTab({ url: '/pages/home/index' });
  },
});
