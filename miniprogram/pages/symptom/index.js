const { get, post, put } = require('../../utils/request');

const RELATION_EMOJI = {
  '本人': '👤',
  '爸爸': '👨',
  '妈妈': '👩',
  '老公': '💑',
  '老婆': '💑',
  '儿子': '👦',
  '女儿': '👧',
  '哥哥': '👱‍♂️',
  '弟弟': '🧑',
  '姐姐': '👱‍♀️',
  '妹妹': '👧',
  '爷爷': '👴',
  '奶奶': '👵',
  '外公': '👴',
  '外婆': '👵',
  '其他': '🧑',
};

function getMemberEmoji(name) {
  return RELATION_EMOJI[name] || '🧑';
}

function getCustomItems(items) {
  return (items || []).filter(i => typeof i === 'object' && i.type === 'custom');
}

Page({
  data: {
    currentStep: 0,
    members: [],
    selectedMemberId: null,
    selectedMemberName: '',
    membersLoaded: false,

    // Health info editing panel
    showHealthEdit: false,
    chronicPresets: [],
    allergyPresets: [],
    geneticPresets: [],
    chronic_diseases: [],
    allergies: [],
    genetic_diseases: [],
    chronicCustomItems: [],
    allergyCustomItems: [],
    geneticCustomItems: [],
    showChronicOther: false,
    showAllergyOther: false,
    showGeneticOther: false,
    chronicOtherInput: '',
    allergyOtherInput: '',
    geneticOtherInput: '',

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

  onLoad() {
    this.loadFamilyMembers();
    this.loadPresets();
  },

  async loadPresets() {
    try {
      const [chronicRes, allergyRes, geneticRes] = await Promise.all([
        get('/api/disease-presets', { category: 'chronic' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'allergy' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'genetic' }, { showLoading: false, suppressErrorToast: true })
      ]);
      this.setData({
        chronicPresets: (chronicRes && chronicRes.items) || [],
        allergyPresets: (allergyRes && allergyRes.items) || [],
        geneticPresets: (geneticRes && geneticRes.items) || []
      });
    } catch (e) {
      console.log('loadPresets error', e);
    }
  },

  async loadFamilyMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const list = (res && (res.items || res)) || [];
      const members = list.map(m => ({
        id: m.id,
        nickname: m.nickname,
        relationship_type: m.relationship_type || '本人',
        is_self: m.is_self,
        emoji: getMemberEmoji(m.relationship_type || '本人'),
        label: `${getMemberEmoji(m.relationship_type || '本人')} ${m.relationship_type || '本人'} ${m.nickname}`
      }));

      members.sort((a, b) => (b.is_self ? 1 : 0) - (a.is_self ? 1 : 0));

      const selfMember = members.find(m => m.is_self) || members[0];
      this.setData({
        members,
        membersLoaded: true,
        selectedMemberId: selfMember ? selfMember.id : null,
        selectedMemberName: selfMember ? selfMember.label : ''
      });

      if (selfMember) {
        this.loadMemberHealth(selfMember);
      }
    } catch (e) {
      this.setData({ membersLoaded: true });
    }
  },

  async loadMemberHealth(member) {
    try {
      let profile;
      if (member.is_self) {
        profile = await get('/api/health/profile', {}, { showLoading: false, suppressErrorToast: true });
      } else {
        profile = await get(`/api/health/profile/member/${member.id}`, {}, { showLoading: false, suppressErrorToast: true });
      }
      if (profile) {
        const cd = profile.chronic_diseases || [];
        const al = profile.allergies || [];
        const gd = profile.genetic_diseases || [];
        this.setData({
          chronic_diseases: cd,
          allergies: al,
          genetic_diseases: gd,
          chronicCustomItems: getCustomItems(cd),
          allergyCustomItems: getCustomItems(al),
          geneticCustomItems: getCustomItems(gd)
        });
      }
    } catch (e) {
      this.setData({
        chronic_diseases: [], allergies: [], genetic_diseases: [],
        chronicCustomItems: [], allergyCustomItems: [], geneticCustomItems: []
      });
    }
  },

  selectMember(e) {
    const member = e.currentTarget.dataset.member;
    this.setData({
      selectedMemberId: member.id,
      selectedMemberName: member.label
    });
    this.loadMemberHealth(member);
  },

  toggleHealthEdit() {
    this.setData({ showHealthEdit: !this.data.showHealthEdit });
  },

  // ── Chronic disease handlers ──
  toggleChronicPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.chronic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ chronic_diseases: items });
  },

  toggleChronicOther() {
    this.setData({ showChronicOther: !this.data.showChronicOther });
  },

  onChronicOtherInput(e) {
    this.setData({ chronicOtherInput: e.detail.value });
  },

  confirmChronicOther() {
    const val = (this.data.chronicOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.chronicPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.chronic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items), chronicOtherInput: '' });
  },

  removeChronicCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.chronic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items) });
  },

  // ── Allergy handlers ──
  toggleAllergyPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.allergies];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ allergies: items });
  },

  toggleAllergyOther() {
    this.setData({ showAllergyOther: !this.data.showAllergyOther });
  },

  onAllergyOtherInput(e) {
    this.setData({ allergyOtherInput: e.detail.value });
  },

  confirmAllergyOther() {
    const val = (this.data.allergyOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.allergyPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.allergies];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items), allergyOtherInput: '' });
  },

  removeAllergyCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.allergies.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items) });
  },

  // ── Genetic disease handlers ──
  toggleGeneticPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.genetic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ genetic_diseases: items });
  },

  toggleGeneticOther() {
    this.setData({ showGeneticOther: !this.data.showGeneticOther });
  },

  onGeneticOtherInput(e) {
    this.setData({ geneticOtherInput: e.detail.value });
  },

  confirmGeneticOther() {
    const val = (this.data.geneticOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.geneticPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.genetic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items), geneticOtherInput: '' });
  },

  removeGeneticCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.genetic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items) });
  },

  async saveHealthInfo() {
    const member = this.data.members.find(m => m.id === this.data.selectedMemberId);
    if (!member) return;

    const payload = {
      chronic_diseases: this.data.chronic_diseases,
      allergies: this.data.allergies,
      genetic_diseases: this.data.genetic_diseases
    };

    try {
      if (member.is_self) {
        await put('/api/health/profile', payload);
      } else {
        await put(`/api/health/profile/member/${member.id}`, payload);
      }
      wx.showToast({ title: '健康信息已保存', icon: 'success' });
      this.setData({ showHealthEdit: false });
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  },

  // ── Symptom flow (unchanged) ──
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
    const memberName = this.data.selectedMemberName;
    const question = memberName
      ? `为${memberName}咨询，症状：${selected}`
      : `我有以下症状：${selected}`;
    wx.navigateTo({
      url: `/pages/chat/index?type=symptom&question=${encodeURIComponent(question)}`
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
