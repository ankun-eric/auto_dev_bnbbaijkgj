const { get, post, put } = require('../../../utils/request');

Page({
  data: {
    isEdit: false,
    id: '',
    name: '',
    dosage: '',
    frequency: '',
    remind_times: '',
    notes: '',
    start_date: '',
    end_date: '',
    frequencyOptions: ['每天', '每周', '每两天', '每三天', '按需'],
    frequencyIndex: 0,
    submitting: false
  },

  onLoad(options) {
    const today = this.formatDate(new Date());
    this.setData({ start_date: today });
    if (options.id) {
      this.setData({ isEdit: true, id: options.id });
      wx.setNavigationBarTitle({ title: '编辑用药提醒' });
      this.loadDetail(options.id);
    } else {
      wx.setNavigationBarTitle({ title: '添加用药提醒' });
    }
  },

  formatDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  },

  async loadDetail(id) {
    try {
      const res = await get(`/api/health-plan/medications/${id}`, {}, { showLoading: true });
      if (!res) return;
      const freqIdx = this.data.frequencyOptions.indexOf(res.frequency);
      this.setData({
        name: res.medicine_name || res.name || '',
        dosage: res.dosage || '',
        frequency: res.frequency || '',
        remind_times: res.remind_time || res.remind_times || '',
        notes: res.notes || '',
        start_date: res.start_date || '',
        end_date: res.end_date || '',
        frequencyIndex: freqIdx >= 0 ? freqIdx : 0
      });
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  onFrequencyChange(e) {
    const idx = e.detail.value;
    this.setData({
      frequencyIndex: idx,
      frequency: this.data.frequencyOptions[idx]
    });
  },

  onStartDateChange(e) {
    this.setData({ start_date: e.detail.value });
  },

  onEndDateChange(e) {
    this.setData({ end_date: e.detail.value });
  },

  async onSubmit() {
    const { name, dosage, frequency, remind_times, notes, start_date, end_date } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入药品名称', icon: 'none' });
      return;
    }
    const payload = {
      medicine_name: name.trim(),
      dosage: dosage.trim(),
      time_period: frequency || this.data.frequencyOptions[this.data.frequencyIndex],
      remind_time: remind_times.trim(),
      notes: notes.trim(),
    };

    this.setData({ submitting: true });
    try {
      if (this.data.isEdit) {
        await put(`/api/health-plan/medications/${this.data.id}`, payload);
      } else {
        await post('/api/health-plan/medications', payload);
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
