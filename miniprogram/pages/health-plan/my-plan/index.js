const { get, post } = require('../../../utils/request');

Page({
  data: {
    id: '',
    plan: null,
    tasks: [],
    loading: false,
    checkinDialog: false,
    checkinTaskId: 0,
    checkinTaskName: '',
    checkinTarget: 0,
    checkinUnit: '',
    checkinValue: ''
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
            today_completed: t.today_completed || false,
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

  onTaskCheckin(e) {
    const taskId = e.currentTarget.dataset.taskId;
    const targetValue = e.currentTarget.dataset.targetValue;
    const targetUnit = e.currentTarget.dataset.targetUnit;
    const name = e.currentTarget.dataset.name;
    if (targetValue && targetValue > 0) {
      this.setData({
        checkinDialog: true,
        checkinTaskId: taskId,
        checkinTaskName: name || '',
        checkinTarget: targetValue,
        checkinUnit: targetUnit || '',
        checkinValue: '',
      });
      return;
    }
    this.doTaskCheckin(taskId, null);
  },

  onCheckinDialogInput(e) {
    this.setData({ checkinValue: e.detail.value });
  },

  onCheckinDialogCancel() {
    this.setData({ checkinDialog: false });
  },

  onCheckinDialogConfirm() {
    const val = this.data.checkinValue ? parseFloat(this.data.checkinValue) : null;
    this.setData({ checkinDialog: false });
    this.doTaskCheckin(this.data.checkinTaskId, val);
  },

  async doTaskCheckin(taskId, value) {
    const body = {};
    if (value != null) body.actual_value = value;
    try {
      await post(`/api/health-plan/user-plans/${this.data.id}/tasks/${taskId}/checkin`, body);
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadDetail(this.data.id);
    } catch (e) {
      // error handled by request
    }
  }
});
