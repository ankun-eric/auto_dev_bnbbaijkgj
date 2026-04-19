const { get, post } = require('../../utils/request');

Page({
  data: {
    coupons: [],
    loading: true,
    claimingId: 0,
  },

  onLoad() {
    this.loadCoupons();
  },

  onShow() {
    this.loadCoupons();
  },

  onPullDownRefresh() {
    this.loadCoupons().finally(() => wx.stopPullDownRefresh());
  },

  isLoggedIn() {
    return !!wx.getStorageSync('access_token') || !!wx.getStorageSync('token');
  },

  formatValue(item) {
    if (item.type === 'discount') {
      return `${(Number(item.discount_rate) * 10).toFixed(1)}折`;
    }
    return `¥${item.discount_value || 0}`;
  },

  formatExpire(item) {
    if (item.valid_end) {
      const d = new Date(item.valid_end);
      return `有效期至 ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
    return '长期有效';
  },

  computeButtonState(item) {
    if (typeof item.button_text === 'string' && typeof item.button_disabled === 'boolean') {
      return { text: item.button_text, disabled: !!item.button_disabled };
    }
    if (item.claimed) return { text: '已领取', disabled: true };
    if (item.sold_out || (item.total_count - item.claimed_count) <= 0) {
      return { text: '已抢光', disabled: true };
    }
    return { text: '领取', disabled: false };
  },

  async loadCoupons() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/coupons/available', {}, { showLoading: false });
      const items = (res.items || res || []).map((it) => {
        const btn = this.computeButtonState(it);
        return Object.assign({}, it, {
          _value: this.formatValue(it),
          _expire: this.formatExpire(it),
          _btnText: btn.text,
          _btnDisabled: btn.disabled,
          _remaining: Math.max(0, (it.total_count || 0) - (it.claimed_count || 0)),
        });
      });
      this.setData({ coupons: items });
    } catch (e) {
      console.log('load coupons failed', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  async claim(e) {
    const id = e.currentTarget.dataset.id;
    const item = this.data.coupons.find((c) => c.id === id);
    if (!item || item._btnDisabled) return;
    if (!this.isLoggedIn()) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      setTimeout(() => wx.navigateTo({ url: '/pages/login/index' }), 800);
      return;
    }
    this.setData({ claimingId: id });
    try {
      await post('/api/coupons/claim', { coupon_id: id });
      wx.showToast({ title: '领取成功', icon: 'success' });
      await this.loadCoupons();
    } catch (err) {
      const status = err && err.statusCode;
      if (status === 409) {
        wx.showToast({ title: '您已领取过该券', icon: 'none' });
        await this.loadCoupons();
      } else {
        const msg = (err && err.data && err.data.detail) || '领取失败';
        wx.showToast({ title: msg, icon: 'none' });
      }
    } finally {
      this.setData({ claimingId: 0 });
    }
  },
});
