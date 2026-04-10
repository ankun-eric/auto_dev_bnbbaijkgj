const { get, post } = require('../../utils/request');

Page({
  data: {
    categories: [
      { key: 'medication', icon: '💊', name: '用药提醒', desc: '按时服药，健康管理', color: '#52c41a', url: '/pages/health-plan/medications/index' },
      { key: 'checkin', icon: '✅', name: '健康打卡', desc: '每日打卡，养成习惯', color: '#13c2c2', url: '/pages/health-plan/checkin/index' },
      { key: 'plan', icon: '📋', name: '自定义计划', desc: '个性化健康计划', color: '#1890ff', url: '/pages/health-plan/categories/index' }
    ],
    stats: null,
    statsLoading: false,
    todayTodos: [],
    todayLoading: false,
    aiGenerating: false
  },

  onShow() {
    this.loadStats();
    this.loadTodayTodos();
  },

  onPullDownRefresh() {
    Promise.all([this.loadStats(), this.loadTodayTodos()])
      .finally(() => wx.stopPullDownRefresh());
  },

  async loadStats() {
    this.setData({ statsLoading: true });
    try {
      const res = await get('/api/health-plan/statistics', {}, { showLoading: false, suppressErrorToast: true });
      this.setData({ stats: res });
    } catch (e) {
      this.setData({ stats: null });
    } finally {
      this.setData({ statsLoading: false });
    }
  },

  async loadTodayTodos() {
    this.setData({ todayLoading: true });
    try {
      const res = await get('/api/health-plan/today-todos', {}, { showLoading: false, suppressErrorToast: true });
      const items = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      this.setData({ todayTodos: items.slice(0, 5) });
    } catch (e) {
      this.setData({ todayTodos: [] });
    } finally {
      this.setData({ todayLoading: false });
    }
  },

  onCategoryTap(e) {
    const { url } = e.currentTarget.dataset;
    if (url) wx.navigateTo({ url });
  },

  async onAiGenerate() {
    if (this.data.aiGenerating) return;
    this.setData({ aiGenerating: true });
    try {
      await post('/api/health-plan/ai-generate', {});
      wx.showToast({ title: 'AI计划已生成', icon: 'success' });
      this.loadTodayTodos();
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ aiGenerating: false });
    }
  },

  goStatistics() {
    wx.navigateTo({ url: '/pages/health-plan/statistics/index' });
  },

  async onTodoCheckin(e) {
    const { type, id, taskId } = e.currentTarget.dataset;
    let url = '';
    if (type === 'medication') {
      url = `/api/health-plan/medications/${id}/checkin`;
    } else if (type === 'checkin_item') {
      url = `/api/health-plan/checkin-items/${id}/checkin`;
    } else if (type === 'plan_task') {
      url = `/api/health-plan/user-plans/${id}/tasks/${taskId}/checkin`;
    }
    if (!url) return;
    try {
      await post(url, {});
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadTodayTodos();
      this.loadStats();
    } catch (e) {
      // error handled by request
    }
  }
});
