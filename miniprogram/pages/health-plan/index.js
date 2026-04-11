const { get, post } = require('../../utils/request');
const { showCheckinPointsToast } = require('../../utils/checkin-points');

Page({
  data: {
    categories: [
      { key: 'medication', icon: '💊', name: '用药提醒', desc: '按时服药，健康管理', color: '#52c41a', url: '/pages/health-plan/medications/index' },
      { key: 'checkin', icon: '✅', name: '健康打卡', desc: '每日打卡，养成习惯', color: '#13c2c2', url: '/pages/health-plan/checkin/index' },
      { key: 'plan', icon: '📋', name: '自定义计划', desc: '个性化健康计划', color: '#1890ff', url: '/pages/health-plan/categories/index' }
    ],
    stats: null,
    statsLoading: false,
    todoGroups: [],
    todoTotalCompleted: 0,
    todoTotalCount: 0,
    todayLoading: false,
    aiGenerating: false,
    pointsRefreshKey: 0,
    checkinDialog: false,
    checkinDialogType: '',
    checkinDialogId: 0,
    checkinDialogSourceId: 0,
    checkinDialogName: '',
    checkinDialogTarget: 0,
    checkinDialogUnit: '',
    checkinDialogValue: ''
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
      if (res) {
        res.streak_days = res.consecutive_days || res.streak_days || 0;
        res.total_checkins = (res.today_completed || 0);
      }
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
      if (res && res.groups) {
        this.setData({
          todoGroups: res.groups || [],
          todoTotalCompleted: res.total_completed || 0,
          todoTotalCount: res.total_count || 0,
        });
      } else {
        this.setData({ todoGroups: [], todoTotalCompleted: 0, todoTotalCount: 0 });
      }
    } catch (e) {
      this.setData({ todoGroups: [], todoTotalCompleted: 0, todoTotalCount: 0 });
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

  onTodoCheckin(e) {
    const { type, id, sourceId, targetValue, targetUnit, name } = e.currentTarget.dataset;
    if (targetValue && targetValue > 0) {
      this.setData({
        checkinDialog: true,
        checkinDialogType: type,
        checkinDialogId: id,
        checkinDialogSourceId: sourceId,
        checkinDialogName: name || '',
        checkinDialogTarget: targetValue,
        checkinDialogUnit: targetUnit || '',
        checkinDialogValue: '',
      });
      return;
    }
    this.doCheckin(type, id, sourceId, null);
  },

  onCheckinDialogInput(e) {
    this.setData({ checkinDialogValue: e.detail.value });
  },

  onCheckinDialogCancel() {
    this.setData({ checkinDialog: false });
  },

  onCheckinDialogConfirm() {
    const { checkinDialogType, checkinDialogId, checkinDialogSourceId, checkinDialogValue } = this.data;
    const val = checkinDialogValue ? parseFloat(checkinDialogValue) : null;
    this.setData({ checkinDialog: false });
    this.doCheckin(checkinDialogType, checkinDialogId, checkinDialogSourceId, val);
  },

  async doCheckin(type, id, sourceId, value) {
    let url = '';
    let body = {};
    if (type === 'medication') {
      url = `/api/health-plan/medications/${id}/checkin`;
    } else if (type === 'checkin') {
      url = `/api/health-plan/checkin-items/${id}/checkin`;
      if (value != null) body.actual_value = value;
    } else if (type === 'plan_task') {
      url = `/api/health-plan/user-plans/${sourceId}/tasks/${id}/checkin`;
      if (value != null) body.actual_value = value;
    }
    if (!url) return;
    try {
      const result = await post(url, body);
      showCheckinPointsToast(result);
      this.setData({ pointsRefreshKey: this.data.pointsRefreshKey + 1 });
      this.loadTodayTodos();
      this.loadStats();
    } catch (e) {
      // error handled by request
    }
  }
});
