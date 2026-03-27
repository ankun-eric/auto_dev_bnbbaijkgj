const { get } = require('../../utils/request');

Page({
  data: {
    keyword: '',
    searchFocus: false,
    currentTab: 0,
    tabs: ['推荐', '养生', '饮食', '运动', '心理', '中医', '育儿'],
    loading: false,
    articles: [
      { id: 1, title: '春季养生：如何预防过敏性鼻炎', tag: '养生', author: '健康编辑部', time: '2小时前', cover: '', views: 1280, likes: 256, comments: 32 },
      { id: 2, title: '高血压患者饮食指南：这些食物要少吃', tag: '饮食', author: '营养师小王', time: '5小时前', cover: '', views: 2350, likes: 480, comments: 56 },
      { id: 3, title: '运动健身：适合上班族的5分钟锻炼法', tag: '运动', author: '运动达人', time: '1天前', cover: '', views: 3600, likes: 720, comments: 88 },
      { id: 4, title: '中医养生：四季养生要点全解析', tag: '中医', author: '中医养生堂', time: '2天前', cover: '', views: 1890, likes: 340, comments: 45 },
      { id: 5, title: '心理健康：如何有效管理工作压力', tag: '心理', author: '心理咨询师', time: '3天前', cover: '', views: 4200, likes: 890, comments: 120 }
    ]
  },

  onLoad(options) {
    if (options.focus === 'true') {
      this.setData({ searchFocus: true });
    }
  },

  onSearch(e) {
    this.setData({ keyword: e.detail.value });
  },

  switchTab(e) {
    this.setData({ currentTab: e.currentTarget.dataset.index });
    this.loadArticles();
  },

  async loadArticles() {
    this.setData({ loading: true });
    try {
      // const res = await get('/api/content/articles', { category: this.data.tabs[this.data.currentTab] });
      // this.setData({ articles: res.data });
    } catch (e) {
      console.log('loadArticles error', e);
    }
    this.setData({ loading: false });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
  }
});
