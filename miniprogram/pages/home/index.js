const { get } = require('../../utils/request');

Page({
  data: {
    banners: [
      { id: 1, title: 'AI智能问诊', desc: '24小时在线，专业健康咨询', bgColor: 'linear-gradient(135deg, #52c41a, #13c2c2)' },
      { id: 2, title: '体检报告解读', desc: '上传报告，AI秒级分析', bgColor: 'linear-gradient(135deg, #13c2c2, #1890ff)' },
      { id: 3, title: '中医智能辨证', desc: '舌诊面诊，科学辨体质', bgColor: 'linear-gradient(135deg, #722ed1, #eb2f96)' }
    ],
    menuItems: [
      { id: 'ai', label: 'AI问诊', icon: '🤖', bgColor: 'rgba(82,196,26,0.12)', path: '/pages/chat/index?type=general' },
      { id: 'checkup', label: '体检报告', icon: '📋', bgColor: 'rgba(19,194,194,0.12)', path: '/pages/checkup/index' },
      { id: 'symptom', label: '症状自查', icon: '🩺', bgColor: 'rgba(24,144,255,0.12)', path: '/pages/symptom/index' },
      { id: 'tcm', label: '中医辨证', icon: '🌿', bgColor: 'rgba(114,46,209,0.12)', path: '/pages/tcm/index' },
      { id: 'drug', label: '药物查询', icon: '💊', bgColor: 'rgba(250,173,20,0.12)', path: '/pages/drug/index' },
      { id: 'plan', label: '健康计划', icon: '📅', bgColor: 'rgba(235,47,150,0.12)', path: '/pages/health-plan/index' }
    ],
    healthTips: [
      { id: 1, content: '今日气温变化大，注意添衣保暖' },
      { id: 2, content: '建议每天饮水 2000ml 以上' }
    ],
    articles: [
      { id: 1, title: '春季养生：如何预防过敏性鼻炎', tag: '养生', time: '2小时前', cover: '' },
      { id: 2, title: '高血压患者饮食指南：这些食物要少吃', tag: '饮食', time: '5小时前', cover: '' },
      { id: 3, title: '运动健身：适合上班族的5分钟锻炼法', tag: '运动', time: '1天前', cover: '' }
    ],
    unreadCount: 3,
    loading: false
  },

  onLoad() {
    this.loadData();
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      // const res = await get('/api/home/data');
      // this.setData({ ...res.data });
    } catch (e) {
      console.log('loadData error', e);
    }
    this.setData({ loading: false });
  },

  onSearchTap() {
    wx.navigateTo({ url: '/pages/articles/index?focus=true' });
  },

  goNotifications() {
    wx.navigateTo({ url: '/pages/notifications/index' });
  },

  onMenuTap(e) {
    const item = e.currentTarget.dataset.item;
    wx.navigateTo({ url: item.path });
  },

  goArticles() {
    wx.navigateTo({ url: '/pages/articles/index' });
  },

  goArticleDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
  }
});
