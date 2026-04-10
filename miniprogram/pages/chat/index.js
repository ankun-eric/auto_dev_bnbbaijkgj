const { post, get, put, del, uploadFile } = require('../../utils/request');
const { generateId } = require('../../utils/util');

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
    functionButtons: []
  },

  _recognizeManager: null,
  _recordTimer: null,
  _touchStartY: 0,
  _touchStartTime: 0,
  _discardNextResult: false,
  _btnCacheExpire: 0,

  onLoad(options) {
    const { type = 'health_qa', chatId, question } = options;
    this.setData({ chatType: type, chatId: chatId || generateId() });

    wx.showShareMenu({ withShareTicket: true, menus: ['shareAppMessage', 'shareTimeline'] });

    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考'
    };
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI健康咨询' });

    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);

    this.loadFontSetting();
    this.loadFamilyMembers();
    this.loadFunctionButtons();

    if (question) {
      setTimeout(() => {
        this.setData({ inputValue: decodeURIComponent(question) });
        this.sendMessage();
      }, 500);
    }

    if (chatId) {
      this.loadChatHistory(chatId);
    }
  },

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

  onShareAppMessage() {
    const chatId = this.data.chatId;
    return {
      title: '宾尼小康AI健康咨询',
      path: `/pages/chat/index?chatId=${chatId}&type=${this.data.chatType}`
    };
  },

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
      messages: []
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
      messages: []
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

  async _uploadAndSendImage(filePath) {
    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: '', image: filePath, time }];
    this.setData({ messages, scrollToId: `msg-${id}` });

    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadFile('/api/chat/upload-image', filePath, 'file', { session_id: this.data.chatId });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的图片，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.removeMessage(loadingId);
      this.addMessage('assistant', '图片上传失败，请稍后重试。');
    }
  },

  async _uploadAndSendFile(filePath, fileName) {
    this.addMessage('user', `[文件] ${fileName}`);
    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadFile('/api/chat/upload-file', filePath, 'file', { session_id: this.data.chatId, file_name: fileName });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的文件，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.removeMessage(loadingId);
      this.addMessage('assistant', '文件上传失败，请稍后重试。');
    }
  },

  toggleTargetPicker() {
    if (!this.data.familyMembers.length) {
      this.loadFamilyMembers();
    }
    this.setData({ showTargetPicker: !this.data.showTargetPicker });
  },

  onSelectTarget(e) {
    const member = e.currentTarget.dataset.member;
    this.setData({
      consultTarget: { name: member.name, color: member.color },
      showTargetPicker: false
    });
  },

  onUnload() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this._recognizeManager = null;
  },

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

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content) return;

    this.addMessage('user', content);
    this.setData({ inputValue: '' });

    const loadingId = this.addMessage('loading', '');

    try {
      // const res = await post(`/api/chat/sessions/${sessionId}/messages`, {
      //   chatId: this.data.chatId,
      //   type: this.data.chatType,
      //   message: content
      // });
      await this.mockDelay(1000 + Math.random() * 1500);
      this.removeMessage(loadingId);
      const { reply, knowledgeHits } = this.getMockReply(content);
      this.addMessage('assistant', reply, knowledgeHits && knowledgeHits.length ? { knowledgeHits } : {});
    } catch (e) {
      this.removeMessage(loadingId);
      this.addMessage('assistant', '抱歉，网络出现了问题，请稍后重试。');
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
