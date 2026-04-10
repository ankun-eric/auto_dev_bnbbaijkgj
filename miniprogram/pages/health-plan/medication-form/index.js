const { get, post, put } = require('../../../utils/request');

const PERIOD_LABELS = ['早晨', '中午', '晚上', '睡前'];
const PERIOD_VALUES = ['morning', 'noon', 'evening', 'bedtime'];

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
    dosage: '',
    timePeriodIndex: 0,
    periodLabels: PERIOD_LABELS,
    periodValues: PERIOD_VALUES,
    remindTime: '',
    notes: '',
    submitting: false
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ isEdit: true, id: options.id });
      wx.setNavigationBarTitle({ title: '编辑用药提醒' });
      this.loadDetail(options.id);
    } else {
      wx.setNavigationBarTitle({ title: '添加用药提醒' });
    }
  },

  async loadDetail(id) {
    try {
      const res = await get(`/api/health-plan/medications/${id}`, {}, { showLoading: true });
      if (!res) return;
      const d = unwrapRes(res);
      const tp = d.time_period || '';
      let idx = PERIOD_VALUES.indexOf(tp);
      if (idx < 0) idx = 0;
      this.setData({
        name: d.medicine_name || '',
        dosage: d.dosage || '',
        remindTime: d.remind_time || '',
        notes: d.notes || '',
        timePeriodIndex: idx
      });
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  onTimePeriodChange(e) {
    const idx = Number(e.detail.value);
    this.setData({ timePeriodIndex: idx });
  },

  onRemindTimeChange(e) {
    this.setData({ remindTime: e.detail.value });
  },

  async onSubmit() {
    const { name, dosage, notes, remindTime, timePeriodIndex } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入药品名称', icon: 'none' });
      return;
    }
    const time_period = PERIOD_VALUES[timePeriodIndex];
    const payload = {
      medicine_name: name.trim(),
      dosage: dosage.trim(),
      time_period: time_period || PERIOD_VALUES[0],
      remind_time: (remindTime || '').trim(),
      notes: notes.trim()
    };

    this.setData({ submitting: true });
    try {
      let result;
      if (this.data.isEdit) {
        result = await put(`/api/health-plan/medications/${this.data.id}`, payload);
      } else {
        result = await post('/api/health-plan/medications', payload);
        this.requestSubscribeMessage(result && result.id);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 1500);
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ submitting: false });
    }
  },

  requestSubscribeMessage(reminderId) {
    const tmplIds = getApp().globalData.subscribeTemplateIds;
    if (!tmplIds || tmplIds.length === 0) return;
    wx.requestSubscribeMessage({
      tmplIds: tmplIds,
      success: (res) => {
        const accepted = [];
        tmplIds.forEach(function(id) {
          if (res[id] === 'accept') accepted.push(id);
        });
        if (accepted.length > 0 && reminderId) {
          post('/api/health-plan/medications/' + reminderId + '/subscribe', {
            template_ids: accepted,
          }, { showLoading: false, suppressErrorToast: true }).catch(function() {});
        }
      },
      fail: function() {}
    });
  }
});
