const { get } = require('../../utils/request');

Page({
  data: {
    categories: [],
    currentCategoryId: '',
    subCategories: [],
    currentSubCategoryId: '',
    fulfillmentTypes: ['全部', '到店', '上门', '快递', '在线'],
    currentFulfillment: 0,
    priceRanges: [
      { label: '全部', min: '', max: '' },
      { label: '0-50', min: 0, max: 50 },
      { label: '50-200', min: 50, max: 200 },
      { label: '200-500', min: 200, max: 500 },
      { label: '500+', min: 500, max: '' }
    ],
    currentPriceRange: 0,
    pointsOnly: false,
    showFilter: false,
    products: [],
    page: 1,
    pageSize: 10,
    total: 0,
    loading: false,
    noMore: false
  },

  onLoad() {
    this.loadCategories();
    this.loadProducts();
  },

  onPullDownRefresh() {
    this.resetList();
    Promise.all([this.loadCategories(), this.loadProducts()])
      .finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (!this.data.noMore && !this.data.loading) {
      this.loadProducts();
    }
  },

  async loadCategories() {
    try {
      const res = await get('/api/products/categories', {}, { showLoading: false });
      const categories = [{ id: '', name: '全部' }].concat(res.items || res || []);
      this.setData({ categories });
    } catch (e) {
      console.log('loadCategories error', e);
    }
  },

  switchCategory(e) {
    const cat = e.currentTarget.dataset.item;
    const subCategories = cat.children || [];
    this.setData({
      currentCategoryId: cat.id,
      subCategories: subCategories,
      currentSubCategoryId: ''
    });
    this.resetList();
    this.loadProducts();
  },

  switchSubCategory(e) {
    const sub = e.currentTarget.dataset.item;
    this.setData({ currentSubCategoryId: sub.id });
    this.resetList();
    this.loadProducts();
  },

  toggleFilter() {
    this.setData({ showFilter: !this.data.showFilter });
  },

  switchFulfillment(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentFulfillment: idx });
    this.resetList();
    this.loadProducts();
  },

  switchPriceRange(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentPriceRange: idx });
    this.resetList();
    this.loadProducts();
  },

  togglePointsOnly() {
    this.setData({ pointsOnly: !this.data.pointsOnly });
    this.resetList();
    this.loadProducts();
  },

  resetList() {
    this.setData({ products: [], page: 1, noMore: false, total: 0 });
  },

  async loadProducts() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    const params = {
      page: this.data.page,
      page_size: this.data.pageSize
    };
    if (this.data.currentCategoryId) params.category_id = this.data.currentCategoryId;
    if (this.data.currentSubCategoryId) params.sub_category_id = this.data.currentSubCategoryId;

    const fulfillmentMap = ['', 'store', 'home', 'express', 'online'];
    if (this.data.currentFulfillment > 0) {
      params.fulfillment_type = fulfillmentMap[this.data.currentFulfillment];
    }

    const range = this.data.priceRanges[this.data.currentPriceRange];
    if (range.min !== '') params.price_min = range.min;
    if (range.max !== '') params.price_max = range.max;
    if (this.data.pointsOnly) params.points_redeemable = true;

    try {
      const res = await get('/api/products', params, { showLoading: false });
      const list = res.items || [];
      const newProducts = this.data.products.concat(list);
      this.setData({
        products: newProducts,
        total: res.total || 0,
        page: this.data.page + 1,
        noMore: newProducts.length >= (res.total || 0) || list.length < this.data.pageSize
      });
    } catch (e) {
      console.log('loadProducts error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/product-detail/index?id=${id}` });
  }
});
