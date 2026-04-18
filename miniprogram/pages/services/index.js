const { get } = require('../../utils/request');
const { ensureMerchantEntry, syncTabBar } = require('../../utils/util');

const PAGE_SIZE = 10;

Page({
  data: {
    pageMode: 'user',
    currentTab: 0,
    tabs: [],
    categories: [],
    services: [],
    page: 1,
    hasMore: false,
    loading: false,
    // 商家模式数据
    records: [],
    noMore: false,
    pageSize: 20,
    totalCount: 0,
    startDate: '',
    endDate: '',
    activeQuick: 'today'
  },

  onLoad() {
    this.initDates();
  },

  onShow() {
    syncTabBar(this, '/pages/services/index');
    const app = getApp();
    const pageMode = app.getCurrentRole() || 'user';
    this.setData({ pageMode });
    if (pageMode === 'merchant') {
      if (!ensureMerchantEntry()) return;
      this.resetMerchantRecords();
      this.loadRecords();
      return;
    }
    if (this.data.categories.length === 0) {
      this.loadCategories();
    } else {
      this.loadServices(true);
    }
  },

  onPullDownRefresh() {
    if (this.data.pageMode === 'merchant') {
      this.resetMerchantRecords();
      this.loadRecords().finally(() => wx.stopPullDownRefresh());
      return;
    }
    this.loadCategories().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.pageMode === 'merchant') {
      if (!this.data.noMore && !this.data.loading) {
        this.loadRecords();
      }
      return;
    }
    if (this.data.hasMore && !this.data.loading) {
      const next = this.data.page + 1;
      this.setData({ page: next });
      this.loadServices(false);
    }
  },

  async loadCategories() {
    try {
      const res = await get('/api/products/categories', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res.items || []).filter(c => !c.parent_id);
      const tabs = items.map(c => c.name);
      this.setData({
        categories: items,
        tabs,
        currentTab: 0,
        page: 1,
        services: []
      });
      if (items.length > 0) {
        await this.loadServices(true);
      }
    } catch (e) {
      console.log('loadCategories error', e);
    }
  },

  switchTab(e) {
    const index = e.currentTarget.dataset.index;
    if (index === this.data.currentTab) return;
    this.setData({
      currentTab: index,
      services: [],
      page: 1,
      hasMore: false
    });
    this.loadServices(true);
  },

  async loadServices(reset) {
    const cat = this.data.categories[this.data.currentTab];
    if (!cat) return Promise.resolve();
    if (this.data.loading) return Promise.resolve();
    this.setData({ loading: true });
    try {
      const res = await get('/api/products', {
        category_id: cat.id,
        page: this.data.page,
        page_size: PAGE_SIZE
      }, { showLoading: false, suppressErrorToast: true });
      const items = res.items || [];
      const list = (items || []).map(p => ({
        id: p.id,
        name: p.name,
        desc: p.description || '',
        icon: cat.icon || '🏥',
        cover: p.cover_image || (p.images && p.images[0]) || '',
        bgColor: 'rgba(82,196,26,0.12)',
        price: p.sale_price,
        marketPrice: p.market_price,
        sales: p.sales_count || 0
      }));
      const newServices = reset ? list : this.data.services.concat(list);
      const total = Number(res.total || 0);
      this.setData({
        services: newServices,
        hasMore: this.data.page * PAGE_SIZE < total
      });
    } catch (e) {
      console.log('loadServices error', e);
    } finally {
      this.setData({ loading: false });
    }
    return Promise.resolve();
  },

  goServiceDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/product-detail/index?id=${id}` });
  },

  initDates() {
    const today = this.formatDate(new Date());
    this.setData({
      startDate: today,
      endDate: today
    });
  },

  formatDate(date) {
    const y = date.getFullYear();
    const m = `${date.getMonth() + 1}`.padStart(2, '0');
    const d = `${date.getDate()}`.padStart(2, '0');
    return `${y}-${m}-${d}`;
  },

  resetMerchantRecords() {
    this.setData({
      records: [],
      noMore: false,
      page: 1,
      totalCount: 0
    });
  },

  onStartDateChange(e) {
    this.setData({
      startDate: e.detail.value,
      activeQuick: '',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  onEndDateChange(e) {
    this.setData({
      endDate: e.detail.value,
      activeQuick: '',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  filterToday() {
    const today = this.formatDate(new Date());
    this.setData({
      startDate: today,
      endDate: today,
      activeQuick: 'today',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  filterWeek() {
    const now = new Date();
    const day = now.getDay() || 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - day + 1);
    this.setData({
      startDate: this.formatDate(monday),
      endDate: this.formatDate(now),
      activeQuick: 'week',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  filterMonth() {
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    this.setData({
      startDate: this.formatDate(firstDay),
      endDate: this.formatDate(now),
      activeQuick: 'month',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  filterAll() {
    this.setData({
      startDate: '',
      endDate: '',
      activeQuick: 'all',
      page: 1,
      records: [],
      noMore: false
    });
    this.loadRecords();
  },

  async loadRecords() {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    if (!currentStore || this.data.loading) return Promise.resolve();

    this.setData({ loading: true });
    try {
      const res = await get('/api/merchant/orders/records', {
        store_id: currentStore.id,
        page: this.data.page,
        page_size: this.data.pageSize,
        start_date: this.data.startDate || undefined,
        end_date: this.data.endDate || undefined
      }, { showLoading: false });
      const list = res.items || [];
      const newRecords = this.data.records.concat(list);
      this.setData({
        records: newRecords,
        totalCount: res.total || 0,
        page: this.data.page + 1,
        noMore: newRecords.length >= (res.total || 0) || list.length < this.data.pageSize
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  }
});
