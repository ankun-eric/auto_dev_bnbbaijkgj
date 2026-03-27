const { get } = require('../../utils/request');

Page({
  data: {
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
    ]
  },

  onLoad() {
    this.loadServices();
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
  }
});
