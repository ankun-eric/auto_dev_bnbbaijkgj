const { get, post, put } = require('../../../utils/request');

Page({
  data: {
    isEdit: false,
    id: '',
    name: '',
    description: '',
    target: '',
    icon: '',
    submitting: false
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ isEdit: true, id: options.id });
      wx.setNavigationBarTitle({ title: '编辑打卡项目' });
      this.loadDetail(options.id);
    } else {
      wx.setNavigationBarTitle({ title: '创建打卡项目' });
    }
  },

  async loadDetail(id) {
    try {
      const res = await get(`/api/health-plan/checkin-items/${id}`, {}, { showLoading: true });
      if (!res) return;
      this.setData({
        name: res.name || '',
        description: res.description || '',
        target: res.target || '',
        icon: res.icon || ''
      });
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  async onSubmit() {
    const { name, description, target, icon } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入名称', icon: 'none' });
      return;
    }

    const payload = {
      name: name.trim(),
      target_value: target.trim() ? parseFloat(target.trim()) : null,
      target_unit: null,
    };

    this.setData({ submitting: true });
    try {
      if (this.data.isEdit) {
        await put(`/api/health-plan/checkin-items/${this.data.id}`, payload);
      } else {
        await post('/api/health-plan/checkin-items', payload);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 1500);
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ submitting: false });
    }
  }
});
