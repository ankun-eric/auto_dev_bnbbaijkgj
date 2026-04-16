const { get, post } = require('../../utils/request');

Page({
  data: {
    id: '',
    order: null,
    loading: true,
    showQrCode: false
  },

  onLoad(options) {
    this.setData({ id: options.id });
    this.loadOrder();
  },

  async loadOrder() {
    try {
      const res = await get(`/api/orders/unified/${this.data.id}`);
      const order = res.data || res;
      this.setData({ order, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      console.log('loadOrder error', e);
    }
  },

  async payOrder() {
    try {
      const res = await post(`/api/orders/unified/${this.data.id}/pay`);
      const data = res.data || res;
      if (data.payment_params) {
        wx.requestPayment({
          ...data.payment_params,
          success: () => {
            wx.showToast({ title: '支付成功', icon: 'success' });
            this.loadOrder();
          },
          fail: () => {
            wx.showToast({ title: '支付取消', icon: 'none' });
          }
        });
      }
    } catch (e) {
      console.log('payOrder error', e);
    }
  },

  cancelOrder() {
    wx.showModal({
      title: '取消订单',
      content: '确定要取消此订单吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/orders/unified/${this.data.id}/cancel`);
          wx.showToast({ title: '已取消', icon: 'success' });
          this.loadOrder();
        } catch (e) {
          console.log('cancelOrder error', e);
        }
      }
    });
  },

  confirmOrder() {
    wx.showModal({
      title: '确认收货',
      content: '确认已收到商品/服务？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/orders/unified/${this.data.id}/confirm`);
          wx.showToast({ title: '已确认', icon: 'success' });
          this.loadOrder();
        } catch (e) {
          console.log('confirmOrder error', e);
        }
      }
    });
  },

  goReview() {
    wx.navigateTo({
      url: `/pages/review/index?order_id=${this.data.id}`
    });
  },

  goRefund() {
    wx.navigateTo({
      url: `/pages/refund/index?order_id=${this.data.id}`
    });
  },

  toggleQrCode() {
    this.setData({ showQrCode: !this.data.showQrCode });
  },

  copyOrderNo() {
    if (!this.data.order) return;
    wx.setClipboardData({
      data: this.data.order.order_no,
      success() {
        wx.showToast({ title: '已复制', icon: 'success' });
      }
    });
  },

  copyVerifyCode() {
    if (!this.data.order || !this.data.order.verify_code) return;
    wx.setClipboardData({
      data: this.data.order.verify_code,
      success() {
        wx.showToast({ title: '已复制', icon: 'success' });
      }
    });
  },

  previewQrCode() {
    if (!this.data.order || !this.data.order.qr_code_url) return;
    wx.previewImage({
      urls: [this.data.order.qr_code_url]
    });
  },

  callStore() {
    const phone = this.data.order && this.data.order.store_phone;
    if (!phone) return;
    wx.makePhoneCall({ phoneNumber: phone });
  }
});
