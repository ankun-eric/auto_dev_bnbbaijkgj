const { generateId } = require('../../utils/util');

Page({
  data: {
    chatStarted: false,
    inputValue: '',
    scrollToId: '',
    messages: [],
    faqList: [
      { id: 1, question: '如何使用AI问诊？', answer: '进入"AI问诊"页面，选择问诊类型后即可开始与AI医生对话。您可以描述症状，AI会给出专业的分析和建议。' },
      { id: 2, question: '如何上传体检报告？', answer: '进入"体检报告"页面，点击上传区域，选择拍照或从相册选择体检报告图片，AI会自动分析解读。' },
      { id: 3, question: '如何预约专家？', answer: '进入"服务"页面，浏览专家列表，选择心仪的专家后查看排班信息，选择可用时段即可预约。' },
      { id: 4, question: '积分如何获取？', answer: '每日签到、完成健康任务、邀请好友等都可以获取积分。积分可在积分商城兑换各类健康好礼。' },
      { id: 5, question: '如何申请退款？', answer: '进入"我的订单"页面，找到需要退款的订单，点击"申请退款"按钮，填写退款原因后提交即可。' }
    ]
  },

  startChat() {
    this.setData({ chatStarted: true });
    this.addMessage('service', '您好！我是宾尼小康AI客服，很高兴为您服务。请问有什么可以帮助您的？');
  },

  askFaq(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({ chatStarted: true });
    this.addMessage('service', '您好！我是宾尼小康AI客服，很高兴为您服务。');
    setTimeout(() => {
      this.addMessage('user', item.question);
      setTimeout(() => {
        this.addMessage('service', item.answer);
      }, 500);
    }, 300);
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content) return;

    this.addMessage('user', content);
    this.setData({ inputValue: '' });

    setTimeout(() => {
      this.addMessage('service', '感谢您的咨询！您的问题我已收到，正在为您处理中。如果是紧急问题，建议拨打客服电话 400-XXX-XXXX。\n\n还有其他问题可以继续向我提问哦~');
    }, 1000);
  },

  addMessage(role, content) {
    const id = generateId();
    const messages = [...this.data.messages, { id, role, content }];
    this.setData({ messages, scrollToId: `msg-${id}` });
  }
});
