const { get } = require('../../utils/request');
const app = getApp();

Page({
  data: {
    shareLink: '',
    userNo: '',
    loading: true
  },

  onLoad() {
    this.loadShareLink();
  },

  async loadShareLink() {
    try {
      const res = await get('/api/users/share-link', {}, { showLoading: true });
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
