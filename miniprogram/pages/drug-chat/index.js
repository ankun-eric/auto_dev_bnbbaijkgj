// [2026-04-23 v1.2] 用药对话页：融合卡片平铺 + 首条 AI 建议 + 重新生成 + 再加一个药
const { get, post } = require('../../utils/request');
const { generateId, checkLogin } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');
const app = getApp();

const REGENERATE_DEBOUNCE_MS = 10 * 1000;
const MAX_DRUGS = 2;

function truncate(s, n) {
  if (!s) return '';
  return s.length <= n ? s : s.slice(0, n) + '…';
}

Page({
  data: {
    sessionId: '',
    recordId: '',
    memberId: '',

    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    sending: false,

    // v1.2 融合卡片数据
    drugList: [],       // [{ id, name, image_url }]
    drugCount: 0,
    memberInfo: null,   // { nickname, age, gender, ... }
    memberDisplay: '',  // "张三 · 68岁"
    openingMessageId: null,
    regenerating: false,
    lastRegenerateTs: 0,
    canAddMore: true    // drugList.length < 2
  },

  onLoad(options) {
    const { sessionId, session_id, record_id, recordId, member_id } = options;
    const sid = sessionId || session_id;
    const rid = recordId || record_id || '';
    const mid = member_id || '';

    if (!sid) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
      return;
    }
    this.setData({ sessionId: sid, recordId: rid, memberId: mid });

    // 先加载历史消息，再在 300ms 内调 init
    this.loadMessages(sid);
    setTimeout(() => this.initDrugChat(), 300);
  },

  async initDrugChat() {
    const { sessionId, memberId } = this.data;
    if (!sessionId) return;
    try {
      const body = { session_id: Number(sessionId) };
      if (memberId) body.member_id = Number(memberId);
      const res = await post('/api/chat/drug/init', body, { showLoading: false, suppressErrorToast: true });
      if (!res) return;

      const drugList = Array.isArray(res.drug_list) ? res.drug_list.slice(0, MAX_DRUGS) : [];
      const memberInfo = res.member_info || null;
      const opening = res.opening_message || {};

      this.setData({
        drugList,
        drugCount: drugList.length,
        memberInfo,
        memberDisplay: this._formatMember(memberInfo),
        openingMessageId: opening.message_id || null,
        canAddMore: drugList.length < MAX_DRUGS
      });

      if (opening.content_markdown) {
        this._upsertOpeningMessage(opening.message_id, opening.content_markdown, opening.generated_at);
      }
    } catch (e) {
      console.log('initDrugChat error', e);
    }
  },

  _formatMember(info) {
    if (!info) return '';
    const name = info.nickname || '咨询对象';
    const parts = [name];
    if (info.age !== null && info.age !== undefined && info.age !== '') {
      parts.push(`${info.age}岁`);
    }
    return parts.join(' · ');
  },

  async loadMessages(sessionId) {
    wx.showLoading({ title: '加载中...' });
    try {
      const res = await get(`/api/chat/sessions/${sessionId}/messages`, {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res.items || res.data || res.messages || []);
      const messages = list.map(msg => this._buildMessage(msg));
      this.setData({ messages });
      this._scrollToBottom();
    } catch (e) {
      console.log('loadMessages error', e);
    } finally {
      wx.hideLoading();
    }
  },

  _buildMessage(msg) {
    const id = msg.id || generateId();
    const role = msg.role || (msg.is_ai ? 'assistant' : 'user');
    const item = {
      id,
      role,
      content: msg.content || '',
      image: msg.image_url || msg.image || '',
      time: this._formatMsgTime(msg.created_at)
    };
    if (role === 'assistant' && item.content && item.content.indexOf('---disclaimer---') >= 0) {
      const parts = item.content.split('---disclaimer---');
      item.mainContent = parts[0].trim();
      item.disclaimer = parts.length > 1 ? parts[1].trim() : '';
    }
    return item;
  },

  _upsertOpeningMessage(messageId, content, generatedAt) {
    if (!messageId) return;
    const messages = this.data.messages.slice();
    const idx = messages.findIndex(m => String(m.id) === String(messageId));
    const time = this._formatMsgTime(generatedAt) || this._nowTime();
    const newMsg = {
      id: messageId,
      role: 'assistant',
      content,
      mainContent: content,
      isOpening: true,
      time
    };
    if (idx >= 0) {
      messages[idx] = { ...messages[idx], ...newMsg };
    } else {
      // 首条：放在最前
      messages.unshift(newMsg);
    }
    this.setData({ messages, openingMessageId: messageId });
    this._scrollToBottom();
  },

  _formatMsgTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const pad = n => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },

  _nowTime() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },

  _scrollToBottom() {
    setTimeout(() => { this.setData({ scrollToId: 'msg-bottom' }); }, 100);
  },

  _addLocalMessage(role, content, extra = {}) {
    const id = generateId();
    const msgData = { id, role, content, time: this._nowTime(), ...extra };
    if (role === 'assistant' && content && content.indexOf('---disclaimer---') >= 0) {
      const parts = content.split('---disclaimer---');
      msgData.mainContent = parts[0].trim();
      msgData.disclaimer = parts.length > 1 ? parts[1].trim() : '';
    }
    const messages = [...this.data.messages, msgData];
    this.setData({ messages, scrollToId: `msg-${id}` });
    return id;
  },

  _removeMessage(id) {
    const messages = this.data.messages.filter(m => m.id !== id);
    this.setData({ messages });
  },

  // ─────── 融合卡片交互 ───────

  previewDrugImage(e) {
    const idx = Number(e.currentTarget.dataset.idx || 0);
    const urls = this.data.drugList.map(d => d.image_url).filter(Boolean);
    if (!urls.length) return;
    const current = urls[idx] || urls[0];
    wx.previewImage({ current, urls });
  },

  onDrugNameTap(e) {
    const name = e.currentTarget.dataset.name || '';
    if (name) {
      wx.showToast({ title: name, icon: 'none', duration: 2500 });
    }
  },

  // ─────── 重新生成首条建议 ───────

  async regenerateOpening() {
    const now = Date.now();
    if (now - this.data.lastRegenerateTs < REGENERATE_DEBOUNCE_MS) {
      wx.showToast({ title: '请稍候…', icon: 'none' });
      return;
    }
    if (this.data.regenerating) return;
    this.setData({ regenerating: true, lastRegenerateTs: now });
    wx.showLoading({ title: '重新生成中...', mask: true });
    try {
      const res = await post('/api/chat/drug/regenerate_opening', {
        session_id: Number(this.data.sessionId)
      }, { showLoading: false, suppressErrorToast: true });
      if (res && res.content_markdown) {
        this._upsertOpeningMessage(res.message_id, res.content_markdown, res.generated_at);
        wx.showToast({ title: '已重新生成', icon: 'success' });
      } else {
        wx.showToast({ title: '生成失败，请重试', icon: 'none' });
      }
    } catch (e) {
      const detail = (e && e.detail) || '生成失败';
      wx.showToast({ title: String(detail).slice(0, 40), icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ regenerating: false });
    }
  },

  // ─────── 再加一个药 ───────

  addMoreDrug() {
    if (this.data.drugList.length >= MAX_DRUGS) {
      wx.showToast({ title: '最多对比 2 个药品', icon: 'none' });
      return;
    }
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this._uploadAddDrug(filePath);
      }
    });
  },

  async _uploadAddDrug(filePath) {
    const sizeCheck = await checkFileSize(filePath, 'drug_identify');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }
    wx.showLoading({ title: '上传识别中...', mask: true });
    try {
      const formData = { scene_name: '拍照识药', session_id: String(this.data.sessionId) };
      if (this.data.memberId) formData.family_member_id = String(this.data.memberId);
      const res = await uploadWithProgress('/api/ocr/recognize', filePath, { formData });
      wx.hideLoading();
      if (res && res.single_select_notice) {
        wx.showToast({ title: '已自动选取第一张', icon: 'none' });
      }
      // 重新拉 init 刷新 drug_list + opening
      this.initDrugChat();
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '识别失败，请重试', icon: 'none' });
    }
  },

  // ─────── 输入 + 发送 ───────

  onInput(e) { this.setData({ inputValue: e.detail.value }); },

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
        this._uploadChatImage(filePath);
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
        this._uploadChatImage(filePath);
      }
    });
  },

  async _uploadChatImage(filePath) {
    const sizeCheck = await checkFileSize(filePath, 'drug_identify');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    this._addLocalMessage('user', '', { image: filePath });
    const loadingId = this._addLocalMessage('loading', '');

    try {
      const formData = { scene_name: '拍照识药', session_id: String(this.data.sessionId) };
      if (this.data.memberId) formData.family_member_id = String(this.data.memberId);
      const res = await uploadWithProgress('/api/ocr/recognize', filePath, { formData });
      this._removeMessage(loadingId);
      if (res && res.single_select_notice) {
        wx.showToast({ title: '已自动选取第一张', icon: 'none' });
      }
      // 刷新融合卡片与首条建议
      this.initDrugChat();
      this.loadMessages(this.data.sessionId);
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
