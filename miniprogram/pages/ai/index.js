const { get, post } = require('../../utils/request');
const { checkLogin, ensureMerchantEntry, syncTabBar } = require('../../utils/util');

Page({
  data: {
    pageMode: 'user',
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
    ],
    orderInfo: null,
    verifying: false
  },

  onShow() {
    syncTabBar(this, '/pages/ai/index');
    const app = getApp();
    const pageMode = app.getCurrentRole() || 'user';
    this.setData({ pageMode });
    if (pageMode === 'merchant') {
      if (!ensureMerchantEntry()) return;
      this.setData({ orderInfo: null });
      return;
    }
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
    if (this.data.pageMode !== 'user') {
      this.startScan();
      return;
    }
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
  },

  startScan() {
    if (!ensureMerchantEntry()) return;
    this.setData({ orderInfo: null });
    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        this.queryOrder(res.result);
      },
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '扫码失败，请重试', icon: 'none' });
        }
      }
    });
  },

  async queryOrder(code) {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    if (!currentStore) return;
    wx.showLoading({ title: '查询订单中...' });
    try {
      const res = await get(`/api/merchant/orders/verify-code/${encodeURIComponent(code)}`, {
        store_id: currentStore.id
      }, { showLoading: false });
      this.setData({ orderInfo: res });
    } catch (e) {
      wx.showToast({ title: e.detail || '未找到对应订单', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  handleVerify() {
    const orderInfo = this.data.orderInfo;
    if (!orderInfo || !orderInfo.id) return;
    wx.showModal({
      title: '确认核销',
      content: `确定要核销订单 ${orderInfo.order_no} 吗？`,
      confirmColor: '#52c41a',
      success: (res) => {
        if (res.confirm) {
          this.doVerify(orderInfo.id);
        }
      }
    });
  },

  async doVerify(orderId) {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    const orderInfo = this.data.orderInfo;
    if (!currentStore || !orderInfo) return;
    this.setData({ verifying: true });
    try {
      await post(`/api/merchant/orders/${orderId}/verify`, {
        store_id: currentStore.id,
        code: orderInfo.verification_code
      }, { showLoading: false });
      wx.showToast({ title: '核销成功', icon: 'success' });
      this.setData({
        orderInfo: {
          ...orderInfo,
          status: 'verified'
        }
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '核销失败', icon: 'none' });
    } finally {
      this.setData({ verifying: false });
    }
  }
});
