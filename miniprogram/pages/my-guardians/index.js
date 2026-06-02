const { get, post } = require('../../utils/request');

// [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 守护我的人卡片：支持 active+pending 列表、查看邀请码、统一文案
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
      // 标记 pending / active
      const mapped = items.map((it) => ({
        ...it,
        _isPending: it.item_type === 'pending',
      }));
      this.setData({ guardians: mapped, loading: false });
    } catch (_) {
      this.setData({ guardians: [], loading: false });
    }
  },

  onRemoveGuardian(e) {
    const { id, nickname } = e.currentTarget.dataset;
    if (this.data.removing) return;
    // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 统一二次确认文案
    wx.showModal({
      title: '解除守护',
      content: '解除后对方将无法查看您的健康数据，确定解除吗？',
      cancelText: '取消',
      confirmText: '确定',
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

  // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 取消邀请
  onCancelInvite(e) {
    const { id, code } = e.currentTarget.dataset;
    wx.showModal({
      title: '取消邀请',
      content: '取消后该邀请将立即失效，您可以重新发起邀请。是否确认取消？',
      cancelText: '不取消',
      confirmText: '确定取消',
      success: async (r) => {
        if (!r.confirm) return;
        try {
          await post('/api/reverse-guardian/invite/cancel', { invitation_id: id, invite_code: code });
          wx.showToast({ title: '已取消邀请', icon: 'success' });
          this.fetchGuardians();
        } catch (err) {
          const msg = (err && (err.message || err.detail)) || '取消失败';
          wx.showToast({ title: String(msg), icon: 'none' });
        }
      },
    });
  },

  // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 查看邀请码（重新打开二维码页）
  onViewInviteCode(e) {
    const { code } = e.currentTarget.dataset;
    if (!code) {
      wx.showToast({ title: '邀请码无效', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: `/pages/reverse-invite/index?code=${encodeURIComponent(code)}` });
  },

  onInviteGuardian() {
    wx.navigateTo({ url: '/pages/reverse-invite/index' });
  },
});
