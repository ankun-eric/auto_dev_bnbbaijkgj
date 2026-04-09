const { get } = require('../../utils/request');

const TYPE_LABEL_MAP = {
  all: '全部',
  article: '文章',
  video: '视频',
  service: '服务',
  points_mall: '积分商品'
};

Page({
  data: {
    query: '',
    currentTab: 'all',
    tabs: [
      { label: '全部', value: 'all' },
      { label: '文章', value: 'article' },
      { label: '视频', value: 'video' },
      { label: '服务', value: 'service' },
      { label: '积分商品', value: 'points_mall' }
    ],
    results: [],
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,
    loadingMore: false
  },

  onLoad(options) {
    const q = options.q ? decodeURIComponent(options.q) : '';
    let source = options.source === 'voice' ? 'voice' : 'text';
    this.setData({ query: q, _searchSource: source });
    if (q) {
      this.doSearch();
    }
  },

  onSearchBoxTap() {
    wx.navigateBack();
  },

  onTabTap(e) {
    const value = e.currentTarget.dataset.value;
    if (value === this.data.currentTab) return;
    this.setData({
      currentTab: value,
      results: [],
      page: 1,
      hasMore: true
    });
    this.doSearch();
  },

  async doSearch() {
    const { query, currentTab, page, pageSize } = this.data;
    if (!query) return;

    if (page === 1) {
      this.setData({ loading: true });
    } else {
      this.setData({ loadingMore: true });
    }

    try {
      const res = await get('/api/search', {
        q: query,
        type: currentTab,
        page,
        page_size: pageSize,
        source: this.data._searchSource || 'text'
      }, { showLoading: false, suppressErrorToast: true });

      const items = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      const total = res && res.total != null ? res.total : items.length;

      const enriched = items.map(item => ({
        ...item,
        type_label: TYPE_LABEL_MAP[item.type] || item.type || '内容'
      }));

      const allResults = page === 1 ? enriched : this.data.results.concat(enriched);
      const hasMore = allResults.length < total;

      this.setData({
        results: allResults,
        hasMore,
        loading: false,
        loadingMore: false
      });
    } catch (e) {
      this.setData({ loading: false, loadingMore: false });
      if (page === 1) {
        this.setData({ results: [] });
      }
    }
  },

  loadMore() {
    if (!this.data.hasMore || this.data.loadingMore) return;
    this.setData({ page: this.data.page + 1 });
    this.doSearch();
  },

  onReachBottom() {
    this.loadMore();
  },

  onResultTap(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;

    const type = item.type;
    const id = item.id;

    if (type === 'article') {
      wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
    } else if (type === 'video') {
      wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
    } else if (type === 'service') {
      wx.navigateTo({ url: `/pages/service-detail/index?id=${id}` });
    } else if (type === 'points_mall') {
      wx.navigateTo({ url: `/pages/points-mall/index` });
    } else if (item.url) {
      wx.navigateTo({
        url: item.url,
        fail() {
          wx.switchTab({ url: item.url });
        }
      });
    }
  }
});
