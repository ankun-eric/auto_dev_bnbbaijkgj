const { get, post, uploadFile } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    historyReports: [],
    alerts: [],
    hasUnreadAlerts: false,
    loading: false,
    page: 1,
    pageSize: 10,
    hasMore: true,
    uploading: false
  },

  onLoad() {
    this.loadHistory();
    this.loadAlerts();
  },

  onShow() {
    this.setData({ page: 1, historyReports: [], hasMore: true });
    this.loadHistory();
    this.loadAlerts();
  },

  onPullDownRefresh() {
    this.setData({ page: 1, historyReports: [], hasMore: true });
    Promise.all([this.loadHistory(), this.loadAlerts()]).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadHistory();
    }
  },

  async loadHistory() {
    if (this.data.loading) return;
    this.setData({ loading: true });
    try {
      const res = await get('/api/report/list', {
        page: this.data.page,
        page_size: this.data.pageSize
      }, { showLoading: false, suppressErrorToast: true });
      const items = res.items || res.data || [];
      const list = items.map(item => ({
        ...item,
        dateFormatted: (item.created_at || item.date || '').substring(0, 10),
        abnormalCount: item.abnormal_count || 0,
        thumbnail: item.thumbnail || item.image_url || ''
      }));
      this.setData({
        historyReports: [...this.data.historyReports, ...list],
        page: this.data.page + 1,
        hasMore: list.length >= this.data.pageSize,
        loading: false
      });
    } catch (e) {
      console.log('loadHistory error', e);
      this.setData({ loading: false });
    }
  },

  async loadAlerts() {
    try {
      const res = await get('/api/report/alerts', {}, { showLoading: false, suppressErrorToast: true });
      const alerts = res.items || res.data || res || [];
      const unread = Array.isArray(alerts) ? alerts.filter(a => !a.is_read) : [];
      this.setData({
        alerts: Array.isArray(alerts) ? alerts : [],
        hasUnreadAlerts: unread.length > 0
      });
    } catch (e) {
      console.log('loadAlerts error', e);
    }
  },

  dismissAlert() {
    const unread = this.data.alerts.filter(a => !a.is_read);
    unread.forEach(a => {
      const { put } = require('../../utils/request');
      put(`/api/report/alerts/${a.id}/read`, {}, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    });
    this.setData({ hasUnreadAlerts: false });
  },

  chooseFromAlbum() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 9,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        this.handleUploadFiles(res.tempFiles.map(f => f.tempFilePath));
      }
    });
  },

  takePhoto() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        this.handleUploadFiles(res.tempFiles.map(f => f.tempFilePath));
      }
    });
  },

  choosePDF() {
    if (!checkLogin()) return;
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf'],
      success: (res) => {
        this.handleUploadFiles(res.tempFiles.map(f => f.path));
      }
    });
  },

  async handleUploadFiles(filePaths) {
    if (!filePaths || !filePaths.length) return;
    this.setData({ uploading: true });
    wx.showLoading({ title: '上传中...', mask: true });

    try {
      let lastResult = null;
      for (const path of filePaths) {
        lastResult = await uploadFile('/api/report/upload', path);
      }

      const reportId = lastResult && (lastResult.report_id || lastResult.id);
      if (!reportId) {
        wx.hideLoading();
        this.setData({ uploading: false });
        wx.showToast({ title: '上传成功', icon: 'success' });
        this.setData({ page: 1, historyReports: [], hasMore: true });
        this.loadHistory();
        return;
      }

      wx.showLoading({ title: 'AI解读中...', mask: true });
      await post('/api/report/analyze', { report_id: parseInt(reportId) }, { showLoading: false, suppressErrorToast: true });
      wx.hideLoading();
      this.setData({ uploading: false });
      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${reportId}` });
    } catch (e) {
      wx.hideLoading();
      this.setData({ uploading: false });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  viewReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/checkup-detail/index?id=${id}` });
  }
});
