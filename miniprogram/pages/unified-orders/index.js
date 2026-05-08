const { get, post } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '全部', status: '' },
      { label: '待付款', status: 'pending_payment' },
      { label: '待收货', status: 'pending_receipt' },
      { label: '待核销', status: 'pending_use' },
      { label: '已完成', status: 'completed' },
      { label: '待评价', status: 'pending_review' },
      { label: '已取消', status: 'cancelled' }
    ],
    orders: [],
    page: 1,
    pageSize: 10,
    total: 0,
    loading: false,
    noMore: false
  },

  onLoad(options) {
    if (options.status) {
      const idx = this.data.tabs.findIndex(t => t.status === options.status);
      if (idx >= 0) this.setData({ currentTab: idx });
    }
    this.loadOrders();
  },

  onShow() {
    // [BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v1.0]
    // 顾客在订单详情页改约/预约成功后会写 globalData.unifiedOrdersNeedRefresh，
    // 列表页 onShow 时检测并强制刷新，确保返回列表看到的就是最新预约时间。
    let needRefresh = !!this._needRefresh;
    try {
      const app = getApp();
      if (app && app.globalData && app.globalData.unifiedOrdersNeedRefresh) {
        app.globalData.unifiedOrdersNeedRefresh = false;
        needRefresh = true;
      }
    } catch (_) {
      /* 兜底忽略 */
    }
    if (needRefresh) {
      this._needRefresh = false;
      this.resetList();
      this.loadOrders();
    }
  },

  onPullDownRefresh() {
    this.resetList();
    this.loadOrders().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (!this.data.noMore && !this.data.loading) {
      this.loadOrders();
    }
  },

  switchTab(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentTab: idx });
    this.resetList();
    this.loadOrders();
  },

  resetList() {
    this.setData({ orders: [], page: 1, noMore: false, total: 0 });
  },

  async loadOrders() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    const status = this.data.tabs[this.data.currentTab].status;
    const params = {
      page: this.data.page,
      page_size: this.data.pageSize
    };
    if (status) params.status = status;

    try {
      const res = await get('/api/orders/unified', params, { showLoading: false });
      const list = res.items || [];
      const newOrders = this.data.orders.concat(list);
      this.setData({
        orders: newOrders,
        total: res.total || 0,
        page: this.data.page + 1,
        noMore: newOrders.length >= (res.total || 0) || list.length < this.data.pageSize
      });
    } catch (e) {
      console.log('loadOrders error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    this._needRefresh = true;
    wx.navigateTo({ url: `/pages/unified-order-detail/index?id=${id}` });
  },

  async payOrder(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await post(`/api/orders/unified/${id}/pay`);
      const data = res.data || res;
      if (data.payment_params) {
        wx.requestPayment({
          ...data.payment_params,
          success: () => {
            wx.showToast({ title: '支付成功', icon: 'success' });
            this.resetList();
            this.loadOrders();
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

  cancelOrder(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '取消订单',
      content: '确定要取消此订单吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/orders/unified/${id}/cancel`);
          wx.showToast({ title: '已取消', icon: 'success' });
          this.resetList();
          this.loadOrders();
        } catch (e) {
          console.log('cancelOrder error', e);
        }
      }
    });
  },

  confirmOrder(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认收货',
      content: '确认已收到商品/服务？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/orders/unified/${id}/confirm`);
          wx.showToast({ title: '已确认', icon: 'success' });
          this.resetList();
          this.loadOrders();
        } catch (e) {
          console.log('confirmOrder error', e);
        }
      }
    });
  },

  // [核销订单过期+改期规则优化 v1.0]「改约」按钮 — 已达上限置灰
  onReschedule(e) {
    const order = e.currentTarget.dataset.order || {};
    const count = Number(order.reschedule_count || 0);
    const limit = Number(order.reschedule_limit || 3);
    if (count >= limit) {
      wx.showToast({ title: '本订单已达改期上限', icon: 'none' });
      return;
    }
    this._needRefresh = true;
    wx.navigateTo({
      url: `/pages/unified-order-detail/index?id=${order.id}&action=appointment`,
    });
  },

  // [核销订单过期+改期规则优化 v1.0]「联系商家」按钮 — 弹底部 ActionSheet
  async onContactStore(e) {
    const order = e.currentTarget.dataset.order || {};
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
        } else if (address && phone && res.tapIndex === 1) {
          if (info && info.lat && info.lng) {
            wx.openLocation({
              latitude: Number(info.lat),
              longitude: Number(info.lng),
              name,
              address,
            });
          }
        } else if (address && !phone && res.tapIndex === 0) {
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

  goRefund(e) {
    const id = e.currentTarget.dataset.id;
    this._needRefresh = true;
    wx.navigateTo({ url: `/pages/refund/index?orderId=${id}` });
  },

  // [BUG-FIX-REBUY-V1 2026-05-07]「再来一单」：调后端 reorder 校验商品状态后跳 checkout
  async onRebuy(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await post(`/api/orders/unified/${id}/reorder`, {}, { showLoading: true });
      const data = (res && res.data) ? res.data : res;
      const status = data && data.status;
      const items = (data && data.available_items) || [];
      if (status === 'all_unavailable' || items.length === 0) {
        wx.showToast({
          title: (data && data.message) || '商品已全部下架，无法再来一单',
          icon: 'none', duration: 2500,
        });
        return;
      }
      if (status === 'partial_filtered') {
        wx.showToast({
          title: (data && data.message) || '部分商品已下架，已为您过滤',
          icon: 'none', duration: 2500,
        });
      }
      const first = items[0];
      const parts = [`product_id=${first.product_id}`, 'from_rebuy=1'];
      if (first.sku_id) parts.push(`sku_id=${first.sku_id}`);
      if (first.quantity) parts.push(`quantity=${first.quantity}`);
      this._needRefresh = true;
      wx.navigateTo({ url: `/pages/checkout/index?${parts.join('&')}` });
    } catch (err) {
      console.log('onRebuy error', err);
      const code = err && (err.statusCode || err.status || (err.data && err.data.code));
      if (code === 401 || code === 403) {
        wx.showToast({ title: '请先登录', icon: 'none' });
        return;
      }
      wx.showToast({ title: '网络异常，请稍后重试', icon: 'none' });
    }
  },

  getStatusText(status) {
    const map = {
      pending_payment: '待付款',
      pending_shipment: '待发货',
      pending_receipt: '待收货',
      pending_appointment: '待预约',
      appointed: '待核销',
      pending_use: '待核销',
      partial_used: '部分核销',
      pending_review: '待评价',
      completed: '已完成',
      expired: '已过期',
      refunding: '退款中',
      refunded: '已退款',
      cancelled: '已取消'
    };
    return map[status] || status;
  }
});
