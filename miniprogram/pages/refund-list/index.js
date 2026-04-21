const { get } = require('../../utils/request.js');

const REFUND_STATUS_TEXT = {
  applied: '退款申请中',
  reviewing: '退款处理中',
  returning: '退款处理中',
  approved: '退款成功',
  refund_success: '退款成功',
  rejected: '退款被拒绝',
  none: ''
};

const REFUND_STATUS_COLOR = {
  applied: '#faad14',
  reviewing: '#1890ff',
  returning: '#1890ff',
  approved: '#52c41a',
  refund_success: '#52c41a',
  rejected: '#ff4d4f'
};

Page({
  data: {
    tabs: [
      { label: '全部', filter: 'all_refund' },
      { label: '申请中', filter: 'applied' },
      { label: '处理中', filter: 'reviewing,returning' },
      { label: '已退款', filter: 'refund_success,approved' },
      { label: '已拒绝', filter: 'rejected' }
    ],
    currentTab: 0,
    orders: [],
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    hasMore: true
  },

  onLoad() {
    this.loadOrders(true);
  },

  onShow() {
    if (this._needRefresh) {
      this._needRefresh = false;
      this.setData({ orders: [], page: 1, hasMore: true });
      this.loadOrders(true);
    }
  },

  switchTab(e) {
    const idx = Number(e.currentTarget.dataset.index);
    if (idx === this.data.currentTab) return;
    this.setData({ currentTab: idx, orders: [], page: 1, hasMore: true });
    this.loadOrders(true);
  },

  async loadOrders(reset = false) {
    if (this.data.loading) return;
    if (!reset && !this.data.hasMore) return;
    this.setData({ loading: true });
    try {
      const filter = this.data.tabs[this.data.currentTab].filter;
      const res = await get('/api/orders/unified', {
        page: this.data.page,
        page_size: this.data.pageSize,
        refund_status: filter
      }, { showLoading: false, suppressErrorToast: true });

      const items = (res.items || []).map(o => ({
        ...o,
        refund_status_text: REFUND_STATUS_TEXT[o.refund_status] || '',
        refund_status_color: REFUND_STATUS_COLOR[o.refund_status] || '#666',
        first_item: (o.items && o.items[0]) || {}
      }));

      this.setData({
        orders: reset ? items : this.data.orders.concat(items),
        total: res.total || 0,
        hasMore: items.length === this.data.pageSize,
        page: this.data.page + 1
      });
    } catch (e) {
      console.log('loadRefundOrders error', e);
      if (reset) {
        this.setData({ orders: [], hasMore: false });
      } else {
        this.setData({ hasMore: false });
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true });
    this.loadOrders(true).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (!this.data.loading && this.data.hasMore) {
      this.loadOrders(false);
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    this._needRefresh = true;
    wx.navigateTo({ url: `/pages/unified-order-detail/index?id=${id}` });
  }
});
