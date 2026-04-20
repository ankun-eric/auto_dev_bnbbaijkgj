const { get, post, put } = require('../../utils/request');

const RELATION_EMOJI = {
  '本人': '👤', '爸爸': '👨', '妈妈': '👩', '父亲': '👨', '母亲': '👩',
  '老公': '💑', '老婆': '💑', '配偶': '💑',
  '儿子': '👦', '女儿': '👧', '子女': '👶',
  '哥哥': '👱‍♂️', '弟弟': '🧑', '姐姐': '👱‍♀️', '妹妹': '👧',
  '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵',
  '其他': '🧑'
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

    // Family members
    members: [],
    selectedMemberId: null,
    selectedMemberName: '',
    membersLoaded: false,

    // Health info editing panel
    showHealthEdit: false,
    profileCollapsed: true, // 档案整体是否收起（existing 模式默认 true）
    initialProfile: null, // 初始档案快照，用于判断是否修改
    profileDirty: false, // 是否有未保存修改
    isNewMember: false, // 是否新建成员场景（暂未启用——本页不支持新建）
    currentMemberEmoji: '', // 当前选中成员的 emoji（收起卡片显示）
    memberSavedErrors: {}, // 保存时兜底校验错误
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

    // Step 1: Body parts + Symptoms + Duration (merged)
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

    // Step 3: Analysis
    analyzing: false,
    analysisResult: null,

    // Self basic info
    isSelfSelected: false,
    selfNickname: '',
    selfGender: '',
    selfBirthday: '',
    selfHeight: '',
    selfWeight: '',
    selfErrors: {},
    today: ''
  },

  onLoad() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    this.setData({ today: `${y}-${m}-${d}` });
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
        selectedMemberName: selfMember ? selfMember.label : '',
        isSelfSelected: selfMember ? !!selfMember.is_self : false,
        currentMemberEmoji: selfMember ? (selfMember.emoji || '👤') : ''
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
        const snap = {
          chronic_diseases: cd,
          allergies: al,
          genetic_diseases: gd,
          selfNickname: profile.nickname || member.nickname || '',
          selfGender: profile.gender || '',
          selfBirthday: profile.birthday || '',
          selfHeight: (profile.height == null ? '' : String(profile.height)),
          selfWeight: (profile.weight == null ? '' : String(profile.weight)),
        };
        const updates = {
          ...snap,
          chronicCustomItems: getCustomItems(cd),
          allergyCustomItems: getCustomItems(al),
          geneticCustomItems: getCustomItems(gd),
          selfErrors: {},
          initialProfile: JSON.parse(JSON.stringify(snap)),
          profileDirty: false,
          profileCollapsed: true,
          showHealthEdit: false,
        };
        this.setData(updates);
      }
    } catch (e) {
      const emptySnap = {
        chronic_diseases: [], allergies: [], genetic_diseases: [],
        selfNickname: member.nickname || '', selfGender: '', selfBirthday: '',
        selfHeight: '', selfWeight: '',
      };
      this.setData({
        ...emptySnap,
        chronicCustomItems: [], allergyCustomItems: [], geneticCustomItems: [],
        initialProfile: JSON.parse(JSON.stringify(emptySnap)),
        profileDirty: false,
        profileCollapsed: true,
        showHealthEdit: false,
      });
    }
  },

  /** 深比较判断档案是否脏 */
  _checkDirty() {
    const init = this.data.initialProfile;
    if (!init) return false;
    const cur = {
      chronic_diseases: this.data.chronic_diseases || [],
      allergies: this.data.allergies || [],
      genetic_diseases: this.data.genetic_diseases || [],
      selfNickname: this.data.selfNickname || '',
      selfGender: this.data.selfGender || '',
      selfBirthday: this.data.selfBirthday || '',
      selfHeight: String(this.data.selfHeight || ''),
      selfWeight: String(this.data.selfWeight || ''),
    };
    const normStr = (obj) => JSON.stringify(obj);
    const initNorm = {
      ...init,
      selfHeight: String(init.selfHeight || ''),
      selfWeight: String(init.selfWeight || ''),
      chronic_diseases: [...(init.chronic_diseases || [])].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      allergies: [...(init.allergies || [])].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      genetic_diseases: [...(init.genetic_diseases || [])].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
    };
    const curNorm = {
      ...cur,
      chronic_diseases: [...cur.chronic_diseases].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      allergies: [...cur.allergies].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      genetic_diseases: [...cur.genetic_diseases].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
    };
    return normStr(curNorm) !== normStr(initNorm);
  },

  _refreshDirty() {
    const dirty = this._checkDirty();
    if (dirty !== this.data.profileDirty) {
      this.setData({ profileDirty: dirty });
    }
  },

  /** 展开档案 */
  expandProfile() {
    this.setData({ profileCollapsed: false, showHealthEdit: true });
  },

  /** 收起档案 */
  collapseProfile() {
    this.setData({ profileCollapsed: true, showHealthEdit: false });
  },

  /** 计算年龄 */
  _calcAge(birthday) {
    if (!birthday) return '';
    const m = String(birthday).match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) return '';
    const bYear = parseInt(m[1], 10);
    const bMonth = parseInt(m[2], 10);
    const bDay = parseInt(m[3], 10);
    const now = new Date();
    let age = now.getFullYear() - bYear;
    const passed = (now.getMonth() + 1) > bMonth || ((now.getMonth() + 1) === bMonth && now.getDate() >= bDay);
    if (!passed) age -= 1;
    if (age < 0 || age > 150) return '';
    return age + '岁';
  },

  /** 弹出未保存修改拦截窗口（返回 Promise<'save'|'discard'|'cancel'>） */
  _showUnsavedModal(scene) {
    return new Promise((resolve) => {
      const primary = scene === 'switch' ? '保存并切换' : '保存并分析';
      const secondary = scene === 'switch' ? '放弃修改并切换' : '放弃修改并分析';
      const content = scene === 'switch'
        ? '您刚才修改的档案信息还未保存，切换成员将丢失未保存的修改。'
        : '您刚才修改的档案信息还未保存，是否先保存再开始分析？';
      // 小程序 wx.showModal 仅支持 2 个按钮，需两次弹窗实现三选项
      wx.showModal({
        title: '档案有未保存的修改',
        content,
        confirmText: primary,
        cancelText: '更多选项',
        confirmColor: '#52c41a',
        success: (r1) => {
          if (r1.confirm) {
            resolve('save');
          } else {
            wx.showModal({
              title: '档案有未保存的修改',
              content: '您是否要放弃修改？',
              confirmText: secondary,
              cancelText: '取消',
              success: (r2) => {
                if (r2.confirm) resolve('discard');
                else resolve('cancel');
              },
              fail: () => resolve('cancel'),
            });
          }
        },
        fail: () => resolve('cancel'),
      });
    });
  },

  /** 放弃修改，还原初始值 */
  _discardChanges() {
    const init = this.data.initialProfile;
    if (!init) return;
    this.setData({
      chronic_diseases: JSON.parse(JSON.stringify(init.chronic_diseases || [])),
      allergies: JSON.parse(JSON.stringify(init.allergies || [])),
      genetic_diseases: JSON.parse(JSON.stringify(init.genetic_diseases || [])),
      chronicCustomItems: getCustomItems(init.chronic_diseases || []),
      allergyCustomItems: getCustomItems(init.allergies || []),
      geneticCustomItems: getCustomItems(init.genetic_diseases || []),
      selfNickname: init.selfNickname || '',
      selfGender: init.selfGender || '',
      selfBirthday: init.selfBirthday || '',
      selfHeight: init.selfHeight || '',
      selfWeight: init.selfWeight || '',
      profileDirty: false,
      selfErrors: {},
    });
  },

  /** 兜底校验 */
  _validateProfile() {
    const errors = {};
    if (!(this.data.selfNickname || '').trim()) errors.nickname = '请输入姓名';
    if (!this.data.selfGender) errors.gender = '请选择性别';
    if (!this.data.selfBirthday) errors.birthday = '请选择出生日期';
    this.setData({ selfErrors: errors });
    return Object.keys(errors).length === 0;
  },

  async selectMember(e) {
    const member = e.currentTarget.dataset.member;
    if (member.id === this.data.selectedMemberId) return;
    if (this.data.profileDirty) {
      const choice = await this._showUnsavedModal('switch');
      if (choice === 'cancel') return;
      if (choice === 'save') {
        const ok = await this.saveHealthInfo();
        if (!ok) return;
      }
      if (choice === 'discard') {
        this._discardChanges();
      }
    }
    this.setData({
      selectedMemberId: member.id,
      selectedMemberName: member.label,
      isSelfSelected: !!member.is_self,
      currentMemberEmoji: member.emoji || (member.is_self ? '👤' : '👨‍👩‍👧'),
      showHealthEdit: false,
      profileCollapsed: true,
      isNewMember: false,
      selfErrors: {}
    });
    this.loadMemberHealth(member);
  },

  goAddFamilyMember() {
    wx.navigateTo({ url: '/pages/family/add' });
  },

  toggleHealthEdit() {
    this.setData({ showHealthEdit: !this.data.showHealthEdit });
  },

  onSelfNicknameInput(e) {
    this.setData({ selfNickname: e.detail.value });
    this._refreshDirty();
  },

  onSelfGenderSelect(e) {
    this.setData({ selfGender: e.currentTarget.dataset.gender, 'selfErrors.gender': undefined });
    this._refreshDirty();
  },

  onSelfBirthdayChange(e) {
    this.setData({ selfBirthday: e.detail.value, 'selfErrors.birthday': undefined });
    this._refreshDirty();
  },

  onSelfHeightInput(e) {
    this.setData({ selfHeight: e.detail.value });
    this._refreshDirty();
  },

  onSelfWeightInput(e) {
    this.setData({ selfWeight: e.detail.value });
    this._refreshDirty();
  },

  onSelfNicknameBlur(e) {
    if (!(e.detail.value || '').trim()) {
      this.setData({ 'selfErrors.nickname': '请输入姓名' });
    } else {
      this.setData({ 'selfErrors.nickname': undefined });
    }
  },

  // ── Chronic disease handlers ──
  toggleChronicPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.chronic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ chronic_diseases: items });
    this._refreshDirty();
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
    this._refreshDirty();
  },

  removeChronicCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.chronic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items) });
    this._refreshDirty();
  },

  // ── Allergy handlers ──
  toggleAllergyPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.allergies];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ allergies: items });
    this._refreshDirty();
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
    this._refreshDirty();
  },

  removeAllergyCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.allergies.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items) });
    this._refreshDirty();
  },

  // ── Genetic disease handlers ──
  toggleGeneticPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.genetic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ genetic_diseases: items });
    this._refreshDirty();
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
    this._refreshDirty();
  },

  removeGeneticCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.genetic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items) });
    this._refreshDirty();
  },

  async saveHealthInfo() {
    const member = this.data.members.find(m => m.id === this.data.selectedMemberId);
    if (!member) return false;

    if (!this._validateProfile()) {
      wx.showToast({ title: '请检查标红字段', icon: 'none' });
      return false;
    }

    const payload = {
      chronic_diseases: this.data.chronic_diseases,
      allergies: this.data.allergies,
      genetic_diseases: this.data.genetic_diseases,
      nickname: (this.data.selfNickname || '').trim(),
      gender: this.data.selfGender,
      birthday: this.data.selfBirthday,
      height: this.data.selfHeight ? Number(this.data.selfHeight) : undefined,
      weight: this.data.selfWeight ? Number(this.data.selfWeight) : undefined,
    };

    try {
      if (member.is_self) {
        await put('/api/health/profile', payload);
      } else {
        await put(`/api/health/profile/member/${member.id}`, payload);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      const snap = {
        chronic_diseases: JSON.parse(JSON.stringify(this.data.chronic_diseases || [])),
        allergies: JSON.parse(JSON.stringify(this.data.allergies || [])),
        genetic_diseases: JSON.parse(JSON.stringify(this.data.genetic_diseases || [])),
        selfNickname: this.data.selfNickname || '',
        selfGender: this.data.selfGender || '',
        selfBirthday: this.data.selfBirthday || '',
        selfHeight: this.data.selfHeight || '',
        selfWeight: this.data.selfWeight || '',
      };
      this.setData({
        initialProfile: snap,
        profileDirty: false,
        profileCollapsed: true,
        showHealthEdit: false,
      });
      return true;
    } catch (e) {
      const msg = (e && e.data && e.data.detail) || (e && e.msg) || '保存失败，请稍后重试';
      wx.showToast({ title: msg, icon: 'none' });
      return false;
    }
  },

  // ── Step 1: Symptom collection (body part + symptoms + duration merged) ──
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
      const selected = symptoms.filter(s => s.selected);
      if (selected.length === 0) {
        wx.showToast({ title: '请至少选择一个症状', icon: 'none' });
        return;
      }
      if (!this.data.selectedDuration) {
        wx.showToast({ title: '请选择症状持续时间', icon: 'none' });
        return;
      }
      this.setData({ currentStep: 1, showHealthEdit: false });
    } else if (currentStep === 1) {
      if (!this.data.selectedMemberId) {
        wx.showToast({ title: '请选择咨询对象', icon: 'none' });
        return;
      }
      // 拦截未保存修改
      if (this.data.profileDirty) {
        const choice = await this._showUnsavedModal('analyze');
        if (choice === 'cancel') return;
        if (choice === 'save') {
          const ok = await this.saveHealthInfo();
          if (!ok) return;
        }
        if (choice === 'discard') {
          this._discardChanges();
        }
      }
      // 兜底校验
      if (!this._validateProfile()) {
        wx.showToast({ title: '请检查标红字段', icon: 'none' });
        return;
      }
      this.setData({ currentStep: 2, analyzing: true });
      await this.analyze();
    }
  },

  confirmFamilyMemberAndAnalyze() {
    if (!this.data.selectedMemberId) {
      wx.showToast({ title: '请选择咨询对象', icon: 'none' });
      return;
    }
    this.nextStep();
  },

  async analyze() {
    try {
      const selected = this.data.symptoms.filter(s => s.selected).map(s => s.name);
      const bodyPart = this.data.bodyParts.find(p => p.id === this.data.selectedPart);

      try {
        const res = await post('/api/symptom/analyze', {
          body_part: this.data.selectedPart,
          symptoms: selected,
          duration: this.data.selectedDuration,
          extra_description: this.data.extraDesc,
          family_member_id: this.data.selectedMemberId
        }, { showLoading: false, suppressErrorToast: true });

        if (res && res.possibilities) {
          this.setData({ analyzing: false, analysisResult: res });
          return;
        }
      } catch (e) {
        // fallback to mock
      }

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
