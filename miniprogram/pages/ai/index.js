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
    chatHistory: [],
    drawerShow: false,
    allSessions: [],
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
      const res = await get('/api/chat-sessions', { page: 1, page_size: 100 }, { showLoading: false, suppressErrorToast: true });
      const sessions = Array.isArray(res) ? res : (res.items || res.data || []);
      this.setData({
        allSessions: sessions,
        chatHistory: sessions.slice(0, 3).map(s => ({
          id: s.id,
          type: this._getTypeLabel(s.session_type),
          summary: s.title || '未命名对话',
          time: this._formatSessionTime(s.updated_at || s.created_at)
        }))
      });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
  },

  _getTypeLabel(type) {
    const map = { general: '综合问诊', symptom: '症状分析', tcm: '中医问诊', nutrition: '营养咨询' };
    return map[type] || type || '对话';
  },

  _formatSessionTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const ts = d.getTime();
    const pad = n => String(n).padStart(2, '0');
    const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    if (ts >= todayStart) return `今天 ${timeStr}`;
    if (ts >= todayStart - 86400000) return `昨天 ${timeStr}`;
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${timeStr}`;
  },

  openDrawer() {
    if (!checkLogin()) return;
    this.setData({ drawerShow: true });
  },

  onDrawerClose() {
    this.setData({ drawerShow: false });
  },

  onSessionTap(e) {
    const { session } = e.detail;
    this.setData({ drawerShow: false });
    wx.navigateTo({ url: `/pages/chat/index?chatId=${session.id}&type=${session.session_type || 'general'}` });
  },

  onDrawerNewChat() {
    this.setData({ drawerShow: false });
    wx.navigateTo({ url: '/pages/chat/index?type=general' });
  },

  onDrawerRefresh() {
    this.loadChatHistory();
  },

  onDrawerShare(e) {
    const { session, shareToken, shareUrl } = e.detail;
    wx.setClipboardData({
      data: shareUrl || shareToken,
      success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
    });
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
    if (!checkLogin()) return;
    this.setData({ drawerShow: true });
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
