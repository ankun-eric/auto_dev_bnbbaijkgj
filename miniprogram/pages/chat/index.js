const { post, get } = require('../../utils/request');
const { generateId } = require('../../utils/util');

Page({
  data: {
    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    chatId: '',
    chatType: 'general'
  },

  onLoad(options) {
    const { type = 'general', chatId, question } = options;
    this.setData({ chatType: type, chatId: chatId || generateId() });

    const typeNames = {
      general: '综合问诊', symptom: '症状分析', tcm: '中医问诊', nutrition: '营养咨询'
    };
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI问诊' });

    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);

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

  async loadChatHistory(chatId) {
    try {
      // const res = await get(`/api/chat/${chatId}/messages`);
      // this.setData({ messages: res.data });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
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
      const reply = this.getMockReply(content);
      this.addMessage('assistant', reply);
    } catch (e) {
      this.removeMessage(loadingId);
      this.addMessage('assistant', '抱歉，网络出现了问题，请稍后重试。');
    }
  },

  addMessage(role, content) {
    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role, content, time }];
    this.setData({ messages, scrollToId: `msg-${id}` });
    return id;
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
    if (question.includes('头痛') || question.includes('头疼')) {
      return '根据您描述的头痛症状，可能的原因有：\n\n1. **紧张性头痛**：压力大、睡眠不足\n2. **偏头痛**：单侧搏动性疼痛\n3. **颈椎问题**：长时间低头导致\n\n建议：\n• 保持充足睡眠\n• 适当休息，减少用眼\n• 若持续加重请及时就医\n\n请问您头痛的位置是哪里？持续多长时间了？';
    }
    if (question.includes('感冒') || question.includes('发烧')) {
      return '感冒症状的自我调理建议：\n\n1. 多休息，保证充足睡眠\n2. 多喝温水，促进新陈代谢\n3. 饮食清淡，多吃蔬果\n4. 注意保暖，避免再次受凉\n\n⚠️ 如果体温超过38.5°C或持续3天以上，建议及时就医。\n\n请问您目前有哪些具体症状？体温多少度？';
    }
    if (question.includes('失眠') || question.includes('睡不着')) {
      return '失眠的调理建议：\n\n1. **作息规律**：固定起床和就寝时间\n2. **睡前放松**：可以尝试深呼吸、冥想\n3. **环境改善**：保持卧室安静、黑暗、凉爽\n4. **避免刺激**：睡前2小时不使用电子设备\n5. **饮食注意**：避免咖啡因和酒精\n\n如果失眠超过一个月，建议寻求专业医生帮助。';
    }
    return '感谢您的描述。根据您提供的信息，我有以下建议：\n\n1. 建议保持良好的作息习惯\n2. 注意饮食均衡，适当运动\n3. 如症状持续或加重，请及时到医院就诊\n\n您可以进一步描述：\n• 症状持续时间\n• 是否有加重或缓解的因素\n• 既往病史和用药情况\n\n这样我能为您提供更准确的分析。';
  }
});
