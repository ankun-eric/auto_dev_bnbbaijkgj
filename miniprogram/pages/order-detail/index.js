const { get } = require('../../utils/request');

Page({
  data: {
    order: {
      id: '1',
      orderNo: '2026032700001',
      name: '在线图文问诊',
      price: '29.00',
      time: '2026-03-27 10:30',
      status: 'paid',
      statusText: '待使用',
      payMethod: '微信支付',
      verifyCode: '8826 3741'
    }
  },

  onLoad(options) {
    if (options.id) {
      this.loadOrder(options.id);
    }
  },

  async loadOrder(id) {
    try {
      // const res = await get(`/api/orders/${id}`);
      // this.setData({ order: res.data });
    } catch (e) {
      console.log('loadOrder error', e);
    }
  },

  payOrder() {
    wx.showToast({ title: '正在调起支付...', icon: 'none' });
  },

  cancelOrder() {
    wx.showModal({
      title: '取消订单',
      content: '确定要取消此订单吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '已取消', icon: 'success' });
          setTimeout(() => { wx.navigateBack(); }, 1500);
        }
      }
    });
  }
});
