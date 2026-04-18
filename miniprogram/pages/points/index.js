const { get, post } = require('../../utils/request');

Page({
  data: {
    totalPoints: 0,
    todayEarned: 0,
    signedToday: false,
    tasks: [],
    loading: true,
    signing: false
  },

  onLoad() {
    this.fetchAll();
  },

  onShow() {
    this.fetchAll();
  },

  onPullDownRefresh() {
    this.fetchAll().finally(() => wx.stopPullDownRefresh());
  },

  async fetchAll() {
    try {
      const [summary, tasks] = await Promise.allSettled([
        get('/api/points/summary', {}, { showLoading: false }),
        get('/api/points/tasks', {}, { showLoading: false })
      ]);
      const update = {};
      if (summary.status === 'fulfilled') {
        const s = summary.value || {};
        update.totalPoints = s.total_points || 0;
        update.todayEarned = s.today_earned_points || 0;
        update.signedToday = !!s.signed_today;
      }
      if (tasks.status === 'fulfilled') {
        const t = tasks.value || {};
        const items = (t.items || []).map(i => ({
          ...i,
          categoryLabel: i.category === 'daily' ? '每日' : i.category === 'once' ? '一次性' : '可重复',
          categoryColor: i.category === 'daily' ? '#52c41a' : i.category === 'once' ? '#fa8c16' : '#1890ff',
          btnText: (i.completed && i.category === 'once') ? '✅ 已完成'
            : (i.completed && i.category === 'daily') ? '已完成'
            : (i.action_type === 'sign_in') ? '去签到'
            : (i.key === 'complete_profile') ? '去完善'
            : '去完成',
          btnDisabled: i.completed && i.category === 'once'
        }));
        update.tasks = items;
      }
      update.loading = false;
      this.setData(update);
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  goRecords() {
    wx.navigateTo({ url: '/pages/points/records/index' });
  },

  goMall() {
    wx.navigateTo({ url: '/pages/points-mall/index' });
  },

  async handleTask(e) {
    const key = e.currentTarget.dataset.key;
    const task = this.data.tasks.find(t => t.key === key);
    if (!task) return;
    if (task.btnDisabled) return;
    if (task.action_type === 'sign_in') {
      return this.handleSignIn();
    }
    if (task.completed && task.category === 'once') return;
    if (task.route) {
      const route = this.normalizeRoute(task.route);
      if (route) {
        wx.navigateTo({ url: route, fail: () => wx.switchTab({ url: route }) });
      }
    }
  },

  normalizeRoute(route) {
    const map = {
      '/profile/edit': '/pages/health-profile/index',
      '/health-plan': '/pages/health-plan/index',
      '/orders?tab=pending_review': '/pages/unified-orders/index?status=pending_review',
      '/invite': '/pages/invite/index',
      '/products': '/pages/products/index',
      '/mall': '/pages/products/index'
    };
    return map[route] || route;
  },

  async handleSignIn() {
    if (this.data.signedToday || this.data.signing) return;
    this.setData({ signing: true });
    try {
      const res = await post('/api/points/signin', {}, { showLoading: false });
      const earned = res.points_earned || 0;
      wx.showToast({ title: earned ? `签到成功 +${earned}` : '签到成功', icon: 'success' });
      this.fetchAll();
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '签到失败', icon: 'none' });
    } finally {
      this.setData({ signing: false });
    }
  }
});
