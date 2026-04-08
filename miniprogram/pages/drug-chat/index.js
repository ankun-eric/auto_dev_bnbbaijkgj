const { get, post, uploadFile } = require('../../utils/request');
const { generateId, checkLogin } = require('../../utils/util');
const app = getApp();

Page({
  data: {
    sessionId: '',
    recordId: '',
    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    sending: false,

    // 结构化药物识别结果
    drugResult: null,
    interactions: [],
    drugs: [],
    expandedDrugs: {},
    activeTab: 'general',   // 'general' | 'personal'
    personalSuggestion: '',
    loadingPersonal: false,
    showDrugPanel: false
  },

  onLoad(options) {
    const { sessionId, session_id, record_id, recordId } = options;
    const sid = sessionId || session_id;
    const rid = recordId || record_id || '';

    if (!sid) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
      return;
    }
    this.setData({ sessionId: sid, recordId: rid });
    this.loadMessages(sid);

    if (rid) {
      this.loadDrugRecord(rid);
    }
  },

  async loadDrugRecord(recordId) {
    try {
      const res = await get(`/api/drug-identify/${recordId}`, {}, { suppressErrorToast: true, showLoading: false });
      const raw = res.data || res;
      const aiResultRaw = raw.ai_result;
      if (!aiResultRaw) return;

      let drugResult = null;
      try {
        drugResult = typeof aiResultRaw === 'string' ? JSON.parse(aiResultRaw) : aiResultRaw;
      } catch (e) {
        return;
      }

      if (!drugResult || !Array.isArray(drugResult.drugs)) return;

      const drugs = drugResult.drugs.map((d, idx) => ({
        ...d,
        _idx: idx
      }));
      const interactions = Array.isArray(drugResult.interactions) ? drugResult.interactions : [];
      const expandedDrugs = {};
      drugs.forEach((d, i) => { expandedDrugs[i] = drugs.length === 1; });

      this.setData({
        drugResult,
        drugs,
        interactions,
        expandedDrugs,
        showDrugPanel: true
      });
    } catch (e) {
      console.log('loadDrugRecord error', e);
    }
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

  toggleDrug(e) {
    const idx = e.currentTarget.dataset.idx;
    const key = `expandedDrugs.${idx}`;
    this.setData({ [key]: !this.data.expandedDrugs[idx] });
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ activeTab: tab });
    if (tab === 'personal' && !this.data.personalSuggestion) {
      this.loadPersonalSuggestion();
    }
  },

  async loadPersonalSuggestion() {
    const { recordId } = this.data;
    if (!recordId) {
      wx.showToast({ title: '无法获取个性化建议', icon: 'none' });
      return;
    }
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    this.setData({ loadingPersonal: true });
    try {
      const res = await get(`/api/drug-identify/${recordId}/personal-suggestion`, {}, { showLoading: false, suppressErrorToast: true });
      const suggestion = res.suggestion || res.content || res.data || '';
      this.setData({ personalSuggestion: suggestion });
    } catch (e) {
      wx.showToast({ title: '获取个性化建议失败', icon: 'none' });
    } finally {
      this.setData({ loadingPersonal: false });
    }
  },

  async shareDrug() {
    const { recordId } = this.data;
    if (!recordId) {
      wx.showToast({ title: '暂无可分享记录', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '生成分享...', mask: true });
    try {
      const res = await post(`/api/drug-identify/${recordId}/share`, {});
      wx.hideLoading();
      const token = res.share_token || res.token || '';
      const shareUrl = res.share_url || res.url || (token ? `${app.globalData.baseUrl}/share/drug/${token}` : '');
      if (shareUrl) {
        wx.setClipboardData({
          data: shareUrl,
          success: () => wx.showToast({ title: '链接已复制', icon: 'success' })
        });
      } else {
        wx.showToast({ title: '分享成功', icon: 'success' });
      }
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '分享失败', icon: 'none' });
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
      const newRecordId = res.record_id || res.recordId || '';
      this._removeMessage(loadingId);

      if (newSessionId && newSessionId !== this.data.sessionId) {
        wx.redirectTo({
          url: `/pages/drug-chat/index?sessionId=${newSessionId}${newRecordId ? '&record_id=' + newRecordId : ''}`
        });
      } else {
        this.loadMessages(this.data.sessionId);
        if (newRecordId) {
          this.setData({ recordId: newRecordId });
          this.loadDrugRecord(newRecordId);
        }
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
