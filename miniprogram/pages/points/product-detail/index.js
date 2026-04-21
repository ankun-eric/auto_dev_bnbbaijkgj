const { get, post } = require('../../../utils/request');

const TYPE_BADGE = {
  coupon: { text: '优惠券', color: '#fa8c16' },
  service: { text: '体验服务', color: '#13c2c2' },
  physical: { text: '实物', color: '#722ed1' },
  virtual: { text: '虚拟', color: '#bfbfbf' },
  third_party: { text: '第三方', color: '#bfbfbf' },
};

Page({
  data: {
    id: null,
    item: null,
    badgeText: '',
    badgeColor: '#888',
    buttonText: '立即兑换',
    disabled: false,
    exchanging: false,
  },

  onLoad(options) {
    if (options && options.id) {
      this.setData({ id: options.id });
      this.loadDetail();
    }
  },

  async loadDetail() {
    try {
      const res = await get(`/api/points/mall/items/${this.data.id}`);
      const data = res?.data || res || {};
      const badge = TYPE_BADGE[data.type] || TYPE_BADGE.virtual;
      const disabled = (data.button_state || 'exchangeable') !== 'exchangeable';
      this.setData({
        item: data,
        badgeText: badge.text,
        badgeColor: badge.color,
        buttonText: data.button_text || '立即兑换',
        disabled,
      });
    } catch (e) {
      wx.showToast({ title: (e && e.data && e.data.detail) || '加载失败', icon: 'none' });
      this.setData({ item: null });
    }
  },

  handleExchange() {
    const { item, disabled } = this.data;
    if (!item || disabled) return;
    const suffix = item.type === 'service'
      ? '\n\n兑换后 30 天内有效，过期作废，积分不退。'
      : '';
    wx.showModal({
      title: '兑换确认',
      content: `确认用 ${item.price_points} 积分兑换【${item.name}】吗？${suffix}`,
      confirmText: '确认兑换',
      cancelText: '取消',
      success: async (r) => {
        if (!r.confirm) return;
        this.setData({ exchanging: true });
        try {
          await post('/api/points/mall/exchange', {
            goods_id: item.id,
            quantity: 1,
          });
          wx.showToast({ title: '兑换成功', icon: 'success' });
          setTimeout(() => {
            wx.redirectTo({ url: '/pages/points/detail/index?tab=exchange' });
          }, 600);
        } catch (err) {
          const msg = (err && err.data && err.data.detail) || '兑换失败';
          wx.showToast({ title: msg, icon: 'none' });
        } finally {
          this.setData({ exchanging: false });
        }
      },
    });
  },
});
