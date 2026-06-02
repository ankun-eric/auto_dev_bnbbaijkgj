// [PRD-SAFETY-ROPE-V1 2026-06-03] 小程序「数字安全绳」中转页：复用 H5 /care-safety-rope
Page({
  data: { webUrl: '' },
  onLoad() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const tkn = wx.getStorageSync('token') || '';
    const qs = tkn ? `?token=${encodeURIComponent(tkn)}` : '';
    this.setData({
      webUrl: base ? `${base}/care-safety-rope${qs}` : '',
    });
  },
});
