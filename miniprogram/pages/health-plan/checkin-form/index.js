const { get, post, put } = require('../../../utils/request');

const FREQ_VALUES = ['daily', 'weekday', 'custom'];
const FREQ_LABELS = ['每天', '工作日', '自定义'];

function unwrapRes(res) {
  if (res == null || typeof res !== 'object') return {};
  const inner = res.data;
  if (inner !== undefined && inner !== null && typeof inner === 'object' && !Array.isArray(inner)) {
    return inner;
  }
  return res;
}

Page({
  data: {
    isEdit: false,
    id: '',
    name: '',
    remindTime: '',
    repeatFrequency: 'daily',
    repeatFrequencyIndex: 0,
    freqLabels: FREQ_LABELS,
    freqValues: FREQ_VALUES,
    customDays: [],
    weekdays: [
      { day: 1, label: '一' },
      { day: 2, label: '二' },
      { day: 3, label: '三' },
      { day: 4, label: '四' },
      { day: 5, label: '五' },
      { day: 6, label: '六' },
      { day: 0, label: '日' }
    ],
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
      const d = unwrapRes(res);
      const times = Array.isArray(d.remind_times) ? d.remind_times : [];
      const remindTime = times[0] || d.remind_time || '';
      const repeatFrequency = d.repeat_frequency || d.frequency || 'daily';
      const idx = FREQ_VALUES.indexOf(repeatFrequency);
      const customDays = Array.isArray(d.custom_days) ? d.custom_days : [];
      this.setData({
        name: d.name || '',
        remindTime,
        repeatFrequency,
        repeatFrequencyIndex: idx >= 0 ? idx : 0,
        customDays
      });
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  onRemindTimeChange(e) {
    this.setData({ remindTime: e.detail.value });
  },

  onRepeatFrequencyChange(e) {
    const idx = Number(e.detail.value);
    const repeatFrequency = FREQ_VALUES[idx] || 'daily';
    this.setData({ repeatFrequencyIndex: idx, repeatFrequency });
  },

  onToggleWeekday(e) {
    const day = Number(e.currentTarget.dataset.day);
    let customDays = (this.data.customDays || []).slice();
    const pos = customDays.indexOf(day);
    if (pos >= 0) customDays.splice(pos, 1);
    else customDays.push(day);
    const order = (x) => (x === 0 ? 7 : x);
    customDays.sort((a, b) => order(a) - order(b));
    this.setData({ customDays });
  },

  async onSubmit() {
    const { name, remindTime, repeatFrequency, customDays } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入名称', icon: 'none' });
      return;
    }
    if (!remindTime) {
      wx.showToast({ title: '请选择提醒时间', icon: 'none' });
      return;
    }
    if (repeatFrequency === 'custom' && (!customDays || customDays.length === 0)) {
      wx.showToast({ title: '请选择重复日期', icon: 'none' });
      return;
    }

    const payload = {
      name: name.trim(),
      target_value: null,
      target_unit: null,
      remind_times: remindTime ? [remindTime] : null,
      repeat_frequency: repeatFrequency,
      custom_days: repeatFrequency === 'custom' ? customDays : null
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
