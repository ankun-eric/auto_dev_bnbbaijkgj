const { get, uploadFile } = require('../../utils/request');
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
    uploading: false,
    selectedImages: [],
    maxImages: 5,
    uploadProgressText: ''
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
    const remaining = this.data.maxImages - this.data.selectedImages.length;
    if (remaining <= 0) {
      wx.showToast({ title: `最多选择${this.data.maxImages}张图片`, icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: remaining,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => ({ path: f.tempFilePath }));
        this.setData({
          selectedImages: [...this.data.selectedImages, ...newImages]
        });
      }
    });
  },

  takePhoto() {
    if (!checkLogin()) return;
    if (this.data.selectedImages.length >= this.data.maxImages) {
      wx.showToast({ title: `最多选择${this.data.maxImages}张图片`, icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => ({ path: f.tempFilePath }));
        this.setData({
          selectedImages: [...this.data.selectedImages, ...newImages]
        });
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

  removeImage(e) {
    const idx = e.currentTarget.dataset.index;
    const images = [...this.data.selectedImages];
    images.splice(idx, 1);
    this.setData({ selectedImages: images });
  },

  async startRecognize() {
    if (this.data.selectedImages.length === 0) {
      wx.showToast({ title: '请先选择图片', icon: 'none' });
      return;
    }
    if (this.data.uploading) return;

    const images = this.data.selectedImages;
    const total = images.length;
    this.setData({ uploading: true, uploadProgressText: `正在上传 1/${total} 张...` });

    try {
      let lastRecordId = null;
      let successCount = 0;

      for (let i = 0; i < images.length; i++) {
        this.setData({ uploadProgressText: `正在上传 ${i + 1}/${total} 张...` });
        try {
          const res = await uploadFile('/api/ocr/recognize', images[i].path, 'file', {
            scene_name: '体检报告识别'
          });
          const recordId = res && (res.record_id || res.id);
          if (recordId) {
            lastRecordId = recordId;
            successCount++;
          }
        } catch (uploadErr) {
          console.log('单张上传失败', uploadErr);
        }
      }

      this.setData({ uploading: false, uploadProgressText: '', selectedImages: [] });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
    } catch (e) {
      this.setData({ uploading: false, uploadProgressText: '' });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  async handleUploadFiles(filePaths) {
    if (!filePaths || !filePaths.length) return;
    this.setData({ uploading: true });
    wx.showLoading({ title: '上传中...', mask: true });

    try {
      let lastRecordId = null;
      for (const path of filePaths) {
        try {
          const res = await uploadFile('/api/ocr/recognize', path, 'file', {
            scene_name: '体检报告识别'
          });
          const recordId = res && (res.record_id || res.id);
          if (recordId) lastRecordId = recordId;
        } catch (e) {
          console.log('文件上传失败', e);
        }
      }

      wx.hideLoading();
      this.setData({ uploading: false });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
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
