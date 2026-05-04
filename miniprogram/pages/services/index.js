const { get } = require('../../utils/request');
const { ensureMerchantEntry, syncTabBar } = require('../../utils/util');

const PAGE_SIZE = 100;

Page({
  data: {
    pageMode: 'user',
    // 左侧一级分类
    topCategories: [],
    activeTopIndex: 0,
    // 右侧二级子类Tab
    subCategories: [],
    activeSubIndex: -1,
    // 按子类分组的商品
    groupedServices: [],
    scrollToView: '',
    loading: false,
    hasMore: false,
    page: 1,
    // 商家模式数据
    records: [],
    noMore: false,
    pageSize: 20,
    totalCount: 0,
    startDate: '',
    endDate: '',
    activeQuick: 'today',
    // OPT-1 / M3-b：携券筛选上下文
    couponId: '',
    couponBanner: null,
    bannerVisible: false
  },

  _categoryTree: [],
  _scrollThrottleTimer: null,
  _groupOffsets: [],
  _programmaticScroll: false,

  onLoad(options) {
    this.initDates();
    // OPT-1 / M3-b：从券进入时带 couponId
    const couponId = (options && options.couponId) ? String(options.couponId) : '';
    if (couponId) {
      this.setData({ couponId });
      this.loadCouponBanner(couponId);
    }
  },

  // OPT-1 / M3-b：带券筛选时拉取专用列表+横幅
  async loadCouponBanner(couponId) {
    try {
      const res = await get('/api/services/list', { coupon_id: couponId }, { showLoading: false, suppressErrorToast: true });
      const banner = (res && (res.coupon_banner || res.banner)) || null;
      if (banner) {
        this.setData({
          couponBanner: {
            title: banner.title || '已选优惠券',
            subtitle: banner.subtitle || ''
          },
          bannerVisible: true
        });
      }
    } catch (e) {
      console.log('loadCouponBanner error', e);
    }
  },

  // OPT-1 / M3-b：关闭横幅但保留 couponId
  closeCouponBanner() {
    this.setData({ bannerVisible: false });
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
    if (this.data.topCategories.length === 0) {
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
    }
  },

  async loadCategories() {
    try {
      const res = await get('/api/products/categories', {}, { showLoading: false, suppressErrorToast: true });
      const items = res.items || [];
      this._categoryTree = items;

      const topCategories = items.map(c => ({
        id: c.id,
        name: c.name,
        icon: c.icon || '',
        is_virtual: c.is_virtual || false,
        children: c.children || []
      }));

      this.setData({
        topCategories,
        activeTopIndex: 0,
        activeSubIndex: -1,
        subCategories: [],
        groupedServices: [],
        scrollToView: ''
      });

      if (topCategories.length > 0) {
        this._applyTopCategory(0);
      }
    } catch (e) {
      console.log('loadCategories error', e);
    }
  },

  switchTopCategory(e) {
    const index = e.currentTarget.dataset.index;
    if (index === this.data.activeTopIndex) return;
    this._applyTopCategory(index);
  },

  _applyTopCategory(index) {
    const cat = this.data.topCategories[index];
    if (!cat) return;
    const subCategories = (cat.children || []).map(c => ({
      id: c.id,
      name: c.name
    }));
    this.setData({
      activeTopIndex: index,
      subCategories,
      activeSubIndex: -1,
      groupedServices: [],
      scrollToView: '',
      page: 1
    });
    this.loadServices(true);
  },

  switchSubCategory(e) {
    const index = parseInt(e.currentTarget.dataset.index, 10);
    if (index === this.data.activeSubIndex) return;

    this._programmaticScroll = true;
    if (index === -1) {
      this.setData({ activeSubIndex: -1, scrollToView: '' });
      this.loadServices(true);
    } else {
      const sub = this.data.subCategories[index];
      if (!sub) return;
      this.setData({
        activeSubIndex: index,
        scrollToView: 'group-' + sub.id
      });
      setTimeout(() => { this._programmaticScroll = false; }, 500);
    }
  },

  async loadServices(reset) {
    const cat = this.data.topCategories[this.data.activeTopIndex];
    if (!cat) return Promise.resolve();
    if (this.data.loading) return Promise.resolve();
    this.setData({ loading: true });
    try {
      const params = { page: 1, page_size: PAGE_SIZE };
      if (cat.id === 'recommend' || cat.is_virtual) {
        params.category_id = 'recommend';
      } else {
        params.parent_category_id = cat.id;
      }

      const res = await get('/api/products', params, { showLoading: false, suppressErrorToast: true });
      const items = res.items || [];

      const fulfillmentLabels = {
        in_store: { text: '到店', color: '#FF8A3D' },
        delivery: { text: '快递', color: '#3B82F6' },
        virtual: { text: '虚拟', color: '#8B5CF6' },
        on_site: { text: '上门', color: '#10B981' },
        to_store: { text: '到店', color: '#06B6D4' },
      };

      const list = items.map(p => ({
        id: p.id,
        name: p.name,
        desc: p.description || '',
        icon: cat.icon || '🏥',
        cover: p.cover_image || (p.images && p.images[0]) || '',
        bgColor: 'rgba(82,196,26,0.12)',
        price: p.min_price || p.sale_price,
        hasMultiSpec: p.has_multi_spec || false,
        marketPrice: p.market_price,
        sales: p.sales_count || 0,
        categoryId: p.category_id || '',
        fulfillmentType: p.fulfillment_type || '',
        fulfillmentText: (fulfillmentLabels[p.fulfillment_type] || {}).text || '',
        fulfillmentColor: (fulfillmentLabels[p.fulfillment_type] || {}).color || ''
      }));

      const subCats = this.data.subCategories;
      let groupedServices = [];

      if (subCats.length > 0) {
        const groupMap = {};
        subCats.forEach(sc => { groupMap[sc.id] = { categoryId: sc.id, categoryName: sc.name, items: [] }; });
        const ungrouped = { categoryId: 'other', categoryName: '其他', items: [] };

        list.forEach(item => {
          if (groupMap[item.categoryId]) {
            groupMap[item.categoryId].items.push(item);
          } else {
            ungrouped.items.push(item);
          }
        });

        subCats.forEach(sc => {
          if (groupMap[sc.id].items.length > 0) {
            groupedServices.push(groupMap[sc.id]);
          }
        });
        if (ungrouped.items.length > 0) {
          groupedServices.push(ungrouped);
        }
      } else {
        groupedServices = [{ categoryId: 'all', categoryName: '', items: list }];
      }

      this.setData({
        groupedServices,
        hasMore: false
      });

      if (subCats.length > 0) {
        this._computeGroupOffsets();
      }
    } catch (e) {
      console.log('loadServices error', e);
    } finally {
      this.setData({ loading: false });
    }
    return Promise.resolve();
  },

  _computeGroupOffsets() {
    setTimeout(() => {
      const query = wx.createSelectorQuery().in(this);
      query.selectAll('.product-group').boundingClientRect();
      query.select('.product-scroll').boundingClientRect();
      query.exec(res => {
        if (!res || !res[0] || !res[1]) return;
        const groups = res[0];
        const scrollRect = res[1];
        this._groupOffsets = groups.map(g => ({
          id: g.id,
          top: g.top - scrollRect.top
        }));
      });
    }, 300);
  },

  onProductScroll(e) {
    if (this._programmaticScroll) return;
    if (this._scrollThrottleTimer) return;
    this._scrollThrottleTimer = setTimeout(() => {
      this._scrollThrottleTimer = null;
    }, 100);

    const scrollTop = e.detail.scrollTop;
    const offsets = this._groupOffsets;
    if (!offsets || offsets.length === 0) return;

    let matchIndex = -1;
    for (let i = offsets.length - 1; i >= 0; i--) {
      if (scrollTop >= offsets[i].top - 10) {
        matchIndex = i;
        break;
      }
    }

    if (matchIndex < 0) matchIndex = 0;

    const groupId = offsets[matchIndex] && offsets[matchIndex].id;
    if (!groupId) return;

    const catId = groupId.replace('group-', '');
    const subIndex = this.data.subCategories.findIndex(sc => String(sc.id) === String(catId));
    if (subIndex !== -1 && subIndex !== this.data.activeSubIndex) {
      this.setData({ activeSubIndex: subIndex });
    }
  },

  goServiceDetail(e) {
    const id = e.currentTarget.dataset.id;
    // OPT-1 / M3-b：携券筛选时把 couponId 透传到详情→下单
    const cid = this.data.couponId;
    const suffix = cid ? `&couponId=${cid}` : '';
    wx.navigateTo({ url: `/pages/product-detail/index?id=${id}${suffix}` });
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
