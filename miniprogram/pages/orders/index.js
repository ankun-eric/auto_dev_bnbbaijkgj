const { get, post } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '全部', status: '' },
      { label: '待付款', status: 'pending' },
      { label: '待使用', status: 'paid' },
      { label: '已完成', status: 'used' },
      { label: '退款', status: 'refund' }
    ],
    orders: [
      { id: '1', orderNo: '2026032700001', name: '在线图文问诊', icon: '💬', price: '29.00', time: '2026-03-27 10:30', status: 'paid', statusText: '待使用', statusClass: 'status-paid' },
      { id: '2', orderNo: '2026032600002', name: '体检报告解读', icon: '📋', price: '49.00', time: '2026-03-26 15:20', status: 'used', statusText: '已完成', statusClass: 'status-used' },
      { id: '3', orderNo: '2026032500003', name: '中医体质辨识', icon: '🌿', price: '19.00', time: '2026-03-25 09:45', status: 'pending', statusText: '待付款', statusClass: 'status-pending' }
    ]
  },

  onLoad(options) {
    if (options.status) {
      const idx = this.data.tabs.findIndex(t => t.status === options.status);
      if (idx >= 0) this.setData({ currentTab: idx });
    }
    this.loadOrders();
  },

  switchTab(e) {
    this.setData({ currentTab: e.currentTarget.dataset.index });
    this.loadOrders();
  },

  async loadOrders() {
    try {
      // const status = this.data.tabs[this.data.currentTab].status;
      // const res = await get('/api/orders', { status });
      // this.setData({ orders: res.data });
    } catch (e) {
      console.log('loadOrders error', e);
    }
  },

  goOrderDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/order-detail/index?id=${id}` });
  },

  payOrder(e) {
    wx.showToast({ title: '正在调起支付...', icon: 'none' });
  },

  useOrder(e) {
    wx.showToast({ title: '正在跳转...', icon: 'none' });
  },

  cancelOrder(e) {
    wx.showModal({
      title: '取消订单',
      content: '确定要取消此订单吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '已取消', icon: 'success' });
        }
      }
    });
  }
});
