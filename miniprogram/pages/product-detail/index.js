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
    sortByDistance: false
  },

  onLoad(options) {
    this.setData({ id: options.id });
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

      const today = this.formatDate(new Date());
      const slotLabels = (product.time_slots || []).map(s => `${s.start}-${s.end}`);
      this.setData({
        appointmentDate: today,
        timeSlots: slotLabels
      });
      if (slotLabels.length > 0) {
        this.loadSlotAvailability(today);
      }

      this.loadAvailableStores();
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
    wx.navigateTo({
      url: `/pages/checkout/index?product_id=${this.data.id}`
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
