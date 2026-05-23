const { get, post } = require('../../utils/request');

Page({
  data: {
    guardians: [],
    loading: true,
    removing: false,
  },

  onLoad() {
    this.fetchGuardians();
  },

  onShow() {
    this.fetchGuardians();
  },

  onPullDownRefresh() {
    this.fetchGuardians().finally(() => wx.stopPullDownRefresh());
  },

  async fetchGuardians() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/reverse-guardian/my-guardians', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []);
      this.setData({ guardians: items, loading: false });
    } catch (_) {
      this.setData({ guardians: [], loading: false });
    }
  },

  onRemoveGuardian(e) {
    const { id, nickname } = e.currentTarget.dataset;
    if (this.data.removing) return;
    wx.showModal({
      title: '解除守护',
      content: `确定要解除「${nickname || '该用户'}」对您的守护关系吗？解除后对方将无法查看您的健康档案。`,
      confirmColor: '#DC2626',
      success: async (r) => {
        if (!r.confirm) return;
        this.setData({ removing: true });
        try {
          await post('/api/reverse-guardian/remove', { management_id: id });
          wx.showToast({ title: '已解除', icon: 'success' });
          this.fetchGuardians();
        } catch (_) {
          wx.showToast({ title: '操作失败', icon: 'none' });
        } finally {
          this.setData({ removing: false });
        }
      },
    });
  },

  onInviteGuardian() {
    wx.navigateTo({ url: '/pages/reverse-invite/index' });
  },
});
