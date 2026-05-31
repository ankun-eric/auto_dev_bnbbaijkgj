// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式「用药提醒」= web-view 加载 H5 用药提醒页
// 需求4：直接进入本人独立的「用药提醒」页面（health-plan/medications，即 H5 /ai-home/medication-reminder）
// 不带 consultant_id → 全量查询本人在用药品，与「用药提醒-全部」一致，不再跳健康档案锚点
Page({
  data: { webUrl: '' },
  onLoad() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = wx.getStorageSync('token') || '';
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    this.setData({ webUrl: `${base}/ai-home/medication-reminder${qs}` });
  },
});
