const { post, get, put, del, uploadFile } = require('../../utils/request');
const { generateId } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');
const { compressImage } = require('../../utils/image-compress');

const RELATION_COLORS = {
  '本人': '#52c41a',
  '爸爸': '#1890ff', '妈妈': '#1890ff',
  '儿子': '#eb2f96', '女儿': '#eb2f96',
  '爷爷': '#fa8c16', '奶奶': '#fa8c16',
  '外公': '#fa8c16', '外婆': '#fa8c16'
};
function getRelationColor(name) {
  return RELATION_COLORS[name] || '#8c8c8c';
}

const plugin = requirePlugin('WechatSI');

const FONT_SIZE_OPTIONS = [
  { level: 'standard', label: '标准', size: '28rpx' },
  { level: 'large', label: '大', size: '36rpx' },
  { level: 'extra_large', label: '超大', size: '44rpx' }
];

Page({
  data: {
    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    chatId: '',
    chatType: 'general',
    drawerShow: false,
    allSessions: [],
    showFontPopover: false,
    fontSizeLevel: 'standard',
    fontSizeOptions: FONT_SIZE_OPTIONS,
    msgFontSize: '28rpx',
    voiceMode: false,
    isRecording: false,
    showRecordOverlay: false,
    recordCancelling: false,
    recordingTime: 0,
    consultTarget: { name: '本人', color: '#52c41a' },
    showTargetPicker: false,
    familyMembers: [],
    functionButtons: [],
    isSymptomLocked: false,
    uploadPercent: -1,
    showUploadProgress: false,

    // Module 5: Drug recognize quick button
    showDrugCard: false,
    drugCardData: null,
    drugCardExpanded: false,
    drugImageUploading: false,
    drugIdentifyDisabled: false,

    // Type-lock & summary bar
    isTypeLocked: false,
    summaryBarText: '',
    lockedFamilyMemberId: null,

    // Drug identify card (顶部卡片，与 H5/Flutter 对齐)
    drugIdentifyMember: '',
    drugIdentifyDrugNames: '',
    drugIdentifyBannerVisible: false,

    // Module 6: SSE streaming
    streamingMsgId: '',
    streamingText: '',
    showCursor: false,
    isStreaming: false,

    // Module 7: Action buttons on latest AI reply
    latestAiMsgId: '',

    // Module 8: TTS
    isTtsPlaying: false,
    ttsMsgId: '',

    // [2026-04-23 报告分支] 报告解读/对比场景的顶部报告卡片
    reportList: [],

    // [2026-04-25] 报告解读异步化：失败状态
    interpretFailed: false,
    interpretPending: false,

    // [2026-04-25 PRD F5] OCR 详情默认隐藏 + 兜底入口
    firstAiMsgId: '',
    ocrDetailExpanded: false,
    ocrDetailLoaded: false,
    ocrDetailLoading: false,
    ocrDetailText: ''
  },

  _recognizeManager: null,
  _recordTimer: null,
  _touchStartY: 0,
  _touchStartTime: 0,
  _discardNextResult: false,
  _btnCacheExpire: 0,
  _audioContext: null,
  _cursorTimer: null,
  _sseRequestTask: null,

  onLoad(options) {
    // [2026-04-23 报告分支] 新增 report_id / report_ids / auto_start 参数
    const { type = 'health_qa', chatId, question, member, family_member_id, constitution_type, summary, drug_name,
            report_id, report_ids, auto_start } = options;
    this.setData({ chatType: type, chatId: chatId || generateId() });

    const isSymptom = type === 'symptom' || type === 'symptom_check';
    if (isSymptom) {
      const relation = member ? decodeURIComponent(member).split('·')[0].trim() : '本人';
      this.setData({
        isSymptomLocked: true,
        consultTarget: { name: relation || '本人', color: getRelationColor(relation || '本人') }
      });
    }

    if (type === 'drug_identify' || type === 'constitution') {
      this.setData({ isTypeLocked: true });
      if (family_member_id) {
        this.setData({ lockedFamilyMemberId: family_member_id });
      }
      if (summary) {
        this.setData({ summaryBarText: decodeURIComponent(summary) });
      }
    }

    if (type === 'drug_identify') {
      const memberLabel = member ? decodeURIComponent(member) : '';
      const drugNamesStr = drug_name ? decodeURIComponent(drug_name) : '';
      this.setData({
        drugIdentifyMember: memberLabel,
        drugIdentifyDrugNames: drugNamesStr,
        drugIdentifyBannerVisible: !!(memberLabel || drugNamesStr)
      });
    }

    // [2026-04-23 报告分支] 报告解读/对比：锁定类型，加载报告卡片数据
    if (type === 'report_interpret' || type === 'report_compare') {
      this.setData({ isTypeLocked: true, chatType: type });
      // [Bug-04] URL 带 family_member_id 时立即把咨询人锁定为报告所属人
      if (family_member_id) {
        this._lockConsultTargetByMemberId(family_member_id);
      }
      this._loadReportsBrief({ chatId, reportId: report_id, reportIds: report_ids });
      if (auto_start === '1' && chatId) {
        // [2026-04-25] 报告解读异步订阅：进入页面即订阅后端 worker 推流
        this._pendingAutoStart = true;
        setTimeout(() => this._startReportInterpretSse(chatId), 300);
      }
    }

    wx.showShareMenu({ withShareTicket: true, menus: ['shareAppMessage', 'shareTimeline'] });

    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考',
      drug_identify: '用药识别',
      constitution: '体质调理',
      // [2026-04-23 报告分支]
      report_interpret: 'AI 报告解读',
      report_compare: '报告对比'
    };
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI健康咨询' });

    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);

    this.loadFontSetting();
    this.loadFamilyMembers();
    this.loadFunctionButtons();

    if (type === 'drug_identify' || type === 'constitution') {
      this._lockConsultTargetByMemberId(family_member_id);
    }

    if (question) {
      setTimeout(() => {
        this.setData({ inputValue: decodeURIComponent(question) });
        this.sendMessage();
      }, 500);
    }

    if (chatId) {
      this.loadChatHistory(chatId);
    }

    if (chatId && !isSymptom) {
      this.restoreSessionMember(chatId);
    }
  },

  onUnload() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this._recognizeManager = null;
    this._stopTts();
    if (this._cursorTimer) {
      clearInterval(this._cursorTimer);
      this._cursorTimer = null;
    }
    if (this._sseRequestTask) {
      this._sseRequestTask.abort();
      this._sseRequestTask = null;
    }
  },

  // ========================
  // Module 9: Share
  // ========================
  onShareAppMessage() {
    const chatId = this.data.chatId;
    return {
      title: '宾尼小康AI健康咨询',
      path: `/pages/chat/index?chatId=${chatId}&type=${this.data.chatType}`
    };
  },

  async shareToFriend() {
    const msgId = this.data.latestAiMsgId;
    if (!msgId) {
      wx.showToast({ title: '暂无可分享的AI回复', icon: 'none' });
      return;
    }
    try {
      const res = await post('/api/chat/share', {
        session_id: this.data.chatId,
        message_id: msgId
      }, { showLoading: true, suppressErrorToast: false });

      const shareUrl = res.share_url || res.url || '';
      if (shareUrl) {
        wx.setClipboardData({
          data: shareUrl,
          success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
        });
      } else {
        wx.showToast({ title: '分享成功', icon: 'success' });
      }
    } catch (e) {
      wx.showToast({ title: '生成分享链接失败', icon: 'none' });
    }
  },

  async generateShareImage() {
    wx.showLoading({ title: '生成图片中...', mask: true });
    try {
      const query = wx.createSelectorQuery();
      query.select('#share-canvas').fields({ node: true, size: true }).exec((res) => {
        if (!res || !res[0]) {
          wx.hideLoading();
          wx.showToast({ title: '生成失败', icon: 'none' });
          return;
        }
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const width = 600;
        const height = 800;
        canvas.width = width;
        canvas.height = height;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        ctx.fillStyle = '#52c41a';
        ctx.fillRect(0, 0, width, 80);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 32px sans-serif';
        ctx.fillText('宾尼小康 AI健康咨询', 30, 52);

        ctx.fillStyle = '#333333';
        ctx.font = '24px sans-serif';
        const msgs = this.data.messages.filter(m => m.role !== 'loading').slice(-5);
        let y = 120;
        msgs.forEach(msg => {
          const prefix = msg.role === 'user' ? '我: ' : 'AI: ';
          const text = prefix + (msg.content || '').substring(0, 80);
          ctx.fillText(text, 30, y);
          y += 40;
        });

        ctx.fillStyle = '#999999';
        ctx.font = '20px sans-serif';
        ctx.fillText('长按识别小程序码查看完整对话', 30, height - 40);

        wx.canvasToTempFilePath({
          canvas,
          success: (imgRes) => {
            wx.hideLoading();
            wx.previewImage({ urls: [imgRes.tempFilePath] });
          },
          fail: () => {
            wx.hideLoading();
            wx.showToast({ title: '生成失败', icon: 'none' });
          }
        });
      });
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '生成失败', icon: 'none' });
    }
  },

  // ========================
  // Module 7: Copy / TTS / Share buttons
  // ========================
  copyMessage(e) {
    const msgId = e.currentTarget.dataset.msgid;
    const msg = this.data.messages.find(m => m.id === msgId);
    if (!msg) return;
    const text = msg.mainContent || msg.content || '';
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' })
    });
  },

  // ========================
  // Module 8: TTS
  // ========================
  toggleTts(e) {
    const msgId = e.currentTarget.dataset.msgid;
    if (this.data.isTtsPlaying && this.data.ttsMsgId === msgId) {
      this._stopTts();
      return;
    }
    const msg = this.data.messages.find(m => m.id === msgId);
    if (!msg) return;
    const text = msg.mainContent || msg.content || '';
    this._playTts(text, msgId);
  },

  async _playTts(text, msgId) {
    this._stopTts();

    if (!this._audioContext) {
      this._audioContext = wx.createInnerAudioContext();
      this._audioContext.onEnded(() => {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
      });
      this._audioContext.onError(() => {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
        wx.showToast({ title: '播报失败', icon: 'none' });
      });
    }

    this.setData({ isTtsPlaying: true, ttsMsgId: msgId });

    try {
      const res = await post('/api/tts/synthesize', {
        text: text.substring(0, 500)
      }, { showLoading: false, suppressErrorToast: true });
      const audioUrl = res && res.audio_url;
      if (!audioUrl) {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
        wx.showToast({ title: '语音合成失败', icon: 'none' });
        return;
      }
      const app = getApp();
      this._audioContext.src = `${app.globalData.baseUrl}${audioUrl}`;
      this._audioContext.play();
    } catch (e) {
      this.setData({ isTtsPlaying: false, ttsMsgId: '' });
      wx.showToast({ title: '播报失败', icon: 'none' });
    }
  },

  _stopTts() {
    if (this._audioContext) {
      this._audioContext.stop();
    }
    this.setData({ isTtsPlaying: false, ttsMsgId: '' });
  },

  // ========================
  // Module 5: Drug recognize quick button
  // ========================
  onDrugRecognizeTap() {
    if (this.data.drugIdentifyDisabled) {
      wx.showToast({ title: '正在识别中，请稍候', icon: 'none' });
      return;
    }
    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        const sourceType = res.tapIndex === 0 ? ['camera'] : ['album'];
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType,
          success: (mediaRes) => {
            const filePath = mediaRes.tempFiles[0].tempFilePath;
            this._uploadDrugImage(filePath);
          }
        });
      }
    });
  },

  async _uploadDrugImage(filePath) {
    try {
      filePath = await compressImage(filePath);
    } catch (_) { /* 压缩失败回退原图 */ }
    const sizeCheck = await checkFileSize(filePath, 'drug_identify');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: '', image: filePath, time }];
    this.setData({ messages, scrollToId: `msg-${id}`, drugImageUploading: true });

    const loadingId = this.addMessage('loading', '');

    try {
      const res = await uploadWithProgress('/api/ocr/recognize', filePath, {
        formData: { scene_name: '拍照识药' },
        onProgress: (percent) => this.setData({ uploadPercent: percent, showUploadProgress: true })
      });

      this.setData({ showUploadProgress: false, uploadPercent: -1, drugImageUploading: false });
      this.removeMessage(loadingId);

      const drugData = res.drugs || res.drug_info || null;
      if (drugData) {
        this.setData({ showDrugCard: true, drugCardData: drugData, drugCardExpanded: false });
      }

      const reply = (res && res.ai_reply) || (res && res.content) || '已收到药品图片，正在识别中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1, drugImageUploading: false });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '药品识别失败，请重试。');
    }
  },

  toggleDrugCard() {
    this.setData({ drugCardExpanded: !this.data.drugCardExpanded });
  },

  // ========================
  // Module 6: SSE Streaming
  // ========================
  _startSseStream(sessionId, content) {
    const app = getApp();
    const url = `${app.globalData.baseUrl}/api/chat/sessions/${sessionId}/stream`;
    const token = app.globalData.token;

    const msgId = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    const messages = [...this.data.messages, { id: msgId, role: 'assistant', content: '', time, isStreaming: true }];
    this.setData({
      messages,
      scrollToId: `msg-${msgId}`,
      streamingMsgId: msgId,
      streamingText: '',
      isStreaming: true,
      showCursor: true,
      latestAiMsgId: ''
    });

    this._startCursorBlink();

    let fullText = '';

    this._sseRequestTask = wx.request({
      url,
      method: 'POST',
      data: { content, session_type: this.data.chatType },
      header: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      enableChunked: true,
      responseType: 'text',
      success: () => {},
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('abort') >= 0) return;
        this._finishStreaming(msgId, fullText || '抱歉，网络出现了问题，请稍后重试。');
      }
    });

    if (this._sseRequestTask) {
      this._sseRequestTask.onChunkReceived((resp) => {
        try {
          const text = this._decodeChunk(resp.data);
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data:')) {
              const dataStr = line.substring(5).trim();
              if (dataStr === '[DONE]') {
                this._finishStreaming(msgId, fullText);
                return;
              }
              try {
                const parsed = JSON.parse(dataStr);
                const delta = parsed.delta || parsed.content || parsed.text || '';
                if (delta) {
                  fullText += delta;
                  this._updateStreamingMessage(msgId, fullText);
                }
              } catch (pe) {
                fullText += dataStr;
                this._updateStreamingMessage(msgId, fullText);
              }
            }
          }
        } catch (e) {
          console.log('SSE chunk parse error', e);
        }
      });
    }
  },

  _decodeChunk(arrayBuffer) {
    if (typeof arrayBuffer === 'string') return arrayBuffer;
    try {
      const uint8 = new Uint8Array(arrayBuffer);
      let str = '';
      for (let i = 0; i < uint8.length; i++) {
        str += String.fromCharCode(uint8[i]);
      }
      return decodeURIComponent(escape(str));
    } catch (e) {
      return '';
    }
  },

  _updateStreamingMessage(msgId, text) {
    const idx = this.data.messages.findIndex(m => m.id === msgId);
    if (idx < 0) return;
    this.setData({
      [`messages[${idx}].content`]: text,
      streamingText: text,
      scrollToId: `msg-${msgId}`
    });
  },

  _finishStreaming(msgId, text) {
    if (this._cursorTimer) {
      clearInterval(this._cursorTimer);
      this._cursorTimer = null;
    }

    const idx = this.data.messages.findIndex(m => m.id === msgId);
    if (idx >= 0) {
      let parsed = {};
      if (text && text.includes('---disclaimer---')) {
        const parts = text.split('---disclaimer---');
        parsed.mainContent = parts[0].trim();
        parsed.disclaimer = parts[1] ? parts[1].trim() : '';
      }
      this.setData({
        [`messages[${idx}].content`]: text,
        [`messages[${idx}].isStreaming`]: false,
        [`messages[${idx}].mainContent`]: parsed.mainContent || '',
        [`messages[${idx}].disclaimer`]: parsed.disclaimer || '',
        streamingMsgId: '',
        streamingText: '',
        isStreaming: false,
        showCursor: false,
        latestAiMsgId: msgId
      });
    }

    this._sseRequestTask = null;
  },

  _startCursorBlink() {
    if (this._cursorTimer) clearInterval(this._cursorTimer);
    this._cursorTimer = setInterval(() => {
      this.setData({ showCursor: !this.data.showCursor });
    }, 500);
  },

  // ========================
  // Font settings
  // ========================
  async loadFontSetting() {
    try {
      const res = await get('/api/user/font-setting', {}, { showLoading: false, suppressErrorToast: true });
      const level = res && res.font_size_level ? res.font_size_level : 'standard';
      this.applyFontLevel(level);
    } catch (e) {
      this.applyFontLevel('standard');
    }
  },

  applyFontLevel(level) {
    const sizeMap = { standard: '28rpx', large: '36rpx', extra_large: '44rpx' };
    this.setData({
      fontSizeLevel: level,
      msgFontSize: sizeMap[level] || '28rpx'
    });
  },

  toggleFontPopover() {
    this.setData({ showFontPopover: !this.data.showFontPopover });
  },

  closeFontPopover() {
    this.setData({ showFontPopover: false });
  },

  async onFontOptionTap(e) {
    const level = e.currentTarget.dataset.level;
    if (level === this.data.fontSizeLevel) {
      this.setData({ showFontPopover: false });
      return;
    }
    this.applyFontLevel(level);
    this.setData({ showFontPopover: false });

    const labelMap = { standard: '标准', large: '大', extra_large: '超大' };
    wx.showToast({ title: `已切换为${labelMap[level]}字体`, icon: 'success' });

    try {
      await put('/api/user/font-setting', { font_size_level: level }, { showLoading: false, suppressErrorToast: true });
    } catch (e) {
      console.log('save font setting error', e);
    }
  },

  // ========================
  // Chat history & sessions
  // ========================
  async loadChatHistory(chatId) {
    try {
      // const res = await get(`/api/chat/${chatId}/messages`);
      // this.setData({ messages: res.data });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
  },

  async loadSessions() {
    try {
      const res = await get('/api/chat-sessions', { page: 1, page_size: 100 }, { showLoading: false, suppressErrorToast: true });
      const sessions = Array.isArray(res) ? res : (res.items || res.data || []);
      this.setData({ allSessions: sessions });
    } catch (e) {
      console.log('loadSessions error', e);
    }
  },

  openDrawer() {
    this.loadSessions();
    this.setData({ drawerShow: true });
  },

  onDrawerClose() {
    this.setData({ drawerShow: false });
  },

  onSessionTap(e) {
    const { session } = e.detail;
    this.setData({ drawerShow: false });

    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考'
    };
    const type = session.session_type || 'health_qa';
    this.setData({
      chatId: session.id,
      chatType: type,
      messages: [],
      latestAiMsgId: ''
    });
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI健康咨询' });
    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);
    this.loadChatHistory(session.id);
  },

  onDrawerNewChat() {
    this.setData({ drawerShow: false });
    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考'
    };
    const type = 'health_qa';
    this.setData({
      chatId: generateId(),
      chatType: type,
      messages: [],
      latestAiMsgId: ''
    });
    wx.setNavigationBarTitle({ title: typeNames[type] });
    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type]}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);
  },

  onDrawerRefresh() {
    this.loadSessions();
  },

  onDrawerShare(e) {
    const { session, shareToken, shareUrl } = e.detail;
    wx.setClipboardData({
      data: shareUrl || shareToken,
      success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
    });
  },

  // ========================
  // Family members
  // ========================
  async loadFamilyMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      const members = items.map(m => ({
        id: m.id,
        name: m.relation_type_name || m.nickname || '本人',
        color: getRelationColor(m.relation_type_name || ''),
        is_self: m.is_self
      }));
      if (!members.some(m => m.is_self)) {
        members.unshift({ id: 0, name: '本人', color: '#52c41a', is_self: true });
      }
      this.setData({ familyMembers: members });
    } catch (e) {
      console.log('loadFamilyMembers error', e);
    }
  },

  async loadFunctionButtons() {
    const now = Date.now();
    if (this._btnCacheExpire > now && this.data.functionButtons.length) return;
    try {
      const res = await get('/api/chat/function-buttons', {}, { showLoading: false, suppressErrorToast: true });
      const buttons = Array.isArray(res) ? res : (res.items || res.data || []);
      this.setData({ functionButtons: buttons.filter(b => b.is_enabled) });
      this._btnCacheExpire = now + 5 * 60 * 1000;
    } catch (e) {
      console.log('loadFunctionButtons error', e);
    }
  },

  onFunctionButtonTap(e) {
    const btn = e.currentTarget.dataset.button;
    if (!btn) return;
    const params = btn.params || {};

    switch (btn.button_type) {
      case 'digital_human_call':
        wx.navigateTo({
          url: `/pages/digital-human-call/index?digitalHumanId=${params.digital_human_id || ''}&sessionId=${this.data.chatId}`
        });
        break;

      case 'photo_upload':
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: ['album', 'camera'],
          success: (res) => {
            const filePath = res.tempFiles[0].tempFilePath;
            this._uploadAndSendImage(filePath);
          }
        });
        break;

      case 'file_upload':
        wx.chooseMessageFile({
          count: 1,
          type: 'file',
          success: (res) => {
            const filePath = res.tempFiles[0].path;
            const fileName = res.tempFiles[0].name;
            this._uploadAndSendFile(filePath, fileName);
          }
        });
        break;

      case 'ai_dialog_trigger': {
        const triggerMsg = params.message || btn.name;
        this.setData({ inputValue: triggerMsg });
        this.sendMessage();
        break;
      }

      case 'drug_identify':
        this._handleDrugIdentifyButton(btn);
        break;

      case 'external_link':
        if (params.url) {
          if (params.url.startsWith('/pages/')) {
            wx.navigateTo({ url: params.url });
          } else {
            wx.navigateTo({ url: `/pages/webview/index?url=${encodeURIComponent(params.url)}` });
          }
        }
        break;

      default:
        wx.showToast({ title: '暂不支持该功能', icon: 'none' });
    }
  },

  _handleDrugIdentifyButton(btn) {
    if (this.data.drugIdentifyDisabled) {
      wx.showToast({ title: '正在识别中，请稍候', icon: 'none' });
      return;
    }
    const params = btn.params || {};
    const tipText = params.photo_tip_text || '请拍摄药品包装、说明书等清晰照片';
    const maxCount = params.max_photo_count || 5;

    wx.showModal({
      title: '拍照识药',
      content: tipText,
      showCancel: false,
      confirmText: '我知道了',
      success: () => {
        wx.showActionSheet({
          itemList: ['拍照', '从相册选择'],
          success: (res) => {
            if (res.tapIndex === 0) {
              wx.chooseMedia({
                count: 1,
                mediaType: ['image'],
                sourceType: ['camera'],
                success: (mediaRes) => {
                  this._processDrugIdentifyImages(mediaRes.tempFiles.map(f => f.tempFilePath));
                }
              });
            } else {
              wx.chooseMedia({
                count: maxCount,
                mediaType: ['image'],
                sourceType: ['album'],
                success: (mediaRes) => {
                  this._processDrugIdentifyImages(mediaRes.tempFiles.map(f => f.tempFilePath));
                }
              });
            }
          }
        });
      }
    });
  },

  async _processDrugIdentifyImages(filePaths) {
    if (!filePaths || !filePaths.length) return;
    this.setData({ drugIdentifyDisabled: true });

    const compressed = [];
    for (const p of filePaths) {
      try {
        compressed.push(await compressImage(p));
      } catch (_) {
        compressed.push(p);
      }
    }
    filePaths = compressed;

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: `[拍照识药] 共${filePaths.length}张`, image: filePaths[0], time }];
    this.setData({ messages, scrollToId: `msg-${id}` });

    const loadingId = this.addMessage('loading', '');
    let allOcrText = '';

    try {
      for (let i = 0; i < filePaths.length; i++) {
        const sizeCheck = await checkFileSize(filePaths[i], 'drug_identify');
        if (!sizeCheck.ok) {
          wx.showToast({ title: `第${i + 1}张图片超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
          continue;
        }
        const ocrRes = await uploadWithProgress('/api/ocr/recognize', filePaths[i], {
          formData: { scene_name: '拍照识药' },
          onProgress: (percent) => {
            const overall = Math.round(((i + percent / 100) / filePaths.length) * 100);
            this.setData({ uploadPercent: overall, showUploadProgress: true });
          }
        });
        const text = (ocrRes && (ocrRes.text || ocrRes.ocr_text || ocrRes.content)) || '';
        if (text) allOcrText += (allOcrText ? '\n' : '') + text;
      }
      this.setData({ showUploadProgress: false, uploadPercent: -1 });

      if (!allOcrText) {
        this.removeMessage(loadingId);
        this.addMessage('assistant', '未能识别到药品文字信息，请拍摄更清晰的照片重试。');
        this.setData({ drugIdentifyDisabled: false });
        return;
      }

      this.removeMessage(loadingId);

      const analyzeLoadingId = this.addMessage('loading', '');
      const analyzeRes = await post('/api/drug-identify/analyze', {
        ocr_text: allOcrText,
        session_id: this.data.chatId,
        family_member_id: this.data.lockedFamilyMemberId || undefined
      }, { showLoading: false, suppressErrorToast: true });

      this.removeMessage(analyzeLoadingId);

      const drugData = analyzeRes && (analyzeRes.drugs || analyzeRes.drug_info);
      if (drugData) {
        this.setData({ showDrugCard: true, drugCardData: drugData, drugCardExpanded: false });
      }

      const reply = (analyzeRes && (analyzeRes.ai_reply || analyzeRes.content)) || '药品信息已识别，请查看上方药品卡片。';
      this.addMessage('assistant', reply);

      if (analyzeRes && analyzeRes.follow_up_question) {
        setTimeout(() => {
          this.setData({ inputValue: analyzeRes.follow_up_question });
          this.sendMessage();
        }, 1000);
      }
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '药品识别失败，请重试。');
    } finally {
      this.setData({ drugIdentifyDisabled: false });
    }
  },

  // [2026-04-25] 报告解读异步订阅：进入 report_interpret/report_compare 页面时调用
  _startReportInterpretSse(sessionId) {
    const app = getApp();
    const baseUrl = app.globalData.baseUrl;
    const token = app.globalData.token;
    const url = `${baseUrl}/api/report/interpret/session/${sessionId}/stream?auto_start=1`;

    this.setData({ interpretPending: true, interpretFailed: false });

    const msgId = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id: msgId, role: 'assistant', content: '', time, isStreaming: true }];
    this.setData({
      messages,
      scrollToId: `msg-${msgId}`,
      streamingMsgId: msgId,
      streamingText: '',
      isStreaming: true,
      showCursor: true,
      // [2026-04-25 PRD F5] 记录第一条 AI 解读消息 id，用于在该条消息底部挂载 OCR 详情入口
      firstAiMsgId: this.data.firstAiMsgId || msgId,
      // 重置 OCR 详情状态（新解读未完成前不展示入口）
      ocrDetailExpanded: false,
      ocrDetailLoaded: false,
      ocrDetailLoading: false,
      ocrDetailText: ''
    });
    this._startCursorBlink();

    let fullText = '';
    let currentEvent = '';
    let leftover = '';

    const task = wx.request({
      url,
      method: 'GET',
      header: {
        'Accept': 'text/event-stream',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      enableChunked: true,
      responseType: 'text',
      success: () => {},
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('abort') >= 0) return;
        this._finishStreaming(msgId, fullText || '网络异常，请稍后重试');
        this.setData({ interpretPending: false });
      }
    });

    this._sseRequestTask = task;

    if (task) {
      task.onChunkReceived((resp) => {
        try {
          const text = leftover + this._decodeChunk(resp.data);
          const lines = text.split('\n');
          leftover = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
              continue;
            }
            if (!line.startsWith('data:')) continue;
            const dataStr = line.startsWith('data: ') ? line.slice(6) : line.slice(5).trim();
            let data = {};
            try { data = JSON.parse(dataStr); } catch { data = { raw: dataStr }; }

            if (currentEvent === 'message.delta' || data.type === 'delta') {
              const d = data.delta || data.content || '';
              if (d) {
                fullText += d;
                this._updateStreamingMessage(msgId, fullText);
              }
            } else if (currentEvent === 'message.done' || data.type === 'done') {
              const final = data.content || fullText;
              fullText = final;
              this._updateStreamingMessage(msgId, fullText);
            } else if (currentEvent === 'status') {
              if (data.interpret_status === 'failed') {
                this.setData({ interpretFailed: true, interpretPending: false });
              } else if (data.interpret_status === 'done') {
                this.setData({ interpretFailed: false, interpretPending: false });
              }
            } else if (currentEvent === 'error' || data.type === 'error') {
              this.setData({ interpretFailed: true, interpretPending: false });
            } else if (currentEvent === 'done') {
              this._finishStreaming(msgId, fullText);
              this.setData({ interpretPending: false });
            }
            currentEvent = '';
          }
        } catch (e) {
          console.log('[report SSE] parse error', e);
        }
      });
    }
  },

  // [2026-04-25 PRD F5-3] 切换 OCR 详情展开/收起
  async onToggleOcrDetail() {
    const sid = this.data.chatId;
    if (!sid) return;
    const next = !this.data.ocrDetailExpanded;
    this.setData({ ocrDetailExpanded: next });
    // [F5-7] 埋点（不阻塞）
    try {
      post('/api/report/interpret/ocr-detail/click', {
        session_id: Number(sid),
        action: next ? 'view' : 'collapse'
      }, { showLoading: false, suppressErrorToast: true });
    } catch (_) { /* ignore */ }
    if (!next) return;
    if (this.data.ocrDetailLoaded || this.data.ocrDetailLoading) return;
    this.setData({ ocrDetailLoading: true });
    try {
      const res = await get(`/api/report/interpret/session/${sid}/ocr-detail`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({
        ocrDetailText: String(data.ocr_text || ''),
        ocrDetailLoaded: true
      });
    } catch (_) {
      this.setData({ ocrDetailText: '' });
    } finally {
      this.setData({ ocrDetailLoading: false });
    }
  },

  // [2026-04-25] 用户点"重新解读"按钮
  async onRetryInterpret() {
    const sid = this.data.chatId;
    if (!sid) return;
    try {
      await post(`/api/report/interpret/session/${sid}/retry`, {}, { showLoading: true });
      // 清理失败状态 + 重新订阅
      this.setData({ interpretFailed: false, messages: this.data.messages.filter(m => !m.isStreaming) });
      this._startReportInterpretSse(sid);
    } catch (e) {
      wx.showToast({ title: e.message || '重试失败，请稍后再试', icon: 'none' });
    }
  },

  // [2026-04-23 报告分支] 加载报告简要信息，用于顶部报告卡片
  async _loadReportsBrief({ chatId, reportId, reportIds }) {
    try {
      let reports = [];
      if (chatId) {
        const sess = await get(`/api/chat/sessions/${chatId}`, {}, { showLoading: false, suppressErrorToast: true });
        if (sess && Array.isArray(sess.reports_brief)) {
          reports = sess.reports_brief;
        }
      } else if (reportId) {
        const rep = await get(`/api/checkup/reports/${reportId}`, {}, { showLoading: false, suppressErrorToast: true });
        if (rep) reports = [rep];
      } else if (reportIds) {
        const ids = String(reportIds).split(',').map(s => parseInt(s, 10)).filter(Boolean);
        for (const rid of ids) {
          const rep = await get(`/api/checkup/reports/${rid}`, {}, { showLoading: false, suppressErrorToast: true });
          if (rep) reports.push(rep);
        }
      }
      const normalized = reports.map(r => {
        const urls = Array.isArray(r.file_urls) && r.file_urls.length > 0
          ? r.file_urls.filter(Boolean)
          : (r.file_url ? [r.file_url] : []);
        const thumbs = Array.isArray(r.thumbnail_urls) && r.thumbnail_urls.length > 0
          ? r.thumbnail_urls.filter(Boolean)
          : urls;
        return {
          id: r.id,
          title: r.title || '体检报告',
          file_urls: urls,
          thumbnail_urls: thumbs,
          display_thumbs: thumbs.slice(0, 4),
          total: urls.length
        };
      });
      this.setData({ reportList: normalized });

      // [Bug-04] 报告加载完成后，若尚未锁定咨询人，则用首份报告的所属人补锁一次
      if (!this.data.lockedFamilyMemberId && reports && reports.length > 0) {
        const firstMemberId = reports[0].family_member_id || reports[0].member_id || null;
        if (firstMemberId) {
          this._lockConsultTargetByMemberId(firstMemberId);
        }
      }
    } catch (e) {
      console.warn('[reports_brief] load failed', e);
    }
  },

  // [2026-04-23 报告分支] 点击报告卡片缩略图：多图预览
  onReportImageTap(e) {
    const { urls, current } = e.currentTarget.dataset;
    if (!urls || urls.length === 0) return;
    wx.previewImage({ current: current || urls[0], urls });
  },

  async _lockConsultTargetByMemberId(memberId) {
    if (!memberId) return;
    await this.loadFamilyMembers();
    const member = this.data.familyMembers.find(m => String(m.id) === String(memberId));
    if (member) {
      this.setData({
        consultTarget: { name: member.name, color: member.color },
        isTypeLocked: true,
        lockedFamilyMemberId: memberId
      });
    }
  },

  async _uploadAndSendImage(filePath) {
    try {
      filePath = await compressImage(filePath);
    } catch (_) { /* 压缩失败回退原图 */ }
    const sizeCheck = await checkFileSize(filePath, 'chat_image');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: '', image: filePath, time }];
    this.setData({ messages, scrollToId: `msg-${id}`, showUploadProgress: true, uploadPercent: 0 });

    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadWithProgress('/api/chat/upload-image', filePath, {
        formData: { session_id: this.data.chatId },
        onProgress: (percent) => this.setData({ uploadPercent: percent })
      });
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的图片，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '图片上传失败，请稍后重试。');
    }
  },

  async _uploadAndSendFile(filePath, fileName) {
    const sizeCheck = await checkFileSize(filePath, 'chat_file');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    this.addMessage('user', `[文件] ${fileName}`);
    this.setData({ showUploadProgress: true, uploadPercent: 0 });
    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadWithProgress('/api/chat/upload-file', filePath, {
        formData: { session_id: this.data.chatId, file_name: fileName },
        onProgress: (percent) => this.setData({ uploadPercent: percent })
      });
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的文件，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '文件上传失败，请稍后重试。');
    }
  },

  // ========================
  // Consult target
  // ========================
  toggleTargetPicker() {
    if (this.data.isSymptomLocked || this.data.isTypeLocked) {
      wx.showToast({
        title: '当前咨询对象已锁定，如需为其他人咨询请返回重新发起',
        icon: 'none',
        duration: 2500
      });
      return;
    }
    if (!this.data.familyMembers.length) {
      this.loadFamilyMembers();
    }
    this.setData({ showTargetPicker: !this.data.showTargetPicker });
  },

  async restoreSessionMember(chatId) {
    try {
      const res = await get(`/api/chat-sessions/${chatId}`, {}, { showLoading: false, suppressErrorToast: true });
      if (res && (res.session_type === 'symptom_check' || res.session_type === 'symptom')) {
        const relation = res.family_member_relation || '本人';
        this.setData({
          isSymptomLocked: true,
          consultTarget: { name: relation, color: getRelationColor(relation) }
        });
      }
      // [Bug-04] 历史会话恢复：报告解读/对比同步锁定咨询人为报告所属人
      if (res && (res.session_type === 'report_interpret' || res.session_type === 'report_compare')) {
        this.setData({ isTypeLocked: true });
        const memberId = res.family_member_id || (res.family_member && res.family_member.id) || null;
        if (memberId) {
          this._lockConsultTargetByMemberId(memberId);
        }
      }
      // drug_identify 卡片 backend 兜底（仅当 URL 参数为空时填充）
      if (res && (res.session_type === 'drug_identify' || res.session_type === 'drug_query')) {
        const updates = {};
        if (!this.data.drugIdentifyMember) {
          const memberInfo = res.family_member_relation || (res.family_member && res.family_member.nickname) || '';
          if (memberInfo) updates.drugIdentifyMember = memberInfo;
        }
        if (!this.data.drugIdentifyDrugNames) {
          const apiDrugs = res.drug_names || res.title || '';
          if (apiDrugs) updates.drugIdentifyDrugNames = apiDrugs;
        }
        if (Object.keys(updates).length > 0) {
          updates.drugIdentifyBannerVisible = true;
          this.setData(updates);
        }
      }
    } catch (e) {
      console.log('restoreSessionMember error', e);
    }
  },

  onSelectTarget(e) {
    const member = e.currentTarget.dataset.member;
    this.setData({
      consultTarget: { name: member.name, color: member.color },
      showTargetPicker: false
    });
  },

  // ========================
  // Voice input
  // ========================
  _initRecognizeManager() {
    const manager = plugin.getRecordRecognitionManager();

    manager.onStart = () => {
      let t = 0;
      this._recordTimer = setInterval(() => {
        t++;
        this.setData({ recordingTime: t });
        if (t >= 30) {
          this._finishRecording();
        }
      }, 1000);
    };

    manager.onStop = (res) => {
      if (this._recordTimer) {
        clearInterval(this._recordTimer);
        this._recordTimer = null;
      }
      if (this._discardNextResult) {
        this._discardNextResult = false;
        return;
      }
      const text = res.result ? res.result.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim() : '';
      if (text) {
        this.setData({ inputValue: text });
        this.sendMessage();
      } else {
        wx.showToast({ title: '未识别到语音内容，请重试', icon: 'none' });
      }
    };

    manager.onError = () => {
      if (this._recordTimer) {
        clearInterval(this._recordTimer);
        this._recordTimer = null;
      }
      this.setData({
        isRecording: false,
        showRecordOverlay: false,
        recordCancelling: false,
        voiceMode: false
      });
      wx.showToast({ title: '语音服务暂不可用，已切换为键盘输入', icon: 'none' });
    };

    this._recognizeManager = manager;
  },

  toggleVoiceMode() {
    if (this.data.voiceMode) {
      this.setData({ voiceMode: false, inputFocus: true });
      return;
    }
    this._checkRecordAuth(() => {
      this.setData({ voiceMode: true, inputFocus: false });
    });
  },

  _checkRecordAuth(successCb) {
    wx.getSetting({
      success: (res) => {
        if (res.authSetting['scope.record']) {
          if (!this._recognizeManager) this._initRecognizeManager();
          successCb();
          return;
        }
        wx.authorize({
          scope: 'scope.record',
          success: () => {
            if (!this._recognizeManager) this._initRecognizeManager();
            successCb();
          },
          fail: () => {
            wx.showModal({
              title: '允许访问麦克风',
              content: '请授权麦克风，以便AI发送语音消息',
              cancelText: '取消',
              confirmText: '去授权',
              success: (modalRes) => {
                if (modalRes.confirm) {
                  wx.openSetting({
                    success: (settingRes) => {
                      if (settingRes.authSetting['scope.record']) {
                        if (!this._recognizeManager) this._initRecognizeManager();
                        successCb();
                      } else {
                        wx.showToast({ title: '请在设置中开启麦克风权限', icon: 'none' });
                      }
                    }
                  });
                } else {
                  wx.showToast({ title: '请在设置中开启麦克风权限', icon: 'none' });
                }
              }
            });
          }
        });
      }
    });
  },

  onRecordTouchStart(e) {
    this._touchStartY = e.touches[0].clientY;
    this._touchStartTime = Date.now();
    this.setData({
      isRecording: true,
      showRecordOverlay: true,
      recordCancelling: false,
      recordingTime: 0
    });
    if (!this._recognizeManager) this._initRecognizeManager();
    this._recognizeManager.start({ lang: 'zh_CN' });
  },

  onRecordTouchMove(e) {
    if (!this.data.isRecording) return;
    const moveY = this._touchStartY - e.touches[0].clientY;
    this.setData({ recordCancelling: moveY > 80 });
  },

  onRecordTouchEnd() {
    if (!this.data.isRecording) return;
    const duration = Date.now() - this._touchStartTime;
    if (duration < 500) {
      this._cancelRecording();
      wx.showToast({ title: '录音时间太短', icon: 'none' });
      return;
    }
    if (this.data.recordCancelling) {
      this._cancelRecording();
    } else {
      this._finishRecording();
    }
  },

  _finishRecording() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this.setData({
      isRecording: false,
      showRecordOverlay: false,
      recordCancelling: false
    });
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  _cancelRecording() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this.setData({
      isRecording: false,
      showRecordOverlay: false,
      recordCancelling: false
    });
    this._discardNextResult = true;
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  preventTouchMove() {},

  // ========================
  // Message handling
  // ========================
  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content) return;

    // Stop TTS when user sends new message
    this._stopTts();

    this.addMessage('user', content);
    this.setData({ inputValue: '', latestAiMsgId: '' });

    // Try SSE streaming first, fallback to normal request
    try {
      this._startSseStream(this.data.chatId, content);
    } catch (e) {
      // Fallback: normal request
      const loadingId = this.addMessage('loading', '');
      try {
        await this.mockDelay(1000 + Math.random() * 1500);
        this.removeMessage(loadingId);
        const { reply, knowledgeHits } = this.getMockReply(content);
        const msgId = this.addMessage('assistant', reply, knowledgeHits && knowledgeHits.length ? { knowledgeHits } : {});
        this.setData({ latestAiMsgId: msgId });
      } catch (err) {
        this.removeMessage(loadingId);
        this.addMessage('assistant', '抱歉，网络出现了问题，请稍后重试。');
      }
    }
  },

  _parseMessage(content) {
    const parts = content.split('---disclaimer---');
    return {
      mainContent: parts[0].trim(),
      disclaimer: parts.length > 1 ? parts[1].trim() : ''
    };
  },

  addMessage(role, content, extra = {}) {
    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const msgData = { id, role, content, time, ...extra };
    if (role === 'assistant' && content && content.includes('---disclaimer---')) {
      const parsed = this._parseMessage(content);
      msgData.mainContent = parsed.mainContent;
      msgData.disclaimer = parsed.disclaimer;
    }
    if (role === 'assistant' && content) {
      this.setData({ latestAiMsgId: id });
    }
    const messages = [...this.data.messages, msgData];
    this.setData({ messages, scrollToId: `msg-${id}` });
    return id;
  },

  onKnowledgeFeedback(e) {
    const { feedback, hit_log_id: hitLogId } = e.detail || {};
    console.log('knowledge feedback', feedback, hitLogId);
  },

  removeMessage(id) {
    const messages = this.data.messages.filter(m => m.id !== id);
    this.setData({ messages });
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath;
        const id = generateId();
        const now = new Date();
        const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        const messages = [...this.data.messages, { id, role: 'user', content: '', image: tempFilePath, time }];
        this.setData({ messages, scrollToId: `msg-${id}` });

        const loadingId = this.addMessage('loading', '');
        setTimeout(() => {
          this.removeMessage(loadingId);
          this.addMessage('assistant', '我已收到您上传的图片。根据图片信息，建议您：\n\n1. 注意保持良好的生活习惯\n2. 如症状持续请及时就医\n3. 可以详细描述您的不适症状，我会为您提供更准确的分析');
        }, 2000);
      }
    });
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    wx.previewImage({ current: url, urls: [url] });
  },

  mockDelay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  getMockReply(question) {
    const demoHits =
      question.includes('知识库') || question.includes('维生素')
        ? [
            {
              entry_id: 'demo-1',
              kb_id: 0,
              type: 'qa',
              question: '示例：维生素C有什么作用？',
              title: '知识库参考',
              hit_log_id: 0,
              content_json: {
                text: '维生素C有助于增强免疫力、促进胶原蛋白合成，并帮助铁的吸收。日常可通过新鲜蔬果适量补充。',
                images: [],
                products: [
                  {
                    name: '维生素C咀嚼片（示例）',
                    price: '68',
                    image: '',
                    url: ''
                  }
                ]
              }
            }
          ]
        : null;

    if (question.includes('头痛') || question.includes('头疼')) {
      return {
        reply:
          '根据您描述的头痛症状，可能的原因有：\n\n1. **紧张性头痛**：压力大、睡眠不足\n2. **偏头痛**：单侧搏动性疼痛\n3. **颈椎问题**：长时间低头导致\n\n建议：\n• 保持充足睡眠\n• 适当休息，减少用眼\n• 若持续加重请及时就医\n\n请问您头痛的位置是哪里？持续多长时间了？',
        knowledgeHits: demoHits
      };
    }
    if (question.includes('感冒') || question.includes('发烧')) {
      return {
        reply:
          '感冒症状的自我调理建议：\n\n1. 多休息，保证充足睡眠\n2. 多喝温水，促进新陈代谢\n3. 饮食清淡，多吃蔬果\n4. 注意保暖，避免再次受凉\n\n⚠️ 如果体温超过38.5°C或持续3天以上，建议及时就医。\n\n请问您目前有哪些具体症状？体温多少度？',
        knowledgeHits: demoHits
      };
    }
    if (question.includes('失眠') || question.includes('睡不着')) {
      return {
        reply:
          '失眠的调理建议：\n\n1. **作息规律**：固定起床和就寝时间\n2. **睡前放松**：可以尝试深呼吸、冥想\n3. **环境改善**：保持卧室安静、黑暗、凉爽\n4. **避免刺激**：睡前2小时不使用电子设备\n5. **饮食注意**：避免咖啡因和酒精\n\n如果失眠超过一个月，建议寻求专业医生帮助。',
        knowledgeHits: demoHits
      };
    }
    return {
      reply:
        '感谢您的描述。根据您提供的信息，我有以下建议：\n\n1. 建议保持良好的作息习惯\n2. 注意饮食均衡，适当运动\n3. 如症状持续或加重，请及时到医院就诊\n\n您可以进一步描述：\n• 症状持续时间\n• 是否有加重或缓解的因素\n• 既往病史和用药情况\n\n这样我能为您提供更准确的分析。',
      knowledgeHits: demoHits
    };
  }
});
