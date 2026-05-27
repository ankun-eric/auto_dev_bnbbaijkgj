// [PRD-AIHOME-CARE-V1 2026-05-27] 小程序首次进入版本选择页
const { put } = require('../../utils/request');

Page({
  data: { submitting: false },

  choose(e) {
    const mode = e.currentTarget.dataset.mode;
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    put('/api/care-v1/user-preferences/ui-mode', { ui_mode: mode, first_choice: true })
      .catch(() => {})
      .then(() => {
        try { wx.setStorageSync('ui_mode', mode); } catch (_) {}
        if (mode === 'care') {
          wx.redirectTo({ url: '/pages/care-home/index' });
        } else {
          wx.switchTab({ url: '/pages/home/index' });
        }
      });
  },

  skip() {
    try { wx.setStorageSync('ui_mode', 'standard'); } catch (_) {}
    wx.switchTab({ url: '/pages/home/index' });
  },
});
