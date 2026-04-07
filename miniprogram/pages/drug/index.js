const { get } = require('../../utils/request');
const { uploadFile } = require('../../utils/request');
const { checkLogin, formatRelativeTime } = require('../../utils/util');

Page({
  data: {
    historyList: [],
    loading: false,
    uploading: false
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
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this._uploadAndRecognize(filePath);
      }
    });
  },

  chooseAlbum() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this._uploadAndRecognize(filePath);
      }
    });
  },

  async _uploadAndRecognize(filePath) {
    this.setData({ uploading: true });
    try {
      const res = await uploadFile('/api/ocr/recognize', filePath, 'file', {
        scene_name: '拍照识药'
      });
      const sessionId = res.session_id || res.id || res.sessionId;
      if (!sessionId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }
      wx.navigateTo({
        url: '/pages/drug-chat/index?sessionId=' + sessionId
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '识别失败，请重试', icon: 'none' });
    } finally {
      this.setData({ uploading: false });
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
