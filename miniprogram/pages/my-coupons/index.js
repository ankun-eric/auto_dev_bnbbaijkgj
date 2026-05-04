const { get } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '可用', status: 'unused' },
      { label: '已使用', status: 'used' },
      { label: '已过期', status: 'expired' }
    ],
    coupons: [],
    availableCount: 0,
    loading: false,
    // OPT-1 / M3-a：高亮目标券（从兑换记录"查看券"跳进来时）
    highlightCouponId: ''
  },

  onLoad(options) {
    const opts = options || {};
    // 默认定位"可用" Tab；query.tab 支持 available / unused
    let currentTab = 0;
    if (opts.tab && opts.tab !== 'available' && opts.tab !== 'unused') {
      const idx = this.data.tabs.findIndex(t => t.status === opts.tab);
      if (idx >= 0) currentTab = idx;
    }
    const highlightCouponId = opts.highlightCouponId || '';
    this.setData({ currentTab, highlightCouponId });
    this.loadCoupons();
  },

  onShow() {
    this.loadCoupons();
  },

  onPullDownRefresh() {
    this.loadCoupons().finally(() => wx.stopPullDownRefresh());
  },

  switchTab(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentTab: idx });
    this.loadCoupons();
  },

  async loadCoupons() {
    this.setData({ loading: true });
    const status = this.data.tabs[this.data.currentTab].status;
    try {
      // Bug #3: 可用券数量请求独立接口（tab=unused + exclude_expired=true），
      // 顶部"合计"与 Tab "可用(N)" 均使用该数量，保证一致
      const [listRes, availableRes] = await Promise.all([
        get('/api/coupons/mine', { tab: status }, { showLoading: false }),
        status === 'unused'
          ? Promise.resolve(null)
          : get('/api/coupons/mine', { tab: 'unused', exclude_expired: true }, { showLoading: false }).catch(() => null)
      ]);
      const rawList = (listRes && (listRes.items || listRes)) || [];
      let availableCount;
      if (status === 'unused') {
        availableCount = (listRes && (listRes.available_count != null ? listRes.available_count : (listRes.available != null ? listRes.available : null)));
        if (availableCount == null) availableCount = rawList.length;
      } else {
        availableCount = (availableRes && (availableRes.available_count != null ? availableRes.available_count : (availableRes.available != null ? availableRes.available : (availableRes.total != null ? availableRes.total : (availableRes.items ? availableRes.items.length : 0)))));
      }

      // OPT-1 / M3-a：标记需要闪烁高亮的卡片
      const highlightId = String(this.data.highlightCouponId || '');
      const list = rawList.map(c => ({
        ...c,
        flash: highlightId && String(c.id) === highlightId
      }));

      this.setData({
        coupons: list,
        availableCount: Number(availableCount) || 0
      });

      // 1.5s 后清掉 highlight（仅触发一次）
      if (highlightId && list.some(c => c.flash)) {
        if (this._flashTimer) clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => {
          const cleared = (this.data.coupons || []).map(c => ({ ...c, flash: false }));
          this.setData({ coupons: cleared, highlightCouponId: '' });
        }, 1500);
      }
    } catch (e) {
      console.log('loadCoupons error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  // OPT-1 / M3-a：去使用 → 跳到服务列表带券筛选
  useCoupon(e) {
    const item = (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.item) || {};
    const couponId = item.id;
    if (!couponId) {
      wx.navigateTo({ url: '/pages/services/index' });
      return;
    }
    wx.navigateTo({ url: `/pages/services/index?couponId=${couponId}` });
  }
});
