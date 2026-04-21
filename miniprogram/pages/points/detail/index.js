const { get } = require('../../../utils/request');

const TYPE_LABEL = {
  signin: '每日签到',
  checkin: '健康打卡',
  completeProfile: '完善档案',
  invite: '邀请奖励',
  firstOrder: '首次下单',
  reviewService: '订单评价',
  exchange: '积分兑换',
  consume: '积分消费',
  redeem: '积分兑换',
  task: '任务奖励',
  purchase: '购物奖励',
};

const TYPE_META = {
  coupon: { text: '优惠券', color: '#fa8c16', icon: '🎫' },
  service: { text: '体验服务', color: '#13c2c2', icon: '💆' },
  physical: { text: '实物', color: '#722ed1', icon: '📦' },
  virtual: { text: '虚拟', color: '#bfbfbf', icon: '🎁' },
  third_party: { text: '第三方', color: '#bfbfbf', icon: '🛍️' },
};

const STATUS_META = {
  success: { text: '兑换成功', color: '#52c41a' },
  pending: { text: '处理中', color: '#1890ff' },
  failed: { text: '失败', color: '#ff4d4f' },
  used: { text: '已使用', color: '#8c8c8c' },
  expired: { text: '已过期', color: '#bfbfbf' },
  cancelled: { text: '已取消', color: '#bfbfbf' },
};

function fmt(dt) {
  if (!dt) return '';
  try {
    const d = new Date(dt);
    const pad = (n) => (n < 10 ? '0' + n : String(n));
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch (e) {
    return String(dt);
  }
}

Page({
  data: {
    activeTab: 'detail',

    records: [],
    recordPage: 1,
    noMoreRecords: false,

    exchanges: [],
    exchangePage: 1,
    exchangeHasMore: true,
    exchangeLoading: true,
  },

  onLoad(options) {
    // PRD F3：支持 ?tab=exchange 直接激活兑换记录
    const initial = options && options.tab === 'exchange' ? 'exchange' : 'detail';
    this.setData({ activeTab: initial });
    if (initial === 'detail') this.loadRecords(true);
    else this.loadExchanges(1, true);
  },

  onShow() {
    // 重新进入时静默刷新当前 Tab
    if (this.data.activeTab === 'detail' && this.data.records.length === 0) this.loadRecords(true);
    if (this.data.activeTab === 'exchange' && this.data.exchanges.length === 0) this.loadExchanges(1, true);
  },

  onPullDownRefresh() {
    const p = this.data.activeTab === 'detail'
      ? this.loadRecords(true)
      : this.loadExchanges(1, true);
    Promise.resolve(p).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.activeTab === 'detail' && !this.data.noMoreRecords) {
      this.loadRecords(false);
    } else if (this.data.activeTab === 'exchange' && this.data.exchangeHasMore) {
      this.loadExchanges(this.data.exchangePage, false);
    }
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    if (tab === this.data.activeTab) return;
    this.setData({ activeTab: tab });
    if (tab === 'detail' && this.data.records.length === 0) this.loadRecords(true);
    if (tab === 'exchange' && this.data.exchanges.length === 0) this.loadExchanges(1, true);
  },

  async loadRecords(reset) {
    try {
      const page = reset ? 1 : this.data.recordPage;
      const res = await get('/api/points/records', { page, page_size: 20 }, { showLoading: false });
      const list = (res.records || res.items || []).map((r) => ({
        ...r,
        type_label: TYPE_LABEL[r.type] || r.type,
        time: (r.created_at || '').replace('T', ' ').slice(0, 19),
      }));
      const records = reset ? list : this.data.records.concat(list);
      this.setData({
        records,
        recordPage: page + 1,
        noMoreRecords: list.length < 20,
      });
    } catch (e) {
      this.setData({ noMoreRecords: true });
    }
  },

  async loadExchanges(page, reset) {
    this.setData({ exchangeLoading: true });
    try {
      const resp = (await get('/api/points/exchange-records', { page, page_size: 20 }, { showLoading: false })) || {};
      const list = (resp.items || []).map((r) => {
        const meta = TYPE_META[r.goods_type] || TYPE_META.virtual;
        const sm = STATUS_META[r.status] || { text: r.status, color: '#666' };
        return {
          ...r,
          typeText: meta.text,
          typeColor: meta.color,
          typeIcon: meta.icon,
          statusText: sm.text,
          statusColor: sm.color,
          exchangeTimeStr: fmt(r.exchange_time),
          expireAtStr: fmt(r.expire_at),
          canAppointment: r.goods_type === 'service' && r.status !== 'expired' && r.ref_service_id,
          canViewCoupon: r.goods_type === 'coupon',
          canViewOrder: r.goods_type === 'physical',
        };
      });
      const total = Number(resp.total || 0);
      const items = reset ? list : this.data.exchanges.concat(list);
      const loaded = (page - 1) * 20 + list.length;
      this.setData({
        exchanges: items,
        exchangePage: page + 1,
        exchangeHasMore: loaded < total && list.length > 0,
        exchangeLoading: false,
      });
    } catch (e) {
      this.setData({ exchangeLoading: false, exchangeHasMore: false });
    }
  },

  goProductDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/product-detail/index?id=${id}` });
  },

  goMyCoupons() {
    wx.navigateTo({ url: '/pages/my-coupons/index' });
  },

  goOrder() {
    wx.navigateTo({ url: '/pages/unified-orders/index' });
  },
});
