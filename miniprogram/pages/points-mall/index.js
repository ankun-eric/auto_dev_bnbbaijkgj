const { get, post } = require('../../utils/request');

const TYPE_BADGE = {
  coupon: { text: '优惠券', bg: 'rgba(250,140,22,0.12)', color: '#fa8c16' },
  service: { text: '体验服务', bg: 'rgba(19,194,194,0.12)', color: '#13c2c2' },
  physical: { text: '实物', bg: 'rgba(114,46,209,0.12)', color: '#722ed1' },
  virtual: { text: '虚拟(开发中)', bg: 'rgba(191,191,191,0.2)', color: '#888' },
  third_party: { text: '第三方(开发中)', bg: 'rgba(191,191,191,0.2)', color: '#888' }
};

const ICON_BY_TYPE = {
  coupon: '🎫',
  service: '💆',
  physical: '📦',
  virtual: '🎁',
  third_party: '🛍️'
};

Page({
  data: {
    totalPoints: 0,
    goods: []
  },

  onLoad() {
    this.loadAvailablePoints();
    this.loadGoods();
  },

  onShow() {
    this.loadAvailablePoints();
    this.loadGoods();
  },

  async loadAvailablePoints() {
    try {
      const s = (await get('/api/points/summary', {}, { showLoading: false })) || {};
      const total = s.total_points != null ? s.total_points : 0;
      const available = s.available_points != null
        ? s.available_points
        : (s.available != null ? s.available : total);
      this.setData({ totalPoints: Number(available) || 0 });
    } catch (e) {
      console.log('loadAvailablePoints error', e);
    }
  },

  async loadGoods() {
    try {
      const resp = (await get('/api/points/mall', { page: 1, page_size: 50 }, { showLoading: false })) || {};
      const items = Array.isArray(resp.items) ? resp.items : [];
      const goods = items.map((it) => {
        const type = typeof it.type === 'string' ? it.type : (it.type && it.type.value) || 'virtual';
        const badge = TYPE_BADGE[type] || TYPE_BADGE.virtual;
        const img = Array.isArray(it.images) ? it.images[0] : (typeof it.images === 'string' ? it.images : null);
        return {
          id: it.id,
          name: it.name,
          desc: it.description ? String(it.description).split(';')[0].slice(0, 20) : '',
          image: img,
          icon: ICON_BY_TYPE[type] || '🎁',
          bgColor: badge.bg,
          badgeText: badge.text,
          badgeBg: badge.bg,
          badgeColor: badge.color,
          points: Number(it.price_points || 0),
          stock: Number(it.stock || 0),
          type,
          isDev: type === 'virtual' || type === 'third_party'
        };
      });
      this.setData({ goods });
    } catch (e) {
      console.log('loadGoods error', e);
    }
  },

  goExchangeRecords() {
    // PRD F3：旧按钮跳到新合并页的 兑换记录 Tab
    wx.navigateTo({ url: '/pages/points/detail/index?tab=exchange' });
  },

  // PRD F4：卡片整体可点 → 商品详情页，不再在列表上直接兑换
  exchangeGoods(e) {
    const item = e.currentTarget.dataset.item;
    if (!item || !item.id) return;
    wx.navigateTo({ url: `/pages/points/product-detail/index?id=${item.id}` });
  },
});
