// [PRD-BP-AI-EXPLAIN-V1 2026-05-31] 小程序血压（及其它指标）详情页 = web-view 加载 H5 详情页
// 配套实现：
//   1) 「全部」按钮跳转修复（H5 端已改为 router.push，整个 web-view 内即时跳转，无需再开新页）
//   2) 血压 AI 解读两个按钮 + 抽屉（H5 端已新增，小程序 web-view 内自动同步生效）
// 与小程序「会员中心」web-view 包装方案一致。
Page({
  data: {
    webUrl: ''
  },

  onLoad(query) {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = wx.getStorageSync('token') || '';
    const type = (query && query.type) || 'blood_pressure';
    const profileId = (query && query.profileId) || '';
    const params = [];
    if (profileId) params.push(`profileId=${encodeURIComponent(profileId)}`);
    if (token) params.push(`token=${encodeURIComponent(token)}`);
    const qs = params.length ? `?${params.join('&')}` : '';
    const webUrl = `${base}/health-metric/${type}${qs}`;
    this.setData({ webUrl });
  }
});
