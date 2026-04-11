const { get, post } = require('../../utils/request');

Page({
  data: {
    code: '',
    loading: true,
    invitation: null,
    error: '',
    processing: false,
    resultStatus: '',
    resultMessage: ''
  },

  onLoad(options) {
    const code = options.code || options.scene || '';
    if (code) {
      this.setData({ code });
      this.loadInvitation(code);
    } else {
      this.setData({ loading: false, error: '无效的邀请链接' });
    }
  },

  async loadInvitation(code) {
    try {
      const res = await get(`/api/family/invitation/${code}`);
      if (res.status && res.status !== 'pending') {
        this.setData({
          loading: false,
          error: res.status === 'accepted' ? '该邀请已被接受' : '该邀请已失效'
        });
        return;
      }
      this.setData({ invitation: res, loading: false });
    } catch (e) {
      let msg = '获取邀请信息失败';
      if (e && e.statusCode === 404) msg = '邀请不存在或已过期';
      if (e && e.statusCode === 410) msg = '邀请已过期';
      this.setData({ loading: false, error: msg });
    }
  },

  async onAccept() {
    if (this.data.processing) return;
    this.setData({ processing: true });
    try {
      await post(`/api/family/invitation/${this.data.code}/accept`);
      this.setData({
        processing: false,
        resultStatus: 'success',
        resultMessage: '授权成功！对方现在可以查看和管理您的健康档案。'
      });
    } catch (e) {
      this.setData({
        processing: false,
        resultStatus: 'error',
        resultMessage: (e && e.detail) || '授权失败，请重试'
      });
    }
  },

  async onReject() {
    if (this.data.processing) return;
    wx.showModal({
      title: '拒绝邀请',
      content: '确定要拒绝此关联邀请吗？',
      success: async (res) => {
        if (!res.confirm) return;
        this.setData({ processing: true });
        try {
          await post(`/api/family/invitation/${this.data.code}/reject`);
          this.setData({
            processing: false,
            resultStatus: 'rejected',
            resultMessage: '已拒绝该邀请'
          });
        } catch (e) {
          this.setData({
            processing: false,
            resultStatus: 'error',
            resultMessage: (e && e.detail) || '操作失败，请重试'
          });
        }
      }
    });
  },

  goHome() {
    wx.switchTab({ url: '/pages/home/index' });
  },

  goBindList() {
    wx.navigateTo({ url: '/pages/family-bindlist/index' });
  }
});
