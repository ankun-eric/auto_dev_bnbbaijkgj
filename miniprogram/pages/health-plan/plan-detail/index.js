const { get, post } = require('../../../utils/request');

Page({
  data: {
    id: '',
    plan: null,
    tasks: [],
    loading: false,
    joining: false
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ id: options.id });
      this.loadDetail(options.id);
    }
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/health-plan/recommended-plans/${id}`, {}, { showLoading: false });
      if (res) {
        wx.setNavigationBarTitle({ title: res.name || '计划详情' });
        const tasks = (res.tasks || res.items || []).map(function(t) {
          return Object.assign({}, t, { name: t.task_name || t.name });
        });
        this.setData({ plan: res, tasks });
      }
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async onJoin() {
    if (this.data.joining) return;
    this.setData({ joining: true });
    try {
      await post(`/api/health-plan/recommended-plans/${this.data.id}/join`, {});
      wx.showToast({ title: '已加入计划', icon: 'success' });
      setTimeout(() => {
        wx.navigateBack({ delta: 2 });
      }, 1500);
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ joining: false });
    }
  }
});
