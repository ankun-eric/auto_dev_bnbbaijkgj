const { post } = require('../../utils/request');

Page({
  data: {
    currentStep: 0,
    bodyParts: [
      { id: 'head', name: '头部', icon: '🧠' },
      { id: 'eye', name: '眼睛', icon: '👁️' },
      { id: 'throat', name: '咽喉', icon: '👅' },
      { id: 'chest', name: '胸部', icon: '🫁' },
      { id: 'stomach', name: '腹部', icon: '🤰' },
      { id: 'back', name: '腰背', icon: '🦴' },
      { id: 'limbs', name: '四肢', icon: '💪' },
      { id: 'skin', name: '皮肤', icon: '🖐️' },
      { id: 'other', name: '其他', icon: '➕' }
    ],
    selectedPart: '',
    symptoms: [],
    durations: ['今天开始', '2-3天', '一周内', '一个月内', '一个月以上'],
    selectedDuration: '',
    extraDesc: '',
    analyzing: false,
    analysisResult: null
  },

  selectPart(e) {
    const part = e.currentTarget.dataset.part;
    this.setData({ selectedPart: part.id });
    this.loadSymptoms(part.id);
  },

  loadSymptoms(partId) {
    const symptomsMap = {
      head: ['头痛', '头晕', '偏头痛', '头部沉重', '记忆力减退', '注意力不集中'],
      eye: ['视力模糊', '眼干', '眼痒', '眼红', '流泪', '畏光'],
      throat: ['咽痛', '咳嗽', '声音嘶哑', '吞咽困难', '口干', '口苦'],
      chest: ['胸闷', '心悸', '气短', '胸痛', '呼吸困难', '咳嗽'],
      stomach: ['腹痛', '腹胀', '恶心', '呕吐', '腹泻', '便秘', '食欲不振'],
      back: ['腰痛', '背痛', '腰酸', '活动受限', '晨僵', '放射痛'],
      limbs: ['关节痛', '肌肉酸痛', '麻木', '无力', '肿胀', '抽筋'],
      skin: ['瘙痒', '红疹', '脱皮', '干燥', '色素沉着', '水泡'],
      other: ['发热', '乏力', '失眠', '多汗', '体重变化', '情绪异常']
    };

    const list = (symptomsMap[partId] || []).map((name, i) => ({
      id: `${partId}_${i}`,
      name,
      selected: false
    }));
    this.setData({ symptoms: list });
  },

  toggleSymptom(e) {
    const index = e.currentTarget.dataset.index;
    const key = `symptoms[${index}].selected`;
    this.setData({ [key]: !this.data.symptoms[index].selected });
  },

  selectDuration(e) {
    this.setData({ selectedDuration: e.currentTarget.dataset.duration });
  },

  onDescInput(e) {
    this.setData({ extraDesc: e.detail.value });
  },

  prevStep() {
    if (this.data.currentStep > 0) {
      this.setData({ currentStep: this.data.currentStep - 1 });
    }
  },

  async nextStep() {
    const { currentStep, selectedPart, symptoms } = this.data;

    if (currentStep === 0) {
      if (!selectedPart) {
        wx.showToast({ title: '请选择身体部位', icon: 'none' });
        return;
      }
      this.setData({ currentStep: 1 });
    } else if (currentStep === 1) {
      const selected = symptoms.filter(s => s.selected);
      if (selected.length === 0) {
        wx.showToast({ title: '请至少选择一个症状', icon: 'none' });
        return;
      }
      this.setData({ currentStep: 2, analyzing: true });
      await this.analyze();
    }
  },

  async analyze() {
    try {
      const selected = this.data.symptoms.filter(s => s.selected).map(s => s.name);
      // Step 1: Create a symptom_check session
      // const sessionRes = await post('/api/chat/sessions', { session_type: 'symptom_check' });
      // Step 2: Send symptoms as a message
      // const res = await post(`/api/chat/sessions/${sessionRes.id}/messages`, {
      //   content: `部位:${this.data.selectedPart}, 症状:${selected.join(',')}, 持续:${this.data.selectedDuration}, 备注:${this.data.extraDesc}`,
      //   message_type: 'text'
      // });
      await new Promise(resolve => setTimeout(resolve, 2500));

      this.setData({
        analyzing: false,
        analysisResult: {
          possibilities: [
            { name: '普通感冒', probability: 65, description: '上呼吸道病毒感染引起，一般7-10天可自愈' },
            { name: '过敏性反应', probability: 20, description: '环境过敏原引起的症状，需要排查过敏源' },
            { name: '需要进一步检查', probability: 15, description: '建议到医院进行详细检查以明确诊断' }
          ],
          advices: [
            '注意休息，保持充足睡眠',
            '多饮温水，清淡饮食',
            '如症状持续加重，建议尽快就医',
            '可以通过AI健康咨询获取更详细的建议'
          ]
        }
      });
    } catch (e) {
      this.setData({ analyzing: false });
      wx.showToast({ title: '分析失败，请重试', icon: 'none' });
    }
  },

  goChat() {
    const selected = this.data.symptoms.filter(s => s.selected).map(s => s.name).join('、');
    wx.navigateTo({
      url: `/pages/chat/index?type=symptom&question=${encodeURIComponent('我有以下症状：' + selected)}`
    });
  },

  restart() {
    this.setData({
      currentStep: 0,
      selectedPart: '',
      symptoms: [],
      selectedDuration: '',
      extraDesc: '',
      analysisResult: null
    });
  }
});
