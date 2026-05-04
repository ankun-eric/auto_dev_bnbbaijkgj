const { get } = require('../../utils/request');

const TYPE_META = {
  coupon: { text: '优惠券', color: '#fa8c16', icon: '🎫' },
  service: { text: '体验服务', color: '#13c2c2', icon: '💆' },
  physical: { text: '实物', color: '#722ed1', icon: '📦' },
  virtual: { text: '虚拟', color: '#bfbfbf', icon: '🎁' },
  third_party: { text: '第三方', color: '#bfbfbf', icon: '🛍️' }
};

const STATUS_META = {
  success: { text: '兑换成功', color: '#52c41a' },
  pending: { text: '处理中', color: '#1890ff' },
  failed: { text: '失败', color: '#ff4d4f' },
  used: { text: '已使用', color: '#8c8c8c' },
  expired: { text: '已过期', color: '#bfbfbf' },
  cancelled: { text: '已取消', color: '#bfbfbf' }
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
    items: [],
    page: 1,
    hasMore: true,
    loading: true
  },

  onLoad() {
    this.loadPage(1, true);
  },

  onShow() {
    this.loadPage(1, true);
  },

  onPullDownRefresh() {
    this.loadPage(1, true).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadPage(this.data.page, false);
    }
  },

  async loadPage(page, reset) {
    this.setData({ loading: true });
    try {
      const resp = (await get('/api/points/exchange-records', { page, page_size: 20 }, { showLoading: false })) || {};
      const list = (resp.items || []).map((r) => {
        const meta = TYPE_META[r.goods_type] || TYPE_META.virtual;
        const sm = STATUS_META[r.status] || { text: r.status, color: '#666' };
        // OPT-4：优惠券类型可拆"查看券 + 去使用"
        const couponId = r.coupon_id || r.user_coupon_id || (r.coupon && (r.coupon.id || r.coupon.user_coupon_id));
        const couponStatus = r.coupon_status || (r.coupon && r.coupon.status) || '';
        const isCoupon = r.goods_type === 'coupon';
        return {
          ...r,
          typeText: meta.text,
          typeColor: meta.color,
          typeIcon: meta.icon,
          statusText: sm.text,
          statusColor: sm.color,
          exchangeTimeStr: fmt(r.exchange_time),
          expireAtStr: fmt(r.expire_at),
          canAppointment: r.goods_type === 'service' && r.status !== 'expired' && r.ref_service_type && r.ref_service_id,
          canViewCoupon: isCoupon,
          couponId: couponId || '',
          couponStatus,
          canUseCoupon: isCoupon && couponStatus === 'available' && !!couponId,
          canViewOrder: r.goods_type === 'physical'
        };
      });
      const total = Number(resp.total || 0);
      const items = reset ? list : this.data.items.concat(list);
      const loaded = (page - 1) * 20 + list.length;
      this.setData({
        items,
        page: page + 1,
        hasMore: loaded < total && list.length > 0,
        loading: false
      });
    } catch (e) {
      this.setData({ loading: false, hasMore: false });
    }
  },

  goAppointment(e) {
    const r = e.currentTarget.dataset.item;
    if (!r) return;
    const map = {
      expert: `/pages/expert-detail/index?id=${r.ref_service_id}`,
      physical_exam: `/pages/service-detail/index?id=${r.ref_service_id}`,
      tcm: `/pages/service-detail/index?id=${r.ref_service_id}`,
      health_plan: `/pages/health-plan/index`
    };
    const url = map[r.ref_service_type];
    if (url) {
      wx.navigateTo({ url });
    } else {
      wx.showToast({ title: '暂无预约入口', icon: 'none' });
    }
  },

  goMyCoupons() {
    wx.navigateTo({ url: '/pages/my-coupons/index?tab=available', fail: () => {
      wx.showToast({ title: '可到"我的优惠券"查看', icon: 'none' });
    }});
  },

  // OPT-4：查看券（次按钮）→ 跳到我的券，并高亮该张
  viewCoupon(e) {
    const item = e.currentTarget.dataset.item || {};
    const couponId = item.couponId;
    const url = couponId
      ? `/pages/my-coupons/index?tab=available&highlightCouponId=${couponId}`
      : `/pages/my-coupons/index?tab=available`;
    wx.navigateTo({ url, fail: () => {
      wx.showToast({ title: '可到"我的优惠券"查看', icon: 'none' });
    }});
  },

  // OPT-4：去使用（主按钮，仅 available 时显示）→ 跳到服务列表带券
  jumpToUseCoupon(e) {
    const item = e.currentTarget.dataset.item || {};
    const couponId = item.couponId;
    if (!couponId) {
      wx.showToast({ title: '券信息缺失', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: `/pages/services/index?couponId=${couponId}` });
  },

  goOrder() {
    wx.navigateTo({ url: '/pages/unified-orders/index' });
  }
});
