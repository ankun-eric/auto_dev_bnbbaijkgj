const { get } = require('../../utils/request');
const app = getApp();

Page({
  data: {
    shareLink: '',
    userNo: '',
    loading: true,
    totalInvited: 0,
    totalPointsEarned: 0,
    inviteList: []
  },

  onLoad() {
    this.loadAll();
  },

  onShow() {
    this.loadStats();
  },

  async loadAll() {
    await Promise.all([this.loadShareLink(), this.loadStats()]);
  },

  async loadShareLink() {
    try {
      const res = await get('/api/users/share-link', {}, { showLoading: false });
      this.setData({
        shareLink: res.share_link || '',
        userNo: res.user_no || '',
        loading: false
      });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: '获取分享链接失败', icon: 'none' });
    }
  },

  async loadStats() {
    try {
      const res = await get('/api/users/invite-stats', { page: 1, page_size: 50 }, { showLoading: false, suppressErrorToast: true });
      const items = (res.items || []).map(it => ({
        ...it,
        registered_at: this._formatTime(it.registered_at),
        display_name: it.nickname || it.phone || it.user_no || `用户${it.user_id}`
      }));
      this.setData({
        totalInvited: res.total_invited || 0,
        totalPointsEarned: res.total_points_earned || 0,
        inviteList: items
      });
    } catch (e) {
      // ignore
    }
  },

  _formatTime(t) {
    if (!t) return '';
    return String(t).replace('T', ' ').slice(0, 16);
  },

  copyShareLink() {
    if (!this.data.shareLink) return;
    wx.setClipboardData({
      data: this.data.shareLink,
      success() {
        wx.showToast({ title: '链接已复制', icon: 'success' });
      }
    });
  },

  onShareAppMessage() {
    return {
      title: '我在用宾尼小康，AI健康管家守护你的健康，快来加入吧！',
      path: `/pages/login/index?ref=${this.data.userNo}`,
      imageUrl: ''
    };
  }
});
