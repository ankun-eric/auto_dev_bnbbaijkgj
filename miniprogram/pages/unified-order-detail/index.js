const { get, post } = require('../../utils/request');

Page({
  data: {
    id: '',
    order: null,
    loading: true,
    showQrCode: false,
    // [先下单后预约 Bug 修复 v1.0] 立即预约弹窗
    showApptModal: false,
    apptDate: '',
    apptSlot: '',
    apptMinDate: '',
    apptMaxDate: '',
    apptItemId: null,
    apptSlotOptions: [
      '09:00-10:00', '10:00-11:00', '11:00-12:00',
      '13:00-14:00', '14:00-15:00', '15:00-16:00',
      '16:00-17:00', '17:00-18:00'
    ]
  },

  onLoad(options) {
    this.setData({ id: options.id });
    this.loadOrder();
  },

  // [先下单后预约 Bug 修复 v1.0]
  openApptModal() {
    const order = this.data.order;
    if (!order) return;
    const items = order.items || [];
    const inStoreItem = items.find(i => i.fulfillment_type === 'in_store') || items[0];
    if (!inStoreItem) {
      wx.showToast({ title: '订单暂无可预约商品', icon: 'none' });
      return;
    }
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    const max = new Date(today);
    max.setDate(today.getDate() + 90);
    const fmt = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    this.setData({
      showApptModal: true,
      apptItemId: inStoreItem.id,
      apptDate: fmt(tomorrow),
      apptSlot: '',
      apptMinDate: fmt(today),
      apptMaxDate: fmt(max)
    });
  },

  closeApptModal() {
    this.setData({ showApptModal: false });
  },

  onApptDateChange(e) {
    this.setData({ apptDate: e.detail.value });
  },

  onApptSlotTap(e) {
    this.setData({ apptSlot: e.currentTarget.dataset.slot });
  },

  async submitAppt() {
    if (!this.data.apptDate) {
      wx.showToast({ title: '请选择预约日期', icon: 'none' });
      return;
    }
    if (!this.data.apptSlot) {
      wx.showToast({ title: '请选择预约时段', icon: 'none' });
      return;
    }
    if (!this.data.apptItemId) {
      wx.showToast({ title: '订单异常', icon: 'none' });
      return;
    }
    const startTime = this.data.apptSlot.split('-')[0];
    try {
      await post(`/api/orders/unified/${this.data.id}/appointment`, {
        item_id: this.data.apptItemId,
        appointment_time: `${this.data.apptDate}T${startTime}:00`,
        appointment_data: {
          date: this.data.apptDate,
          time_slot: this.data.apptSlot
        }
      });
      wx.showToast({ title: '预约成功', icon: 'success' });
      this.setData({ showApptModal: false });
      this.loadOrder();
    } catch (e) {
      wx.showToast({ title: (e && e.detail) || '预约失败', icon: 'none' });
    }
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

  withdrawRefund() {
    var that = this;
    wx.showModal({
      title: '撤回退款',
      content: '确定要撤回退款申请吗？',
      success: function (res) {
        if (!res.confirm) return;
        post('/api/orders/unified/' + that.data.id + '/refund/withdraw').then(function () {
          wx.showToast({ title: '已撤回', icon: 'success' });
          that.loadOrder();
        }).catch(function (e) {
          wx.showToast({ title: (e && e.detail) || '撤回失败', icon: 'none' });
        });
      }
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
