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
    wx.navigateTo({ url: '/pages/points-exchange-records/index' });
  },

  exchangeGoods(e) {
    const item = e.currentTarget.dataset.item;
    if (item.isDev) {
      wx.showToast({ title: '该类型商品正在开发中', icon: 'none' });
      return;
    }
    if (this.data.totalPoints < item.points) {
      wx.showToast({ title: '积分不足', icon: 'none' });
      return;
    }
    const suffix = item.type === 'service' ? '\n\n兑换后30天内有效，过期作废，积分不退' : '';
    wx.showModal({
      title: '兑换确认',
      content: `确定使用 ${item.points} 积分兑换「${item.name}」吗？${suffix}`,
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post('/api/points/mall/exchange', {
            goods_id: item.id,
            quantity: 1
          }, { showLoading: true });
          wx.showToast({ title: '兑换成功', icon: 'success' });
          this.loadAvailablePoints();
          this.loadGoods();
        } catch (err) {
          const msg = (err && err.data && err.data.detail) || '兑换失败';
          wx.showToast({ title: msg, icon: 'none' });
        }
      }
    });
  }
});
