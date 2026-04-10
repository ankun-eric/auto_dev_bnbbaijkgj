const { get, post } = require('../../../utils/request');

Page({
  data: {
    id: '',
    plan: null,
    tasks: [],
    loading: false
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ id: options.id });
    }
  },

  onShow() {
    if (this.data.id) {
      this.loadDetail(this.data.id);
    }
  },

  onPullDownRefresh() {
    if (this.data.id) {
      this.loadDetail(this.data.id).finally(() => wx.stopPullDownRefresh());
    } else {
      wx.stopPullDownRefresh();
    }
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/health-plan/user-plans/${id}`, {}, { showLoading: false });
      if (res) {
        const planName = res.plan_name || res.name || '计划详情';
        wx.setNavigationBarTitle({ title: planName });
        const tasks = (res.tasks || res.items || []).map(function(t) {
          return Object.assign({}, t, {
            name: t.task_name || t.name,
            is_completed: t.today_completed || t.is_completed || false,
          });
        });
        const doneCount = tasks.filter(function(t) { return t.is_completed; }).length;
        const progress = tasks.length > 0 ? Math.round((doneCount / tasks.length) * 100) : 0;
        this.setData({
          plan: Object.assign({}, res, { name: planName, progress: progress }),
          tasks: tasks,
        });
      }
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async onTaskCheckin(e) {
    const taskId = e.currentTarget.dataset.taskId;
    try {
      await post(`/api/health-plan/user-plans/${this.data.id}/tasks/${taskId}/checkin`, {});
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadDetail(this.data.id);
    } catch (e) {
      // error handled by request
    }
  },

  computeProgress() {
    const tasks = this.data.tasks;
    if (!tasks.length) return 0;
    const done = tasks.filter(t => t.is_completed || t.today_checked).length;
    return Math.round((done / tasks.length) * 100);
  }
});
