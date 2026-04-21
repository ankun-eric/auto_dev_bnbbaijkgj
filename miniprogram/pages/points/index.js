const { get, post } = require('../../utils/request');

Page({
  data: {
    totalPoints: 0,
    availablePoints: 0,
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
        // Bug #4: 可用积分统一读取后端 available_points / available 字段，前端不再自行计算
        const total = s.total_points != null ? s.total_points : 0;
        const available = s.available_points != null
          ? s.available_points
          : (s.available != null ? s.available : total);
        update.totalPoints = total;
        update.availablePoints = Number(available) || 0;
        update.todayEarned = s.today_earned_points || 0;
        update.signedToday = !!s.signed_today;
      }
      if (tasks.status === 'fulfilled') {
        const t = tasks.value || {};
        const items = (t.items || []).map(i => {
          const onceDone = !!(i.completed && i.category === 'once');
          return {
            ...i,
            categoryLabel: i.category === 'daily' ? '每日' : i.category === 'once' ? '一次性' : '可重复',
            categoryColor: i.category === 'daily' ? '#52c41a' : i.category === 'once' ? '#fa8c16' : '#1890ff',
            onceDone,
            btnText: onceDone ? '✓ 已完成'
              : (i.completed && i.category === 'daily') ? '已完成'
              : (i.action_type === 'sign_in') ? '去签到'
              : (i.key === 'complete_profile') ? '去完善'
              : '去完成',
            btnDisabled: onceDone
          };
        });
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

  goExchangeRecords() {
    wx.navigateTo({ url: '/pages/points-exchange-records/index' });
  },

  // PRD F3：新合并入口，跳到积分明细聚合页（默认 积分明细 Tab）
  goDetail() {
    wx.navigateTo({ url: '/pages/points/detail/index' });
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
    // Bug 7：后端已统一为 /health-profile；/profile/edit 兼容旧值
    // Bug 8：first_order 任务已被后端过滤，前端不再硬编码其跳转
    const map = {
      '/health-profile': '/pages/health-profile/index',
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
