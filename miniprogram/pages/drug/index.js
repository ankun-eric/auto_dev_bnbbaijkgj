const { get } = require('../../utils/request');
const { uploadFile } = require('../../utils/request');
const { checkLogin, formatRelativeTime } = require('../../utils/util');

Page({
  data: {
    historyList: [],
    loading: false,
    uploading: false,
    selectedImages: [],
    maxImages: 5,
    uploadProgressText: ''
  },

  onShow() {
    if (!checkLogin()) return;
    this.loadHistory();
  },

  onPullDownRefresh() {
    this.loadHistory().finally(() => wx.stopPullDownRefresh());
  },

  async loadHistory() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/drug-identify/history', {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res.items || res.data || []);
      const historyList = list.map(item => ({
        id: item.id,
        sessionId: item.session_id || item.id,
        drugName: item.drug_name || item.title || '未识别药品',
        thumbnail: item.image_url || item.thumbnail || '',
        time: this._formatTime(item.created_at || item.updated_at),
        status: item.status || 'completed',
        statusText: this._getStatusText(item.status)
      }));
      this.setData({ historyList });
    } catch (e) {
      console.log('loadHistory error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  _formatTime(dateStr) {
    if (!dateStr) return '';
    const ts = new Date(dateStr).getTime();
    if (isNaN(ts)) return '';
    return formatRelativeTime(ts);
  },

  _getStatusText(status) {
    const map = {
      pending: '识别中',
      completed: '已完成',
      failed: '识别失败'
    };
    return map[status] || '已完成';
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

  chooseAlbum() {
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

    let firstSessionId = null;
    try {
      for (let i = 0; i < images.length; i++) {
        this.setData({ uploadProgressText: `正在上传 ${i + 1}/${total} 张...` });
        const res = await uploadFile('/api/ocr/recognize', images[i].path, 'file', {
          scene_name: '拍照识药'
        });
        const sessionId = res && (res.session_id || res.id || res.sessionId);
        if (sessionId && !firstSessionId) {
          firstSessionId = sessionId;
        }
      }

      this.setData({ uploading: false, uploadProgressText: '', selectedImages: [] });

      if (!firstSessionId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }
      wx.navigateTo({
        url: '/pages/drug-chat/index?sessionId=' + firstSessionId
      });
    } catch (e) {
      this.setData({ uploading: false, uploadProgressText: '' });
      wx.showToast({ title: e.detail || '识别失败，请重试', icon: 'none' });
    }
  },

  goChat(e) {
    const sessionId = e.currentTarget.dataset.sessionid;
    if (!sessionId) return;
    wx.navigateTo({
      url: '/pages/drug-chat/index?sessionId=' + sessionId
    });
  }
});
