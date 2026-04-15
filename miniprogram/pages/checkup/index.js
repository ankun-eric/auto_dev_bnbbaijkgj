const { get, uploadFile } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');

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
    uploadProgressText: '',
    uploadPercent: -1,
    compareMode: false,
    selectedIds: []
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
        thumbnail: item.thumbnail || item.image_url || '',
        healthScore: item.health_score || 0,
        scoreColor: this.getScoreColor(item.health_score || 0)
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

  getScoreColor(score) {
    if (score >= 90) return '#1B8C3D';
    if (score >= 75) return '#4CAF50';
    if (score >= 60) return '#FFC107';
    if (score >= 40) return '#FF9800';
    if (score > 0) return '#F44336';
    return '#ccc';
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

    for (let i = 0; i < images.length; i++) {
      const sizeCheck = await checkFileSize(images[i].path, 'checkup_report');
      if (!sizeCheck.ok) {
        wx.showToast({ title: `第${i + 1}张图片超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
        return;
      }
    }

    this.setData({ uploading: true, uploadProgressText: `正在上传 1/${total} 张...`, uploadPercent: 0 });

    try {
      let lastRecordId = null;
      let successCount = 0;

      for (let i = 0; i < images.length; i++) {
        this.setData({ uploadProgressText: `正在上传 ${i + 1}/${total} 张...` });
        try {
          const res = await uploadWithProgress('/api/ocr/recognize', images[i].path, {
            formData: { scene_name: '体检报告识别' },
            onProgress: (percent) => {
              const overallPercent = Math.round(((i + percent / 100) / total) * 100);
              this.setData({ uploadPercent: overallPercent });
            }
          });
          const reportId = res && (res.report_id || res.record_id || res.id);
          if (reportId) {
            lastRecordId = reportId;
            successCount++;
          }
        } catch (uploadErr) {
          console.log('单张上传失败', uploadErr);
        }
      }

      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1, selectedImages: [] });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
    } catch (e) {
      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1 });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  async handleUploadFiles(filePaths) {
    if (!filePaths || !filePaths.length) return;

    for (const path of filePaths) {
      const sizeCheck = await checkFileSize(path, 'checkup_report');
      if (!sizeCheck.ok) {
        wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
        return;
      }
    }

    this.setData({ uploading: true, uploadPercent: 0 });

    try {
      let lastRecordId = null;
      const total = filePaths.length;
      for (let i = 0; i < filePaths.length; i++) {
        try {
          const res = await uploadWithProgress('/api/ocr/recognize', filePaths[i], {
            formData: { scene_name: '体检报告识别' },
            onProgress: (percent) => {
              const overallPercent = Math.round(((i + percent / 100) / total) * 100);
              this.setData({ uploadPercent: overallPercent });
            }
          });
          const reportId = res && (res.report_id || res.record_id || res.id);
          if (reportId) lastRecordId = reportId;
        } catch (e) {
          console.log('文件上传失败', e);
        }
      }

      this.setData({ uploading: false, uploadPercent: -1 });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
    } catch (e) {
      this.setData({ uploading: false, uploadPercent: -1 });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  onItemTap(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.compareMode) {
      this.toggleSelectReport(e);
    } else {
      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${id}` });
    }
  },

  viewReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/checkup-detail/index?id=${id}` });
  },

  toggleCompareMode() {
    this.setData({
      compareMode: !this.data.compareMode,
      selectedIds: []
    });
  },

  toggleSelectReport(e) {
    const id = String(e.currentTarget.dataset.id);
    let selected = [...this.data.selectedIds];
    const idx = selected.indexOf(id);
    if (idx >= 0) {
      selected.splice(idx, 1);
    } else {
      if (selected.length >= 2) {
        wx.showToast({ title: '最多选择2份报告', icon: 'none' });
        return;
      }
      selected.push(id);
    }
    this.setData({ selectedIds: selected });
  },

  goCompare() {
    const { selectedIds } = this.data;
    if (selectedIds.length !== 2) {
      wx.showToast({ title: '请选择2份报告进行对比', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: `/pages/checkup-compare/index?id1=${selectedIds[0]}&id2=${selectedIds[1]}`
    });
  }
});
