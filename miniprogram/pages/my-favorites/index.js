const { get, post } = require('../../utils/request');

Page({
  data: {
    currentTab: 0,
    tabs: [
      { label: '商品收藏', type: 'product' },
      { label: '知识收藏', type: 'knowledge' }
    ],
    favorites: [],
    loading: false,
    page: 1,
    pageSize: 10,
    noMore: false
  },

  onLoad() {
    this.loadFavorites();
  },

  onPullDownRefresh() {
    this.resetList();
    this.loadFavorites().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (!this.data.noMore && !this.data.loading) {
      this.loadFavorites();
    }
  },

  switchTab(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ currentTab: idx });
    this.resetList();
    this.loadFavorites();
  },

  resetList() {
    this.setData({ favorites: [], page: 1, noMore: false });
  },

  async loadFavorites() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    const targetType = this.data.tabs[this.data.currentTab].type;
    try {
      const res = await get('/api/favorites', {
        tab: targetType,
        page: this.data.page,
        page_size: this.data.pageSize
      }, { showLoading: false });
      const list = res.items || [];
      const newList = this.data.favorites.concat(list);
      this.setData({
        favorites: newList,
        page: this.data.page + 1,
        noMore: newList.length >= (res.total || 0) || list.length < this.data.pageSize
      });
    } catch (e) {
      console.log('loadFavorites error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const item = e.currentTarget.dataset.item;
    if (item.content_type === 'product') {
      wx.navigateTo({ url: `/pages/product-detail/index?id=${item.content_id}` });
    } else {
      wx.navigateTo({ url: `/pages/article-detail/index?id=${item.content_id}` });
    }
  },

  removeFavorite(e) {
    const item = e.currentTarget.dataset.item;
    wx.showModal({
      title: '取消收藏',
      content: '确定要取消收藏吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/favorites?content_type=${item.content_type}&content_id=${item.content_id}`);
          const list = this.data.favorites.filter(f => f.id !== item.id);
          this.setData({ favorites: list });
          wx.showToast({ title: '已取消收藏', icon: 'success' });
        } catch (e) {
          console.log('removeFavorite error', e);
        }
      }
    });
  }
});
