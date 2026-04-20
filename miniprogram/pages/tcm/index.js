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
    pendingDiagnosisType: null,

    // StepBar（PRD v1.0 § 3.2）：0=答题 / 1=选择对象 / 2=AI 分析
    stepItems: ['答题', '选择对象', 'AI 分析'],
    currentStep: 0,

    // 测评记录（PRD v1.0：替代原"历史记录"，使用原"我的档案"数据源与样式）
    archiveList: [],
    archiveLoading: false
  },

  onShow() {
    this.loadTcmConfig();
    this.loadArchiveList();
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

  async loadArchiveList() {
    this.setData({ archiveLoading: true });
    try {
      const res = await get('/api/constitution/archive', { page: 1, page_size: 50 }, { showLoading: false, suppressErrorToast: true });
      const list = (res && (res.items || [])) || [];
      const archiveList = list.map(item => ({
        diagnosis_id: item.diagnosis_id,
        constitution_type: item.constitution_type || '未知',
        persona_emoji: item.persona_emoji || '🌿',
        persona_color: item.persona_color || '#52c41a',
        one_line_desc: item.one_line_desc || '',
        member_label: item.member_label || '本人',
        created_at_text: this._formatTime(item.created_at),
      }));
      this.setData({ archiveList });
    } catch (e) {
      console.log('loadArchiveList error', e);
    } finally {
      this.setData({ archiveLoading: false });
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
      success: () => {
        this._showMemberPickerForDiagnosis('tcm_tongue');
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
      success: () => {
        this._showMemberPickerForDiagnosis('tcm_face');
      }
    });
  },

  async _showMemberPickerForDiagnosis(diagnosisType) {
    this.setData({ pendingDiagnosisType: diagnosisType });
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
      this.setData({
        showMemberPicker: true,
        familyMembers: [{ id: 0, name: '本人', color: '#52c41a', is_self: true }],
        selectedMemberId: 0
      });
    }
  },

  async _createDiagnosisSessionAndChat(diagnosisType, member) {
    const memberName = (member && member.name) || '本人';
    const isTongue = diagnosisType === 'tcm_tongue';
    const title = `${isTongue ? '舌诊' : '面诊'}咨询 · ${memberName}`;
    const userMsg = isTongue
      ? '我刚完成了舌诊拍照，请帮我分析舌象并给出调理建议'
      : '我刚完成了面诊拍照，请帮我分析面色并给出调理建议';
    wx.showLoading({ title: '创建会话中...', mask: true });
    try {
      const payload = { session_type: diagnosisType, title };
      if (member && member.id !== undefined && member.id !== null && member.id !== 0) {
        payload.family_member_id = member.id;
      }
      const session = await post('/api/chat/sessions', payload, { showLoading: false, suppressErrorToast: true });
      wx.hideLoading();
      const sessionId = session && (session.id || session.session_id);
      const memberIdParam = (member && member.id) || 0;
      const msg = encodeURIComponent(userMsg);
      let url = `/pages/chat/index?type=${diagnosisType}&family_member_id=${memberIdParam}&msg=${msg}`;
      if (sessionId) url += `&session_id=${sessionId}`;
      wx.navigateTo({ url });
    } catch (e) {
      wx.hideLoading();
      const memberIdParam = (member && member.id) || 0;
      const msg = encodeURIComponent(userMsg);
      wx.navigateTo({
        url: `/pages/chat/index?type=${diagnosisType}&family_member_id=${memberIdParam}&msg=${msg}`
      });
    }
  },

  startConstitution() {
    if (!checkLogin()) return;
    this.setData({ showQuiz: true, showResult: false, currentQuestion: 0, quizAnswers: [], currentStep: 0 });
  },

  goTcmChat() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=tcm' });
  },

  // 测评记录卡片点击 → 统一跳 6 屏结果页（PRD v1.0 § Q18）
  goArchiveDetail(e) {
    const diagnosisId = e.currentTarget.dataset.id;
    if (!diagnosisId) return;
    wx.navigateTo({ url: `/pages/tcm-constitution-result/index?id=${diagnosisId}` });
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
      // 答完全部题目 → 先弹咨询人选择（StepBar 进入"选择对象"阶段）
      this.setData({ currentStep: 1 });
      this._showMemberPickerForConstitution();
    }
  },

  async _submitConstitutionTest(answers, familyMemberId) {
    // StepBar 进入"AI 分析"阶段
    this.setData({ currentStep: 2 });
    wx.showLoading({ title: '分析中...', mask: true });
    try {
      const answersArr = (answers || []).map((value, idx) => ({
        question_id: idx + 1,
        answer_value: String(value)
      }));
      const payload = { answers: answersArr };
      if (familyMemberId !== undefined && familyMemberId !== null && familyMemberId !== 0) {
        payload.family_member_id = familyMemberId;
      }
      const res = await post('/api/tcm/constitution-test', payload, { showLoading: false, suppressErrorToast: true });

      wx.hideLoading();

      // 新版：跳转到 6 屏结果页
      const diagnosisId = res && (res.id || res.diagnosis_id);
      if (diagnosisId) {
        // 重置本页状态，避免从结果页返回时回到答题状态
        this.setData({ showQuiz: false, showResult: false, currentQuestion: 0, quizAnswers: [], currentStep: 0 });
        wx.navigateTo({ url: `/pages/tcm-constitution-result/index?id=${diagnosisId}` });
        this.loadArchiveList();
        return;
      }

      // 兜底：未返回 id，退回旧版面内展示
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
            id: diagnosisId
          }
        });
        this.loadArchiveList();
      }
    } catch (e) {
      wx.hideLoading();
      const detail = (e && e.data && e.data.detail) || (e && e.message) || '提交测评失败，请重试';
      wx.showToast({ title: typeof detail === 'string' ? detail : '提交失败', icon: 'none' });
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

  async onConfirmMember() {
    const member = this.data.familyMembers.find(m => m.id === this.data.selectedMemberId);
    if (!member) {
      wx.showToast({ title: '请选择咨询对象', icon: 'none' });
      return;
    }
    this.setData({ showMemberPicker: false });

    // 情形 0: 舌诊 / 面诊 选定咨询人 → 创建会话并跳转 chat
    if (this.data.pendingDiagnosisType) {
      const diagnosisType = this.data.pendingDiagnosisType;
      this.setData({ pendingDiagnosisType: null });
      await this._createDiagnosisSessionAndChat(diagnosisType, member);
      return;
    }

    // 情形 1: 答完 9 题但还未提交（无 result）→ 提交测评
    if (!this.data.result) {
      await this._submitConstitutionTest(this.data.quizAnswers, member.id);
      return;
    }

    // 情形 2: 已得到测评结果，跳转 chat 咨询
    const result = this.data.result;
    const constitutionType = result ? result.type : '';
    const memberId = member.id;
    const memberName = member.name || '本人';
    const summary = encodeURIComponent(`体质测评 · ${constitutionType} · ${memberName}`);
    const msg = encodeURIComponent('请根据我的体质测评结果详细介绍调理方案');

    wx.navigateTo({
      url: `/pages/chat/index?type=constitution_test&family_member_id=${memberId}&summary=${summary}&msg=${msg}`
    });
  },

  onCancelMemberPicker() {
    this.setData({ showMemberPicker: false, pendingDiagnosisType: null, currentStep: 0 });
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
      quizAnswers: [],
      result: null,
      currentStep: 0
    });
  }
});
