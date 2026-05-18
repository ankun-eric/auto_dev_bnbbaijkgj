/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 守护详情/AI 外呼配置（小程序）
 */
const { get, put, post, del } = require('../../utils/request');

Page({
  data: {
    targetUserId: 0,
    isSelf: false,
    setting: null,
    devices: [],
    deviceLoading: false,
  },

  onLoad(options) {
    const target = Number(options.target || 0);
    const isSelf = options.self === '1';
    this.setData({ targetUserId: target, isSelf });
    this.fetchSetting();
    if (!isSelf && target > 0) {
      this.fetchDevices();
    }
  },

  async fetchSetting() {
    try {
      const url = `/api/health-archive/ai-call/settings/${this.data.targetUserId}`;
      const res = await get(url, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({ setting: data });
    } catch (_) {
      wx.showToast({ icon: 'none', title: '加载失败' });
    }
  },

  async fetchDevices() {
    this.setData({ deviceLoading: true });
    try {
      const url = `/api/health-archive/guardian/${this.data.targetUserId}/devices`;
      const res = await get(url, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const devices = Array.isArray(data.items) ? data.items : [];
      this.setData({ devices, deviceLoading: false });
    } catch (_) {
      this.setData({ devices: [], deviceLoading: false });
    }
  },

  async updateSetting(patch) {
    try {
      const url = `/api/health-archive/ai-call/settings/${this.data.targetUserId}`;
      const res = await put(url, patch, { showLoading: false });
      const data = (res && (res.data || res)) || {};
      this.setData({ setting: data });
      wx.showToast({ icon: 'success', title: '已保存', duration: 800 });
    } catch (e) {
      wx.showToast({ icon: 'none', title: '保存失败' });
    }
  },

  onToggleEnabled(e) {
    this.updateSetting({ enabled: e.detail.value });
  },

  onChangeDndStart(e) {
    this.updateSetting({ dnd_start: e.detail.value });
  },

  onChangeDndEnd(e) {
    this.updateSetting({ dnd_end: e.detail.value });
  },

  onChangeCallTarget(e) {
    const v = e.currentTarget.dataset.value;
    this.updateSetting({ call_target: v });
  },

  async onRemindBind() {
    try {
      const url = `/api/health-archive/guardian/${this.data.targetUserId}/devices/remind-bind`;
      await post(url, {}, { showLoading: false });
      wx.showToast({ icon: 'success', title: '已提醒 TA' });
    } catch (_) {
      wx.showToast({ icon: 'none', title: '提醒失败' });
    }
  },

  onCancelManagement() {
    wx.showModal({
      title: '解除守护',
      content: '解除后将不再接收 TA 的健康提醒，确认解除吗？',
      confirmColor: '#ef4444',
      success: async (r) => {
        if (!r.confirm) return;
        try {
          await del(`/api/family/co-managed/${this.data.targetUserId}`, {}, { showLoading: false });
          wx.showToast({ icon: 'success', title: '已解除' });
          setTimeout(() => wx.navigateBack(), 800);
        } catch (e) {
          wx.showToast({ icon: 'none', title: '解除失败' });
        }
      },
    });
  },
});
