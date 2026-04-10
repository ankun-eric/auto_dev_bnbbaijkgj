const { post } = require('../../../utils/request');

Page({
  data: {
    name: '',
    description: '',
    tasks: [{ name: '', description: '' }],
    submitting: false
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  onTaskInput(e) {
    const { idx, field } = e.currentTarget.dataset;
    this.setData({ [`tasks[${idx}].${field}`]: e.detail.value });
  },

  addTask() {
    const tasks = this.data.tasks.concat({ name: '', description: '' });
    this.setData({ tasks });
  },

  removeTask(e) {
    const idx = e.currentTarget.dataset.idx;
    if (this.data.tasks.length <= 1) {
      wx.showToast({ title: '至少保留一个任务', icon: 'none' });
      return;
    }
    const tasks = this.data.tasks.filter((_, i) => i !== idx);
    this.setData({ tasks });
  },

  async onSubmit() {
    const { name, description, tasks } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入计划名称', icon: 'none' });
      return;
    }
    const validTasks = tasks.filter(t => t.name.trim());
    if (validTasks.length === 0) {
      wx.showToast({ title: '请至少添加一个任务', icon: 'none' });
      return;
    }

    const payload = {
      plan_name: name.trim(),
      description: description.trim(),
      tasks: validTasks.map((t, idx) => ({
        task_name: t.name.trim(),
        sort_order: idx,
      }))
    };

    this.setData({ submitting: true });
    try {
      await post('/api/health-plan/user-plans', payload);
      wx.showToast({ title: '创建成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 1500);
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ submitting: false });
    }
  }
});
