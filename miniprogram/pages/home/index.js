const { get } = require('../../utils/request');
const { syncTabBar } = require('../../utils/util');

Page({
  data: {
    pageMode: 'user',
    canSwitchRole: false,
    currentStore: null,
    merchantUserName: '',
    todayCount: 0,
    todayAmount: '0.00',
    banners: [
      { id: 1, title: 'AI健康咨询', desc: '24小时在线，专业健康咨询', bgColor: 'linear-gradient(135deg, #52c41a, #13c2c2)' },
      { id: 2, title: '体检报告解读', desc: '上传报告，AI秒级分析', bgColor: 'linear-gradient(135deg, #13c2c2, #1890ff)' },
      { id: 3, title: '中医智能辨证', desc: '舌诊面诊，科学辨体质', bgColor: 'linear-gradient(135deg, #722ed1, #eb2f96)' }
    ],
    menuItems: [
      { id: 'ai', label: 'AI健康咨询', icon: '🤖', bgColor: 'rgba(82,196,26,0.12)', path: '/pages/chat/index?type=health_qa' },
      { id: 'checkup', label: '体检报告', icon: '📋', bgColor: 'rgba(19,194,194,0.12)', path: '/pages/checkup/index' },
      { id: 'symptom', label: '症状自查', icon: '🩺', bgColor: 'rgba(24,144,255,0.12)', path: '/pages/symptom/index' },
      { id: 'tcm', label: '中医辨证', icon: '🌿', bgColor: 'rgba(114,46,209,0.12)', path: '/pages/tcm/index' },
      { id: 'drug', label: '用药参考', icon: '💊', bgColor: 'rgba(250,173,20,0.12)', path: '/pages/drug/index' },
      { id: 'plan', label: '健康计划', icon: '📅', bgColor: 'rgba(235,47,150,0.12)', path: '/pages/health-plan/index' }
    ],
    healthTips: [
      { id: 1, content: '今日气温变化大，注意添衣保暖' },
      { id: 2, content: '建议每天饮水 2000ml 以上' }
    ],
    articles: [
      { id: 1, title: '春季养生：如何预防过敏性鼻炎', tag: '养生', time: '2小时前', cover: '' },
      { id: 2, title: '高血压患者饮食指南：这些食物要少吃', tag: '饮食', time: '5小时前', cover: '' },
      { id: 3, title: '运动健身：适合上班族的5分钟锻炼法', tag: '运动', time: '1天前', cover: '' }
    ],
    unreadCount: 3,
    loading: false
  },

  onShow() {
    syncTabBar(this, '/pages/home/index');
    if (!this.syncRoleState()) return;
    this.loadCurrentModeData();
  },

  onPullDownRefresh() {
    if (!this.syncRoleState()) {
      wx.stopPullDownRefresh();
      return;
    }
    this.loadCurrentModeData().finally(() => wx.stopPullDownRefresh());
  },

  syncRoleState() {
    const app = getApp();
    const pageMode = app.getCurrentRole() || 'user';
    if (pageMode === 'merchant') {
      if (!app.hasMerchantIdentity()) {
        wx.navigateTo({ url: '/pages/no-permission/index?scene=merchant' });
        return false;
      }
      if (!app.getCurrentStore()) {
        wx.navigateTo({ url: '/pages/store-select/index' });
        return false;
      }
    } else if (app.globalData.isLoggedIn && !app.hasUserIdentity()) {
      wx.navigateTo({ url: '/pages/no-permission/index?scene=user' });
      return false;
    }

    const merchantProfile = app.getMerchantProfile() || {};
    this.setData({
      pageMode,
      canSwitchRole: app.isDualIdentity(),
      currentStore: app.getCurrentStore(),
      merchantUserName: merchantProfile.nickname || (app.getUserInfo() || {}).nickname || '工作人员'
    });
    return true;
  },

  loadCurrentModeData() {
    if (this.data.pageMode === 'merchant') {
      return this.loadMerchantDashboard();
    }
    return this.loadUserData();
  },

  async loadUserData() {
    this.setData({ loading: true });
    try {
      // 用户端首页暂继续沿用现有静态展示与后续页面能力。
    } finally {
      this.setData({ loading: false });
    }
  },

  async loadMerchantDashboard() {
    const currentStore = this.data.currentStore;
    if (!currentStore) return Promise.resolve();
    this.setData({ loading: true });
    try {
      const res = await get('/api/merchant/dashboard', { store_id: currentStore.id }, { showLoading: false });
      this.setData({
        todayCount: res.today_count || 0,
        todayAmount: Number(res.today_amount || 0).toFixed(2)
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '商家数据加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  switchRole() {
    const app = getApp();
    if (!app.isDualIdentity()) return;
    const currentRole = this.data.pageMode;
    const targetRole = currentRole === 'merchant' ? 'user' : 'merchant';
    const targetLabel = targetRole === 'merchant' ? '商家端' : '用户端';
    wx.showModal({
      title: '切换角色',
      content: `确认切换到${targetLabel}吗？`,
      success: (res) => {
        if (!res.confirm) return;
        app.setCurrentRole(targetRole);
        if (targetRole === 'merchant') {
          app.clearCurrentStore();
          wx.navigateTo({ url: '/pages/store-select/index' });
          return;
        }
        wx.switchTab({ url: '/pages/home/index' });
      }
    });
  },

  onSearchTap() {
    if (this.data.pageMode !== 'user') return;
    wx.navigateTo({ url: '/pages/articles/index?focus=true' });
  },

  goNotifications() {
    if (this.data.pageMode === 'merchant') {
      wx.navigateTo({ url: '/pages/merchant-messages/index' });
      return;
    }
    wx.navigateTo({ url: '/pages/notifications/index' });
  },

  onMenuTap(e) {
    if (this.data.pageMode !== 'user') return;
    const item = e.currentTarget.dataset.item;
    wx.navigateTo({ url: item.path });
  },

  goArticles() {
    wx.navigateTo({ url: '/pages/articles/index' });
  },

  goArticleDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
  },

  goScan() {
    wx.switchTab({ url: '/pages/ai/index' });
  },

  goRecords() {
    wx.switchTab({ url: '/pages/services/index' });
  }
});
