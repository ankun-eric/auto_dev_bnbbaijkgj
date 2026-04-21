const { get } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    expert: {
      id: '1',
      name: '张明华',
      title: '主任医师',
      department: '内科',
      hospital: '协和医院',
      color: '#52c41a',
      consultCount: 12580,
      rating: 98,
      experience: 30,
      price: 99,
      speciality: '心血管疾病、高血压、冠心病、心律失常的诊断和治疗。在高血压个体化治疗和心力衰竭管理方面具有丰富经验。',
      bio: '医学博士，博士生导师。从事心血管内科临床与科研工作30余年，现任中华医学会心血管病分会委员。发表学术论文100余篇，获多项省部级科技成果奖。'
    },
    schedule: [
      { weekday: '周一', date: '03-28', available: true },
      { weekday: '周二', date: '03-29', available: false },
      { weekday: '周三', date: '03-30', available: true },
      { weekday: '周四', date: '03-31', available: true },
      { weekday: '周五', date: '04-01', available: false },
      { weekday: '周六', date: '04-02', available: true },
      { weekday: '周日', date: '04-03', available: false }
    ]
  },

  onLoad(options) {
    if (options.id) {
      this.loadExpert(options.id);
    }
  },

  async loadExpert(id) {
    try {
      // const res = await get(`/api/experts/${id}`);
      // this.setData({ expert: res.data, schedule: res.data.schedule });
    } catch (e) {
      console.log('loadExpert error', e);
    }
  },

  selectSchedule(e) {
    const item = e.currentTarget.dataset.item;
    if (!item.available) {
      wx.showToast({ title: '该时段已约满', icon: 'none' });
      return;
    }
    wx.showToast({ title: `已选择${item.weekday}`, icon: 'success' });
  },

  bookExpert() {
    if (!checkLogin()) return;
    wx.showModal({
      title: '预约确认',
      content: `确定预约${this.data.expert.name}医生的图文问诊吗？费用：¥${this.data.expert.price}`,
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '预约成功', icon: 'success' });
          setTimeout(() => {
            wx.navigateTo({ url: '/pages/unified-orders/index' });
          }, 1500);
        }
      }
    });
  }
});
