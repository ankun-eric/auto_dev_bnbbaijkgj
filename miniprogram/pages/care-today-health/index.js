// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式「今日健康数据」= web-view 加载 H5 页面
Page({
  data: { webUrl: '' },
  onLoad() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = wx.getStorageSync('token') || '';
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    this.setData({ webUrl: `${base}/care-ai-home/today-health${qs}` });
  },
});
