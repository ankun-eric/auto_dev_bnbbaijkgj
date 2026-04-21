const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    service: {
      id: '',
      name: '在线图文问诊',
      icon: '💬',
      bgColor: 'linear-gradient(135deg, #52c41a, #13c2c2)',
      price: 29,
      sales: 12580,
      fullDesc: '与专业医生在线文字交流，随时随地获取健康建议。支持图片、语音等多种交流方式，医生将在30分钟内回复。',
      contents: [
        '专业医生一对一图文咨询',
        '30分钟内首次回复',
        '24小时内不限次数追问',
        '电子处方与用药建议',
        '问诊记录永久保存'
      ],
      notices: [
        '本服务不能替代线下就医',
        '紧急情况请立即拨打120',
        '购买后48小时内有效',
        '如需退款请联系客服'
      ]
    }
  },

  onLoad(options) {
    if (options.id) {
      this.loadService(options.id);
    }
  },

  async loadService(id) {
    try {
      // const res = await get(`/api/services/${id}`);
      // this.setData({ service: res.data });
    } catch (e) {
      console.log('loadService error', e);
    }
  },

  buyService() {
    if (!checkLogin()) return;
    if (this.data.service.price > 0) {
      wx.showModal({
        title: '确认购买',
        content: `确认购买「${this.data.service.name}」？费用：¥${this.data.service.price}`,
        success: (res) => {
          if (res.confirm) {
            wx.showToast({ title: '购买成功', icon: 'success' });
            setTimeout(() => {
              wx.navigateTo({ url: '/pages/unified-orders/index' });
            }, 1500);
          }
        }
      });
    } else {
      wx.navigateTo({ url: '/pages/chat/index?type=general' });
    }
  },

  contactService() {
    wx.navigateTo({ url: '/pages/customer-service/index' });
  }
});
