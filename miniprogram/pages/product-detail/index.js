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
    loading: true
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
      await post(`/api/favorites?content_type=product&content_id=${this.data.id}`);
      const newVal = !this.data.isFavorited;
      this.setData({ isFavorited: newVal });
      wx.showToast({ title: newVal ? '已收藏' : '已取消收藏', icon: 'success' });
    } catch (e) {
      console.log('toggleFavorite error', e);
    }
  },

  goBuy() {
    wx.navigateTo({
      url: `/pages/checkout/index?product_id=${this.data.id}`
    });
  },

  onShareAppMessage() {
    const p = this.data.product;
    return {
      title: p ? p.name : '健康商品',
      path: `/pages/product-detail/index?id=${this.data.id}`
    };
  }
});
