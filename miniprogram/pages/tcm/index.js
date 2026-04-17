const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

const RELATION_COLORS = {
  '本人': '#52c41a',
  '爸爸': '#1890ff', '妈妈': '#1890ff',
  '儿子': '#eb2f96', '女儿': '#eb2f96',
  '爷爷': '#fa8c16', '奶奶': '#fa8c16',
  '外公': '#fa8c16', '外婆': '#fa8c16'
};
function getRelationColor(name) {
  return RELATION_COLORS[name] || '#8c8c8c';
}

Page({
  data: {
    showTongue: true,
    showFace: true,
    showConstitution: true,

    showQuiz: false,
    showResult: false,
    currentQuestion: 0,
    quizAnswers: [],
    questions: [
      { text: '您是否经常感到疲乏无力？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您是否容易出汗（不因运动）？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您的手脚是否经常发凉？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您是否经常感到口干舌燥？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] },
      { text: '您的睡眠质量如何？', options: [{ label: '很好', value: 1 }, { label: '一般', value: 2 }, { label: '较差', value: 3 }, { label: '很差', value: 4 }] },
      { text: '您是否容易感到心情抑郁或焦虑？', options: [{ label: '没有', value: 1 }, { label: '偶尔', value: 2 }, { label: '经常', value: 3 }, { label: '总是', value: 4 }] }
    ],
    result: null,

    showMemberPicker: false,
    familyMembers: [],
    selectedMemberId: null,

    historyList: [],
    historyLoading: false
  },

  onShow() {
    this.loadTcmConfig();
    this.loadDiagnosisHistory();
  },

  async loadTcmConfig() {
    try {
      const res = await get('/api/tcm/config', {}, { showLoading: false, suppressErrorToast: true });
      if (res) {
        this.setData({
          showTongue: res.tongue_enabled !== false,
          showFace: res.face_enabled !== false,
          showConstitution: res.constitution_enabled !== false
        });
      }
    } catch (e) {
      console.log('loadTcmConfig error', e);
    }
  },

  async loadDiagnosisHistory() {
    this.setData({ historyLoading: true });
    try {
      const res = await get('/api/tcm/diagnosis', {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res && (res.items || res.data) || []);
      const historyList = list.map(item => ({
        id: item.id,
        constitution_type: item.constitution_type || '未知体质',
        description: item.description || '',
        icon: item.icon || '🌿',
        created_at: this._formatTime(item.created_at),
        family_member_name: item.family_member_name || item.family_member_relation || '',
        family_member_id: item.family_member_id
      }));
      this.setData({ historyList });
    } catch (e) {
      console.log('loadDiagnosisHistory error', e);
    } finally {
      this.setData({ historyLoading: false });
    }
  },

  _formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const h = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${day} ${h}:${min}`;
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
    this.setData({ showQuiz: true, showResult: false, currentQuestion: 0, quizAnswers: [] });
  },

  goTcmChat() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=tcm' });
  },

  selectOption(e) {
    const value = e.currentTarget.dataset.value;
    const { currentQuestion, questions, quizAnswers } = this.data;
    const answers = [...quizAnswers];
    answers[currentQuestion] = value;
    this.setData({ quizAnswers: answers });

    if (currentQuestion < questions.length - 1) {
      this.setData({ currentQuestion: currentQuestion + 1 });
    } else {
      this.setData({ showQuiz: false });
      this._submitConstitutionTest(answers);
    }
  },

  async _submitConstitutionTest(answers) {
    wx.showLoading({ title: '分析中...', mask: true });
    try {
      const res = await post('/api/tcm/constitution-test', {
        answers
      }, { showLoading: false, suppressErrorToast: true });

      wx.hideLoading();

      if (res) {
        this.setData({
          showResult: true,
          result: {
            type: res.constitution_type || '气虚质',
            description: res.description || '元气不足，以气息低弱、机体脏腑功能状态低下为主要特征的体质状态',
            traits: res.traits || ['容易疲乏，精力不足', '说话声音偏低，不喜多言'],
            advices: res.advices || [
              { title: '饮食调理', content: '宜食益气健脾食物，如黄芪、党参、山药、大枣。' },
              { title: '运动建议', content: '适合柔和运动，如太极拳、八段锦、散步。' }
            ],
            id: res.id || res.diagnosis_id
          }
        });

        this._showMemberPickerForConstitution();
      }
    } catch (e) {
      wx.hideLoading();
      this.setData({
        showResult: true,
        result: {
          type: '气虚质',
          description: '元气不足，以气息低弱、机体脏腑功能状态低下为主要特征的体质状态',
          traits: ['容易疲乏，精力不足', '说话声音偏低，不喜多言', '容易感冒，抵抗力较弱'],
          advices: [
            { title: '饮食调理', content: '宜食益气健脾食物，如黄芪、党参、山药、大枣。避免生冷寒凉食物。' },
            { title: '运动建议', content: '适合柔和运动，如太极拳、八段锦、散步。避免剧烈运动和大量出汗。' }
          ]
        }
      });
      this._showMemberPickerForConstitution();
    }
  },

  async _showMemberPickerForConstitution() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && (res.items || res)) || [];
      const members = items.map(m => ({
        id: m.id,
        name: m.relation_type_name || m.nickname || '本人',
        color: getRelationColor(m.relation_type_name || ''),
        is_self: m.is_self
      }));
      if (!members.some(m => m.is_self)) {
        members.unshift({ id: 0, name: '本人', color: '#52c41a', is_self: true });
      }
      const selfMember = members.find(m => m.is_self) || members[0];
      this.setData({
        familyMembers: members,
        selectedMemberId: selfMember ? selfMember.id : null,
        showMemberPicker: true
      });
    } catch (e) {
      this.setData({ showMemberPicker: true, familyMembers: [{ id: 0, name: '本人', color: '#52c41a', is_self: true }], selectedMemberId: 0 });
    }
  },

  onSelectMember(e) {
    const member = e.currentTarget.dataset.member;
    this.setData({ selectedMemberId: member.id });
  },

  onConfirmMember() {
    const member = this.data.familyMembers.find(m => m.id === this.data.selectedMemberId);
    if (!member) {
      wx.showToast({ title: '请选择咨询对象', icon: 'none' });
      return;
    }
    this.setData({ showMemberPicker: false });

    const result = this.data.result;
    const constitutionType = result ? result.type : '';
    const memberId = member.id;
    const memberName = member.name || '本人';
    const summary = encodeURIComponent(`体质测评 · ${constitutionType} · ${memberName}`);

    wx.navigateTo({
      url: `/pages/chat/index?type=constitution&family_member_id=${memberId}&summary=${summary}`
    });
  },

  onCancelMemberPicker() {
    this.setData({ showMemberPicker: false });
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

  goHistoryDetail(e) {
    const item = e.currentTarget.dataset.item;
    if (!item || !item.id) return;
    wx.navigateTo({
      url: `/pages/tcm-diagnosis-detail/index?id=${item.id}`
    });
  },

  resetAll() {
    this.setData({
      showQuiz: false,
      showResult: false,
      currentQuestion: 0,
      quizAnswers: [],
      result: null
    });
  }
});
