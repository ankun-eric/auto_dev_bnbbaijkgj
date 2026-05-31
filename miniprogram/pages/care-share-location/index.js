// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式「分享我的位置」中转 + 查看页
// - 由 SOS 页（H5 web-view）生成静态位置 token 后跳转进来
// - 本页启用 onShareAppMessage：点右上角「…」或自动弹出转发 → 微信发给好友
// - 好友点开后进入本页 → web-view 加载 H5 查看页（地图 + 精简信息卡）
Page({
  data: { webUrl: '', token: '', address: '我的位置' },
  onLoad(options) {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = (options && options.token) || '';
    const address = (options && options.address) ? decodeURIComponent(options.address) : '我的位置';
    const tkn = wx.getStorageSync('token') || '';
    const qs = tkn ? `?token=${encodeURIComponent(tkn)}` : '';
    this.setData({
      token,
      address,
      webUrl: token ? `${base}/care-ai-home/share-location/${token}${qs}` : '',
    });
    // 开启转发能力
    wx.showShareMenu({ withShareTicket: true, menus: ['shareAppMessage', 'shareTimeline'] });
  },

  // 微信发给好友：转发卡片指向本页（带 token），好友打开即看到地图 + 精简信息卡
  onShareAppMessage() {
    const { token, address } = this.data;
    return {
      title: `我分享了我的位置：${address}`,
      path: `/pages/care-share-location/index?token=${encodeURIComponent(token)}&address=${encodeURIComponent(address)}`,
    };
  },

  onShareTimeline() {
    const { token, address } = this.data;
    return {
      title: `我的位置：${address}`,
      query: `token=${encodeURIComponent(token)}&address=${encodeURIComponent(address)}`,
    };
  },
});
