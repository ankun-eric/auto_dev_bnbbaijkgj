const { uploadFile } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    showQuiz: false,
    showResult: false,
    currentQuestion: 0,
    questions: [
      { text: '您是否经常感到疲乏无力？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您是否容易出汗（不因运动）？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您的手脚是否经常发凉？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您是否经常感到口干舌燥？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您的睡眠质量如何？', options: [{ label: '很好', value: 1 }, { label: '一般', value: 2 }, { label: '较差', value: 3 }, { label: '很差', value: 4 }] },
      { text: '您是否容易感到心情抑郁或焦虑？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] }
    ],
    result: null
  },

  startTongue() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      camera: 'back',
      success: (res) => {
        wx.showLoading({ title: 'AI舌诊分析中...' });
        setTimeout(() => {
          wx.hideLoading();
          this.showTcmResult('舌诊分析');
        }, 2000);
      }
    });
  },

  startFace() {
    if (!checkLogin()) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      camera: 'front',
      success: (res) => {
        wx.showLoading({ title: 'AI面诊分析中...' });
        setTimeout(() => {
          wx.hideLoading();
          this.showTcmResult('面诊分析');
        }, 2000);
      }
    });
  },

  startConstitution() {
    if (!checkLogin()) return;
    this.setData({ showQuiz: true, showResult: false, currentQuestion: 0 });
  },

  goTcmChat() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=tcm' });
  },

  selectOption(e) {
    const value = e.currentTarget.dataset.value;
    const { currentQuestion, questions } = this.data;

    if (currentQuestion < questions.length - 1) {
      this.setData({ currentQuestion: currentQuestion + 1 });
    } else {
      this.setData({ showQuiz: false });
      wx.showLoading({ title: '分析中...' });
      setTimeout(() => {
        wx.hideLoading();
        this.showTcmResult('体质测评');
      }, 1500);
    }
  },

  showTcmResult(source) {
    this.setData({
      showResult: true,
      result: {
        type: '气虚质',
        description: '元气不足，以气息低弱、机体脏腑功能状态低下为主要特征的体质状态',
        traits: [
          '容易疲乏，精力不足',
          '说话声音偏低，不喜多言',
          '容易感冒，抵抗力较弱',
          '稍微活动就出汗',
          '舌淡红，舌边有齿痕'
        ],
        advices: [
          { title: '饮食调理', content: '宜食益气健脾食物，如黄芪、党参、山药、大枣。避免生冷寒凉食物。' },
          { title: '运动建议', content: '适合柔和运动，如太极拳、八段锦、散步。避免剧烈运动和大量出汗。' },
          { title: '起居调护', content: '保持充足睡眠，避免过度劳累。注意保暖，防止感冒。' },
          { title: '穴位保健', content: '常按足三里、气海、关元穴，可艾灸补气。' }
        ]
      }
    });
  },

  resetAll() {
    this.setData({
      showQuiz: false,
      showResult: false,
      currentQuestion: 0,
      result: null
    });
  }
});
