const { get } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    consultTypes: [
      { id: 'general', name: '综合问诊', desc: '全科健康咨询', icon: '🩺', bgColor: 'rgba(82,196,26,0.12)' },
      { id: 'symptom', name: '症状分析', desc: '智能症状自查', icon: '🔍', bgColor: 'rgba(19,194,194,0.12)' },
      { id: 'tcm', name: '中医问诊', desc: '中医辨证论治', icon: '🌿', bgColor: 'rgba(114,46,209,0.12)' },
      { id: 'nutrition', name: '营养咨询', desc: '饮食健康指导', icon: '🥗', bgColor: 'rgba(250,173,20,0.12)' }
    ],
    quickQuestions: [
      '最近经常头痛怎么办？',
      '感冒了吃什么药好？',
      '失眠有什么好的调理方法？',
      '血压偏高该注意什么？'
    ],
    chatHistory: [
      { id: '1', type: '综合问诊', summary: '关于最近失眠的咨询，AI建议保持规律作息...', time: '今天 14:30' },
      { id: '2', type: '症状分析', summary: '头痛伴有眩晕症状分析结果...', time: '昨天 09:15' }
    ]
  },

  onLoad() {
    this.loadChatHistory();
  },

  onShow() {
    this.loadChatHistory();
  },

  async loadChatHistory() {
    try {
      // const res = await get('/api/chat/sessions');
      // this.setData({ chatHistory: res.data });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
  },

  startConsult(e) {
    if (!checkLogin()) return;
    const type = e.currentTarget.dataset.type;
    wx.navigateTo({ url: `/pages/chat/index?type=${type.id}` });
  },

  quickAsk(e) {
    if (!checkLogin()) return;
    const question = e.currentTarget.dataset.question;
    wx.navigateTo({ url: `/pages/chat/index?type=general&question=${encodeURIComponent(question)}` });
  },

  continueChat(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/chat/index?chatId=${id}` });
  },

  newChat() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=general' });
  },

  viewAllChats() {
    wx.navigateTo({ url: '/pages/chat/index?viewHistory=true' });
  }
});
