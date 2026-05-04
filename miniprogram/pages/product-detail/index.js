const { get, post } = require('../../utils/request');

Page({
  data: {
    id: '',
    product: null,
    currentMediaIndex: 0,
    faqExpanded: {},
    isFavorited: false,
    stores: [],
    reviews: [],
    loading: true,
    appointmentDate: '',
    timeSlots: [],
    slotAvailability: [],
    disabledSlots: [],
    fullyBookedSlots: [],
    expiredSlots: [],
    availableStores: [],
    currentStoreIdx: 0,
    storeDrawerVisible: false,
    sortByDistance: false,
    // OPT-1 / M3-b：从券进入时携带 couponId，下单时透传
    couponId: ''
  },

  onLoad(options) {
    const opts = options || {};
    this.setData({
      id: opts.id,
      couponId: opts.couponId ? String(opts.couponId) : ''
    });
    this.loadProduct();
  },

  async loadProduct() {
    try {
      const res = await get(`/api/products/${this.data.id}`);
      const product = res.data || res;
      this.setData({
        product,
        isFavorited: product.is_favorited || false,
        stores: product.stores || [],
        reviews: product.reviews || [],
        loading: false
      });

      // [2026-05-02 H5 下单流程优化 PRD v1.0] 详情页删除日期/时段/门店选择，
      // 选择行为整体下沉到下单页（pages/checkout）。详情页只保留商品展示。

      // 收藏状态回显
      try {
        const fav = await get(`/api/favorites/status?content_type=product&content_id=${this.data.id}`);
        const favData = fav.data || fav;
        this.setData({ isFavorited: Boolean(favData && favData.is_favorited) });
      } catch (_) { /* 未登录或失败时静默 */ }
    } catch (e) {
      this.setData({ loading: false });
      console.log('loadProduct error', e);
    }
  },

  onMediaChange(e) {
    this.setData({ currentMediaIndex: e.detail.current });
  },

  previewImage(e) {
    const current = e.currentTarget.dataset.src;
    const media = (this.data.product && this.data.product.media) || [];
    const urls = media.filter(m => m.type === 'image').map(m => m.url);
    wx.previewImage({ current, urls });
  },

  toggleFaq(e) {
    const idx = e.currentTarget.dataset.index;
    const key = `faqExpanded.${idx}`;
    this.setData({ [key]: !this.data.faqExpanded[idx] });
  },

  async toggleFavorite() {
    try {
      const res = await post(`/api/favorites?content_type=product&content_id=${this.data.id}`);
      const data = res.data || res || {};
      const newVal = data.is_favorited != null ? Boolean(data.is_favorited) : !this.data.isFavorited;
      this.setData({ isFavorited: newVal });
      wx.showToast({
        title: newVal ? '收藏成功，可在「我的-收藏」中查看' : '已取消收藏',
        icon: 'none',
        duration: 2000,
      });
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' });
      console.log('toggleFavorite error', e);
    }
  },

  goBuy() {
    const cid = this.data.couponId;
    const suffix = cid ? `&couponId=${cid}` : '';
    wx.navigateTo({
      url: `/pages/checkout/index?product_id=${this.data.id}${suffix}`
    });
  },

  formatDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  },

  async loadSlotAvailability(dateStr) {
    if (!dateStr || !this.data.id) return;
    const product = this.data.product;
    if (!product || !product.time_slots || product.time_slots.length === 0) return;
    try {
      const res = await get(`/api/products/${this.data.id}/time-slots/availability`, { date: dateStr });
      const data = (res.data || res)?.data || {};
      const slots = data.slots || [];
      this.setData({ slotAvailability: slots });
      this.updateSlotDisabledState(dateStr, slots);
    } catch (e) {
      this.setData({ slotAvailability: [], disabledSlots: [], fullyBookedSlots: [], expiredSlots: [] });
    }
  },

  updateSlotDisabledState(dateStr, availSlots) {
    const product = this.data.product;
    if (!product || !product.time_slots) return;
    const today = this.formatDate(new Date());
    const isToday = dateStr === today;
    const now = new Date();
    const nowHM = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const disabled = [];
    const fullyBooked = [];
    const expiredArr = [];
    product.time_slots.forEach(slot => {
      const label = `${slot.start}-${slot.end}`;
      const expired = isToday && slot.end <= nowHM;
      const avail = availSlots.find(s => `${s.start_time}-${s.end_time}` === label);
      const isFull = avail ? avail.available <= 0 : false;
      if (expired || isFull) disabled.push(label);
      if (expired) expiredArr.push(label);
      if (isFull && !expired) fullyBooked.push(label);
    });
    this.setData({ disabledSlots: disabled, fullyBookedSlots: fullyBooked, expiredSlots: expiredArr });
  },

  async loadAvailableStores() {
    const tryFetch = async (lat, lng) => {
      try {
        const params = (lat !== undefined && lng !== undefined) ? { lat, lng } : {};
        const res = await get(`/api/products/${this.data.id}/available-stores`, params);
        const data = (res.data || res)?.data || {};
        this.setData({
          availableStores: data.stores || [],
          currentStoreIdx: 0,
          sortByDistance: data.sort_by === 'distance'
        });
      } catch (e) {
        this.setData({ availableStores: [] });
      }
    };
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => tryFetch(loc.latitude, loc.longitude),
      fail: () => tryFetch()
    });
  },

  onSwitchStore() {
    if (this.data.availableStores.length <= 1) return;
    this.setData({ storeDrawerVisible: true });
  },

  /**
   * [2026-05-01 门店地图能力 PRD v1.0] 点击门店卡片调起 wx.openLocation
   * 微信原生面板（腾讯地图底图）会自动提供"导航 / 查看周边"按钮，无需自定义抽屉。
   * 当门店无经纬度时，回退到切换门店行为。
   */
  onStoreCardTap() {
    const list = this.data.availableStores;
    if (!list || list.length === 0) return;
    const cur = list[this.data.currentStoreIdx] || list[0];
    if (cur.lat == null || cur.lng == null) {
      // 无经纬度：回退切换
      this.onSwitchStore();
      return;
    }
    const fullAddr = `${cur.province || ''}${cur.city || ''}${cur.district || ''}${cur.address || ''}`;
    wx.openLocation({
      latitude: Number(cur.lat),
      longitude: Number(cur.lng),
      name: cur.name,
      address: fullAddr,
      scale: 16,
      fail: () => wx.showToast({ title: '打开地图失败', icon: 'none' }),
    });
  },

  onCloseDrawer() {
    this.setData({ storeDrawerVisible: false });
  },

  onPickStore(e) {
    const idx = e.currentTarget.dataset.idx;
    this.setData({ currentStoreIdx: Number(idx), storeDrawerVisible: false });
  },

  onShareAppMessage() {
    const p = this.data.product;
    return {
      title: p ? p.name : '健康商品',
      path: `/pages/product-detail/index?id=${this.data.id}`
    };
  }
});
