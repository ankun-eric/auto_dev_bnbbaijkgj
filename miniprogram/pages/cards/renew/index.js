const request = require('../../../utils/request');

Page({
  data: { userCardId: null, submitting: false },
  onLoad(options) {
    this.setData({ userCardId: Number(options && options.id) });
  },
  handleRenew() {
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    const that = this;
    request({
      url: `/api/cards/me/${this.data.userCardId}/renew`,
      method: 'POST',
      data: { payment_method: 'wechat' },
    })
      .then((res) => {
        wx.showToast({ title: '续卡订单已生成', icon: 'success' });
        wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${res.order_id}` });
      })
      .catch((err) => {
        wx.showToast({ title: (err && err.detail) || '续卡失败', icon: 'none' });
      })
      .finally(() => that.setData({ submitting: false }));
  },
});
