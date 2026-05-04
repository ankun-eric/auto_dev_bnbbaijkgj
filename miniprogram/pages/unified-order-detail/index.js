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
    // [修改预约 Bug 修复 v1.0] 当前正在预约的商品的预约模式（none/date/time_slot/custom_form）
    // 用于弹窗中按模式联动隐藏整块时段（date 模式）/ 跳转自定义表单页（custom_form 模式）
    apptCurrentMode: 'time_slot',
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

  // [核销订单过期+改期规则优化 v1.0] 改约按钮：达到上限弹 Toast
  onRescheduleClick() {
    const order = this.data.order || {};
    const count = Number(order.reschedule_count || 0);
    const limit = Number(order.reschedule_limit || 3);
    if (count >= limit) {
      wx.showToast({ title: '本订单已达改期上限', icon: 'none' });
      return;
    }
    this.openApptModal();
  },

  // [核销订单过期+改期规则优化 v1.0] 联系商家：底部 ActionSheet
  async onContactStore() {
    const order = this.data.order || {};
    const storeId = order.store_id;
    if (!storeId) {
      wx.showToast({ title: '商家未提供联系方式', icon: 'none' });
      return;
    }
    let info = null;
    try {
      info = await get(`/api/stores/${storeId}/contact`, {}, { showLoading: false });
    } catch (err) {
      console.log('store contact error', err);
    }
    const name = (info && info.store_name) || order.store_name || '门店';
    const phone = info && info.contact_phone;
    const address = info && info.address;
    const items = [];
    if (phone) items.push(`拨打 ${phone}`);
    if (address) items.push(`查看地址：${address}`);
    items.push('如有疑问可联系商家协商处理');
    if (items.length === 0) {
      wx.showToast({ title: '商家未提供联系方式', icon: 'none' });
      return;
    }
    wx.showActionSheet({
      itemList: items,
      success: (res) => {
        if (phone && res.tapIndex === 0) {
          wx.makePhoneCall({ phoneNumber: phone, fail: () => {} });
        } else if (phone && address && res.tapIndex === 1) {
          if (info && info.lat && info.lng) {
            wx.openLocation({
              latitude: Number(info.lat),
              longitude: Number(info.lng),
              name,
              address,
            });
          }
        } else if (!phone && address && res.tapIndex === 0) {
          if (info && info.lat && info.lng) {
            wx.openLocation({
              latitude: Number(info.lat),
              longitude: Number(info.lng),
              name,
              address,
            });
          }
        }
      },
    });
  },

  // [先下单后预约 Bug 修复 v1.0] [订单状态机简化方案 v1.0]
  // [修改预约 Bug 修复 v1.0] 增加 partial_used 状态、按 appointment_mode 联动
  // 同时打印日志便于现场排查（按需求文档要求）
  openApptModal() {
    console.log('[appt] openApptModal called, order=', this.data.order);
    const order = this.data.order;
    if (!order) return;
    if (['pending_appointment', 'pending_use', 'appointed', 'partial_used'].indexOf(order.status) < 0) {
      wx.showToast({ title: '当前订单状态不可预约', icon: 'none' });
      return;
    }
    const items = order.items || [];
    // 优先选择需要预约（appointment_mode != none）且是 in_store 的 item
    const apptItem =
      items.find(i => i.fulfillment_type === 'in_store' && i.appointment_mode && i.appointment_mode !== 'none') ||
      items.find(i => i.fulfillment_type === 'in_store') ||
      items[0];
    if (!apptItem) {
      wx.showToast({ title: '订单暂无可预约商品', icon: 'none' });
      return;
    }
    const mode = apptItem.appointment_mode || 'time_slot';
    // [修改预约 Bug 修复 v1.0] custom_form 模式：跳转到自定义表单页面，不打开普通弹窗
    if (mode === 'custom_form') {
      wx.navigateTo({
        url: `/pages/custom-appointment/index?orderId=${order.id}&itemId=${apptItem.id}&mode=edit`,
        fail: () => {
          wx.showToast({ title: '请前往商品详情填写预约表单', icon: 'none' });
        }
      });
      return;
    }
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    const max = new Date(today);
    max.setDate(today.getDate() + 90);
    const fmt = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    // 已存在预约时间则回填
    let initialDate = fmt(tomorrow);
    if (apptItem.appointment_time) {
      try {
        initialDate = fmt(new Date(apptItem.appointment_time));
      } catch (e) { /* 保持默认明天 */ }
    }
    let initialSlot = '';
    if (apptItem.appointment_data && apptItem.appointment_data.time_slot) {
      initialSlot = apptItem.appointment_data.time_slot;
    }
    this.setData({
      showApptModal: true,
      apptItemId: apptItem.id,
      apptCurrentMode: mode,
      apptDate: initialDate,
      apptSlot: initialSlot,
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
    if (!this.data.apptItemId) {
      wx.showToast({ title: '订单异常', icon: 'none' });
      return;
    }
    // [修改预约 Bug 修复 v1.0] 仅 time_slot 模式才校验时段；date 模式不校验且不携带 time_slot
    const mode = this.data.apptCurrentMode || 'time_slot';
    if (mode === 'time_slot' && !this.data.apptSlot) {
      wx.showToast({ title: '请选择预约时段', icon: 'none' });
      return;
    }
    const startTime =
      mode === 'time_slot' && this.data.apptSlot
        ? this.data.apptSlot.split('-')[0]
        : '09:00';
    const appointmentData = { date: this.data.apptDate };
    if (mode === 'time_slot' && this.data.apptSlot) {
      appointmentData.time_slot = this.data.apptSlot;
    }
    try {
      await post(`/api/orders/unified/${this.data.id}/appointment`, {
        item_id: this.data.apptItemId,
        appointment_time: `${this.data.apptDate}T${startTime}:00`,
        appointment_data: appointmentData
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
    const order = this.data.order;
    if (!order) return;
    try {
      const methodsRes = await get('/api/pay/available-methods', { platform: 'miniprogram' }, { showLoading: false });
      const methods = Array.isArray(methodsRes) ? methodsRes : (Array.isArray(methodsRes && methodsRes.data) ? methodsRes.data : []);
      const channelCode = (methods[0] && methods[0].channel_code) || null;
      const paidAmount = Number(order.paid_amount) || 0;

      if (paidAmount === 0) {
        await post(`/api/orders/unified/${order.id}/confirm-free`, { channel_code: channelCode });
        wx.showToast({ title: '支付成功', icon: 'success' });
        this.loadOrder();
        return;
      }

      if (!channelCode) {
        wx.showToast({ title: '暂未开通支付方式', icon: 'none' });
        return;
      }

      const payRes = await post(`/api/orders/unified/${order.id}/pay`, { channel_code: channelCode });
      const paymentParams = payRes && payRes.payment_params;
      if (channelCode === 'wechat_miniprogram' && paymentParams) {
        wx.requestPayment({
          ...paymentParams,
          success: () => this.loadOrder(),
          fail: () => this.loadOrder(),
        });
      } else {
        this.loadOrder();
      }
    } catch (e) {
      wx.showToast({ title: (e && e.detail) || '支付失败', icon: 'none' });
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
