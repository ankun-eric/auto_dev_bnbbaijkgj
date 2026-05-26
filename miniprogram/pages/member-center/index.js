// [Bug 修复 v1.0 §3.1.3] 小程序会员中心 = web-view 加载 H5 会员中心，token 透传
Page({
  data: {
    webUrl: ''
  },

  onLoad() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = wx.getStorageSync('token') || '';
    // H5 会员中心路由：{baseUrl}/member-center?token=xxx
    // 注意：base URL 已包含 https://newbb.test.bangbangvip.com/autodev/{deployId}
    // H5 路由约定通过 query string 携带 token 给前端首屏鉴权（已存在拦截器消费）
    const sep = base.includes('?') ? '&' : '?';
    const webUrl = `${base}/member-center${token ? `${sep}token=${encodeURIComponent(token)}` : ''}`;
    this.setData({ webUrl });
  }
});
