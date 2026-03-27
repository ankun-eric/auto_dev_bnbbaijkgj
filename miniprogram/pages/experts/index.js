const { get } = require('../../utils/request');

Page({
  data: {
    currentDept: '',
    departments: ['内科', '外科', '中医科', '妇科', '儿科', '营养科', '皮肤科', '全科'],
    experts: [
      { id: '1', name: '张明华', title: '主任医师', department: '内科', hospital: '协和医院', color: '#52c41a', tags: ['心血管', '高血压'], description: '从事内科临床工作30年，擅长心血管疾病、高血压的诊治', consultCount: 12580, rating: 98, price: 99 },
      { id: '2', name: '李芳', title: '副主任医师', department: '中医科', hospital: '中医院', color: '#13c2c2', tags: ['体质调理', '针灸'], description: '中医内科专家，擅长体质辨识与调理，针灸治疗', consultCount: 8920, rating: 97, price: 79 },
      { id: '3', name: '王建国', title: '主治医师', department: '全科', hospital: '社区医院', color: '#1890ff', tags: ['全科', '慢病管理'], description: '全科医学专家，擅长慢性病管理、健康咨询', consultCount: 6430, rating: 96, price: 49 },
      { id: '4', name: '陈晓燕', title: '主任医师', department: '营养科', hospital: '协和医院', color: '#722ed1', tags: ['营养', '减重'], description: '营养学专家，擅长各类营养相关疾病的诊治和指导', consultCount: 5210, rating: 99, price: 89 }
    ]
  },

  onLoad() {
    this.loadExperts();
  },

  filterDept(e) {
    this.setData({ currentDept: e.currentTarget.dataset.dept });
    this.loadExperts();
  },

  async loadExperts() {
    try {
      // const res = await get('/api/experts', { department: this.data.currentDept });
      // this.setData({ experts: res.data });
    } catch (e) {
      console.log('loadExperts error', e);
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/expert-detail/index?id=${id}` });
  }
});
