const { get } = require('../../utils/request');
const { ensureMerchantEntry, syncTabBar } = require('../../utils/util');

Page({
  data: {
    pageMode: 'user',
    currentTab: 0,
    tabs: ['全部', '在线问诊', '体检套餐', '健康管理', '中医服务', '上门服务'],
    services: [
      { id: '1', name: '在线图文问诊', desc: '与专业医生在线文字交流，获取健康建议', icon: '💬', bgColor: 'rgba(82,196,26,0.12)', price: 29, sales: 12580 },
      { id: '2', name: '视频问诊', desc: '面对面视频沟通，更直观了解病情', icon: '📹', bgColor: 'rgba(19,194,194,0.12)', price: 99, sales: 5680 },
      { id: '3', name: 'AI健康评估', desc: '全面AI健康风险评估报告', icon: '🤖', bgColor: 'rgba(24,144,255,0.12)', price: 0, sales: 32100 },
      { id: '4', name: '体检报告解读', desc: '专业医生为您解读体检报告', icon: '📋', bgColor: 'rgba(250,173,20,0.12)', price: 49, sales: 8920 },
      { id: '5', name: '中医体质辨识', desc: '九种体质辨识，个性化调理方案', icon: '🌿', bgColor: 'rgba(114,46,209,0.12)', price: 19, sales: 6430 }
    ],
    experts: [
      { id: '1', name: '张明华', title: '主任医师', department: '内科' },
      { id: '2', name: '李芳', title: '副主任医师', department: '中医科' },
      { id: '3', name: '王建国', title: '主治医师', department: '全科' },
      { id: '4', name: '陈晓燕', title: '主任医师', department: '营养科' }
    ],
    records: [],
    loading: false,
    noMore: false,
    page: 1,
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
    this.loadServices();
  },

  onPullDownRefresh() {
    if (this.data.pageMode === 'merchant') {
      this.resetMerchantRecords();
      this.loadRecords().finally(() => wx.stopPullDownRefresh());
      return;
    }
    this.loadServices().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.pageMode === 'merchant' && !this.data.noMore && !this.data.loading) {
      this.loadRecords();
    }
  },

  switchTab(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ currentTab: index });
    this.loadServices();
  },

  async loadServices() {
    try {
      // const res = await get('/api/services/items', { category: this.data.tabs[this.data.currentTab] });
      // this.setData({ services: res.data });
    } catch (e) {
      console.log('loadServices error', e);
    }
    return Promise.resolve();
  },

  goServiceDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/service-detail/index?id=${id}` });
  },

  goExperts() {
    wx.navigateTo({ url: '/pages/experts/index' });
  },

  goExpertDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/expert-detail/index?id=${id}` });
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
