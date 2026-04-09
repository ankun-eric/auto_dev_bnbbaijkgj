const { post, get, put, del } = require('../../utils/request');
const { generateId } = require('../../utils/util');

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
    msgFontSize: '28rpx'
  },

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
