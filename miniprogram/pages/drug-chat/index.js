const { get, post, uploadFile } = require('../../utils/request');
const { generateId, checkLogin } = require('../../utils/util');

Page({
  data: {
    sessionId: '',
    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    sending: false
  },

  onLoad(options) {
    const { sessionId } = options;
    if (!sessionId) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
      return;
    }
    this.setData({ sessionId });
    this.loadMessages(sessionId);
  },

  async loadMessages(sessionId) {
    wx.showLoading({ title: '加载中...' });
    try {
      const res = await get(`/api/chat/sessions/${sessionId}/messages`, {}, { showLoading: false });
      const list = Array.isArray(res) ? res : (res.items || res.data || res.messages || []);
      const messages = list.map(msg => {
        const item = {
          id: msg.id || generateId(),
          role: msg.role || (msg.is_ai ? 'assistant' : 'user'),
          content: msg.content || '',
          image: msg.image_url || msg.image || '',
          time: this._formatMsgTime(msg.created_at)
        };
        if (item.role === 'assistant' && item.content && item.content.includes('---disclaimer---')) {
          const parsed = this._parseMessage(item.content);
          item.mainContent = parsed.mainContent;
          item.disclaimer = parsed.disclaimer;
        }
        return item;
      });
      this.setData({ messages });
      this._scrollToBottom();
    } catch (e) {
      console.log('loadMessages error', e);
    } finally {
      wx.hideLoading();
    }
  },

  _formatMsgTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const pad = n => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },

  _parseMessage(content) {
    const parts = content.split('---disclaimer---');
    return {
      mainContent: parts[0].trim(),
      disclaimer: parts.length > 1 ? parts[1].trim() : ''
    };
  },

  _scrollToBottom() {
    setTimeout(() => {
      this.setData({ scrollToId: 'msg-bottom' });
    }, 100);
  },

  _addLocalMessage(role, content, extra = {}) {
    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const msgData = { id, role, content, time, ...extra };
    if (role === 'assistant' && content && content.includes('---disclaimer---')) {
      const parsed = this._parseMessage(content);
      msgData.mainContent = parsed.mainContent;
      msgData.disclaimer = parsed.disclaimer;
    }
    const messages = [...this.data.messages, msgData];
    this.setData({ messages, scrollToId: `msg-${id}` });
    return id;
  },

  _removeMessage(id) {
    const messages = this.data.messages.filter(m => m.id !== id);
    this.setData({ messages });
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content || this.data.sending) return;

    this._addLocalMessage('user', content);
    this.setData({ inputValue: '', sending: true });
    const loadingId = this._addLocalMessage('loading', '');

    try {
      const res = await post(`/api/chat/sessions/${this.data.sessionId}/messages`, {
        content: content
      }, { showLoading: false });

      this._removeMessage(loadingId);
      const reply = res.reply || res.content || res.message || '';
      if (reply) {
        this._addLocalMessage('assistant', reply);
      }
    } catch (e) {
      this._removeMessage(loadingId);
      this._addLocalMessage('assistant', '抱歉，网络出现了问题，请稍后重试。');
    } finally {
      this.setData({ sending: false });
    }
  },

  takePhoto() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this._uploadImage(filePath);
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
        this._uploadImage(filePath);
      }
    });
  },

  async _uploadImage(filePath) {
    this._addLocalMessage('user', '', { image: filePath });
    const loadingId = this._addLocalMessage('loading', '');

    try {
      const res = await uploadFile('/api/ocr/recognize', filePath, 'file', {
        scene_name: '拍照识药'
      });
      const newSessionId = res.session_id || res.id || res.sessionId;
      this._removeMessage(loadingId);

      if (newSessionId && newSessionId !== this.data.sessionId) {
        wx.redirectTo({
          url: '/pages/drug-chat/index?sessionId=' + newSessionId
        });
      } else {
        this.loadMessages(this.data.sessionId);
      }
    } catch (e) {
      this._removeMessage(loadingId);
      this._addLocalMessage('assistant', '图片识别失败，请重试。');
    }
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    wx.previewImage({ current: url, urls: [url] });
  }
});
