// [卡管理 v2.0 第 5 期] 小程序卡包页（极简版）
const request = require('../../../utils/request');

Page({
  data: {
    cards: [],
    loading: true,
  },
  onLoad() {
    this.fetchWallet();
  },
  fetchWallet() {
    const that = this;
    request({ url: '/api/cards/me/wallet', method: 'GET' })
      .then((res) => {
        that.setData({ cards: (res && res.items) || [], loading: false });
      })
      .catch(() => that.setData({ loading: false }));
  },
  goRedeem(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/cards/redeem-code/index?id=${id}` });
  },
  goRenew(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/cards/renew/index?id=${id}` });
  },
});
